#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2022 Huawei Device Co., Ltd.
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

import io
import os
import hashlib
import struct

from log_exception import UPDATE_LOGGER
from asn1crypto import cms
from asn1crypto import pem
from asn1crypto import util
from asn1crypto import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes

operation_path = os.path.dirname(os.path.realpath(__file__))
CERT_PATH = os.path.join(operation_path, 'sign_cert/signing_cert.crt')
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


def load_public_cert():
    with open(CERT_PATH, 'rb') as cert_file:
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


def sign_ota_package(package_path, signed_package, private_key):
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

    cert = load_public_cert()

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