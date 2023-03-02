#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (c) 2023 Huawei Device Co., Ltd.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
The tool for making module package.

positional arguments:
  target_package        Target package file path.
  update_package        Update package file path.
  -pn PACKAGE_NAME, --package_name PACKAGE_NAME
                        Module package name.
  -pk PRIVATE_KEY, --private_key PRIVATE_KEY
                        Private key file path.
  -sc SIGN_CERT, --sign_cert SIGN_CERT
                        Sign cert file path.
"""
import os
import sys
import argparse
import subprocess
import hashlib
import zipfile
import io
import struct
import logging

from asn1crypto import cms
from asn1crypto import pem
from asn1crypto import util
from asn1crypto import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes


# 1000000: max number of function recursion depth
MAXIMUM_RECURSION_DEPTH = 1000000
sys.setrecursionlimit(MAXIMUM_RECURSION_DEPTH)

BLCOK_SIZE = 8192
FOOTER_LENGTH = 6
ZIP_ECOD_LENGTH = 22
DIGEST_SHA256 = 672
SHA256_HASH_LEN = 32

CONTENT_INFO_FORMAT = "<2H32s"
# the length of zip eocd comment
ZIP_EOCD_COMMENT_LEN_FORMAT = "<H"
# signed package footer
SIGANTURE_FOOTER_FORMAT = "<3H"

SIGN_TOOL_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'zipalign.jar')


def target_package_check(arg):
    """
    Argument check, which is used to check whether the specified arg is a file path.
    :param arg: the arg to check.
    :return:  Check result, which is False if the arg is invalid.
    """
    if not os.path.isdir(arg):
        UPDATE_LOGGER.print_log(
            "Target package error, path: %s" % arg, UPDATE_LOGGER.ERROR_LOG)
        return False
    return arg


def package_name_check(arg):
    """
    Argument check, which is used to check whether the specified arg is none.
    :param arg: the arg to check.
    :return: Check result, which is False if the arg is invalid.
    """
    if arg is None:
        UPDATE_LOGGER.print_log(
            "Package name error: %s" % arg, UPDATE_LOGGER.ERROR_LOG)
        return False
    return arg


def private_key_check(arg):
    """
    Argument check, which is used to check whether
    the specified arg is a private key.
    :param arg: the arg to check.
    :return: Check result, which is False if the arg is invalid.
    """
    if arg != "ON_SERVER" and not os.path.isfile(arg):
        UPDATE_LOGGER.print_log(
            "FileNotFoundError, path: %s" % arg, UPDATE_LOGGER.ERROR_LOG)
        return False
    return arg


def sign_cert_check(arg):
    """
    Argument check, which is used to check whether
    the specified arg is a sign cert.
    :param arg: the arg to check.
    :return: Check result, which is False if the arg is invalid.
    """
    if arg != "ON_SERVER" and not os.path.isfile(arg):
        UPDATE_LOGGER.print_log(
            "FileNotFoundError, path: %s" % arg, UPDATE_LOGGER.ERROR_LOG)
        return False
    return arg


def check_update_package(arg):
    """
    Argument check, which is used to check whether
    the update package path exists.
    :param arg: The arg to check.
    :return: Check result
    """
    make_dir_path = None
    if os.path.exists(arg):
        if os.path.isfile(arg):
            UPDATE_LOGGER.print_log(
                "Update package must be a dir path, not a file path. "
                "path: %s" % arg, UPDATE_LOGGER.ERROR_LOG)
            return False
    else:
        try:
            UPDATE_LOGGER.print_log(
                "Update package path does not exist. The dir will be created!"
                "path: %s" % arg, UPDATE_LOGGER.WARNING_LOG)
            os.makedirs(arg)
            make_dir_path = arg
        except OSError:
            UPDATE_LOGGER.print_log(
                "Make update package path dir failed! "
                "path: %s" % arg, UPDATE_LOGGER.ERROR_LOG)
            return False
    return arg


class UpdateToolLogger:
    """
    Global log class
    """
    INFO_LOG = 'INFO_LOG'
    WARNING_LOG = 'WARNING_LOG'
    ERROR_LOG = 'ERROR_LOG'
    LOG_TYPE = (INFO_LOG, WARNING_LOG, ERROR_LOG)

    def __init__(self, output_type='console'):
        self.__logger_obj = self.__get_logger_obj(output_type=output_type)

    @staticmethod
    def __get_logger_obj(output_type='console'):
        ota_logger = logging.getLogger(__name__)
        ota_logger.setLevel(level=logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s : %(message)s',
            "%Y-%m-%d %H:%M:%S")
        if output_type == 'console':
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)
            ota_logger.addHandler(console_handler)
        elif output_type == 'file':
            file_handler = logging.FileHandler("UpdateToolLog.txt")
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            ota_logger.addHandler(file_handler)
        return ota_logger

    def print_log(self, msg, log_type=INFO_LOG):
        """
        Print log information.
        :param msg: log information
        :param log_type: log type
        :return:
        """
        if log_type == self.LOG_TYPE[0]:
            self.__logger_obj.info(msg)
        elif log_type == self.LOG_TYPE[1]:
            self.__logger_obj.warning(msg)
        elif log_type == self.LOG_TYPE[2]:
            self.__logger_obj.error(msg)
        else:
            self.__logger_obj.error("Unknown log type! %s", log_type)
            return False
        return True

    def print_uncaught_exception_msg(self, msg, exc_info):
        """
        Print log when an uncaught exception occurs.
        :param msg: Uncaught exception
        :param exc_info: information about the uncaught exception
        """
        self.__logger_obj.error(msg, exc_info=exc_info)


UPDATE_LOGGER = UpdateToolLogger()


def load_public_cert(sign_cert):
    with open(sign_cert, 'rb') as cert_file:
        der_bytes = cert_file.read()
        if pem.detect(der_bytes):
            type_name, headers, der_bytes = pem.unarmor(der_bytes)

    return x509.Certificate.load(der_bytes)


def calculate_package_hash(package_path):
    """
    :return: (hash) for path using hashlib.sha256()
    """
    hash_sha256 = hashlib.sha256()
    length = 0

    remain_len = os.path.getsize(package_path) - ZIP_ECOD_LENGTH
    with open(package_path, 'rb') as package_file:
        while remain_len > BLCOK_SIZE:
            hash_sha256.update(package_file.read(BLCOK_SIZE))
            remain_len -= BLCOK_SIZE
        if remain_len > 0:
            hash_sha256.update(package_file.read(remain_len))

    return hash_sha256.digest()


def sign_digest_with_pss(digset, private_key_file):
    # read private key from pem file
    try:
        with open(private_key_file, 'rb') as f_r:
            key_data = f_r.read()

        private_key = serialization.load_pem_private_key(
            key_data,
            password=None,
            backend=default_backend())
        pad = padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH)

        signature = private_key.sign(
            digset,
            pad,
            hashes.SHA256()
        )
    except (OSError, ValueError):
        return False
    return signature


def sign_digest(digset, private_key_file):
    # read private key from pem file
    try:
        with open(private_key_file, 'rb') as f_r:
            key_data = f_r.read()

        private_key = serialization.load_pem_private_key(
            key_data,
            password=None,
            backend=default_backend())

        signature = private_key.sign(
            digset,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
    except (OSError, ValueError):
        return False
    return signature


def create_encap_content_info(diget):
    if not diget:
        UPDATE_LOGGER.print_log("calc package hash failed! file: %s",
            log_type=UPDATE_LOGGER.ERROR_LOG)
        return False
    content_header = struct.pack(CONTENT_INFO_FORMAT, DIGEST_SHA256,
        SHA256_HASH_LEN, diget)
    return content_header


def write_signed_package(unsigned_package, signature, signed_package):
    """
    :Write signature to signed package
    """
    signature_size = len(signature)
    signature_total_size = signature_size + FOOTER_LENGTH

    package_fd = os.open(signed_package, os.O_RDWR | os.O_CREAT, 0o755)
    f_signed = os.fdopen(package_fd, 'wb')

    remain_len = os.path.getsize(unsigned_package) - 2
    with open(unsigned_package, 'rb') as f_unsign:
        while remain_len > BLCOK_SIZE:
            f_signed.write(f_unsign.read(BLCOK_SIZE))
            remain_len -= BLCOK_SIZE
        if remain_len > 0:
            f_signed.write(f_unsign.read(remain_len))

    zip_comment_len = struct.pack(ZIP_EOCD_COMMENT_LEN_FORMAT,
            signature_total_size)
    f_signed.write(zip_comment_len)

    f_signed.write(signature)
    footter = struct.pack(SIGANTURE_FOOTER_FORMAT, signature_total_size,
            0xffff, signature_total_size)
    f_signed.write(footter)
    f_signed.close()


def sign_ota_package(package_path, signed_package, private_key, sign_cert):
    digest = calculate_package_hash(package_path)
    data = create_encap_content_info(digest)
    signature = sign_digest(digest, private_key)

    digest_fd = os.open("digest", os.O_RDWR | os.O_CREAT, 0o755)
    digest_file = os.fdopen(digest_fd, 'wb')
    digest_file.write(digest)
    digest_file.close()

    signatute_fd = os.open("signature", os.O_RDWR | os.O_CREAT, 0o755)
    signatute_file = os.fdopen(signatute_fd, 'wb')
    signatute_file.write(signature)
    signatute_file.close()

    # Creating a SignedData object from cms
    signed_data = cms.SignedData()
    signed_data['version'] = 'v1'
    signed_data['encap_content_info'] = util.OrderedDict([
        ('content_type', 'data'),
        ('content', data)])

    signed_data['digest_algorithms'] = [util.OrderedDict([
        ('algorithm', 'sha256'),
        ('parameters', None)])]

    cert = load_public_cert(sign_cert)

    # Adding this certificate to SignedData object
    signed_data['certificates'] = [cert]

    # Setting signer info section
    signer_info = cms.SignerInfo()
    signer_info['version'] = 'v1'
    signer_info['digest_algorithm'] = util.OrderedDict([
                ('algorithm', 'sha256'),
                ('parameters', None)])
    signer_info['signature_algorithm'] = util.OrderedDict([
                ('algorithm', 'sha256_rsa'),
                ('parameters', None)])

    issuer = cert.issuer
    serial_number = cert.serial_number
    issuer_and_serial = cms.IssuerAndSerialNumber()
    issuer_and_serial['issuer'] = cert.issuer
    issuer_and_serial['serial_number'] = cert.serial_number

    key_id = cert.key_identifier_value.native
    signer_info['sid'] = cms.SignerIdentifier({
        'issuer_and_serial_number': issuer_and_serial})

    signer_info['signature'] = signature
    # Adding SignerInfo object to SignedData object
    signed_data['signer_infos'] = [signer_info]

    # Writing everything into ASN.1 object
    asn1obj = cms.ContentInfo()
    asn1obj['content_type'] = 'signed_data'
    asn1obj['content'] = signed_data

    # This asn1obj can be dumped to a disk using dump() method (DER format)
    write_signed_package(package_path, asn1obj.dump(), signed_package)
    return True


def build_module_package(package_name, target_package, update_package, private_key, sign_cert):
    unsigned_package = os.path.join(
        update_package, '%s_unsigned.zip' % package_name)

    zip_file = zipfile.ZipFile(unsigned_package, 'w')
    # add module.img to update package
    img_file_path = os.path.join(target_package, 'module.img')
    if os.path.exists(img_file_path):
        zip_file.write(img_file_path, "module.img")
    # add config.json to update package
    module_file_path = os.path.join(target_package, 'config.json')
    zip_file.write(module_file_path, "config.json")
    # add pub_key.pem to update package
    pub_key_file_path = os.path.join(target_package, 'pub_key.pem')
    if os.path.exists(pub_key_file_path):
        zip_file.write(pub_key_file_path, 'pub_key.pem')
    zip_file.close()

    # align package
    align_package = os.path.join(
        update_package, '%s_align.zip' % package_name)
    align_cmd = ['java', '-jar', SIGN_TOOL_PATH, unsigned_package, align_package, '4096']
    subprocess.call(align_cmd, shell=False)
    if not os.path.exists(align_package):
        UPDATE_LOGGER.print_log("align package failed", log_type=UPDATE_LOGGER.ERROR_LOG)
        return False

    # sign package
    signed_package = os.path.join(
        update_package, '%s.zip' % package_name)
    if os.path.exists(signed_package):
        os.remove(signed_package)

    sign_result = sign_ota_package(
        align_package,
        signed_package,
        private_key,
        sign_cert)

    if not sign_result:
        UPDATE_LOGGER.print_log("Sign module package fail", UPDATE_LOGGER.ERROR_LOG)
        return False
    if os.path.exists(align_package):
        os.remove(align_package)
    if os.path.exists(unsigned_package):
        os.remove(unsigned_package)

    return True


def main(argv):
    """
    Entry function.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("target_package", type=target_package_check,
                        help="Target package file path.")
    parser.add_argument("update_package", type=check_update_package,
                        help="Update package file path.")
    parser.add_argument("-pk", "--private_key", type=private_key_check,
                        default=None, help="Private key file path.")
    parser.add_argument("-sc", "--sign_cert", type=sign_cert_check,
                        default=None, help="Sign cert file path.")
    parser.add_argument("-pn", "--package_name", type=package_name_check,
                        default=None, help="Package name.")

    args = parser.parse_args(argv)

    # Generate the module package.
    build_re = build_module_package(args.package_name, args.target_package,
        args.update_package, args.private_key, args.sign_cert)

if __name__ == '__main__':
    main(sys.argv[1:])
