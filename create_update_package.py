#!/usr/bin/env python3
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
"""
Description : Generate the update.bin file
"""
import os
import struct
import hashlib
import subprocess
from log_exception import UPDATE_LOGGER
from utils import OPTIONS_MANAGER
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding

UPGRADE_FILE_HEADER_LEN = 180
UPGRADE_RESERVE_LEN = 16
SIGN_SHA256_LEN = 256
SIGN_SHA384_LEN = 384
UPGRADE_SIGNATURE_LEN = SIGN_SHA256_LEN + SIGN_SHA384_LEN
TLV_SIZE = 4
UPGRADE_PKG_HEADER_SIZE = 136
UPGRADE_PKG_TIME_SIZE = 32
UPGRADE_COMPINFO_SIZE = 71
UPGRADE_COMPINFO_SIZE_L2 = 87
COMPONEBT_ADDR_SIZE = 16
COMPONEBT_ADDR_SIZE_L2 = 32
COMPONENT_INFO_FMT_SIZE = 5
COMPONENT_VERSION_SIZE = 10
COMPONENT_SIZE_FMT_SIZE = 8
COMPONENT_DIGEST_SIZE = 32
BLCOK_SIZE = 8192
HEADER_TLV_TYPE = 0x11
HEADER_TLV_TYPE_L2 = 0x01
# signature algorithm
SIGN_ALGO_RSA = "SHA256withRSA"
SIGN_ALGO_PSS = "SHA256withPSS"

"""
Format
H: unsigned short
I: unsigned int
B: unsigned char
s: char[]
"""
TLV_FMT = "2H"
UPGRADE_PKG_HEADER_FMT = "2I64s64s"
UPGRADE_PKG_TIME_FMT = "16s16s"
COMPONENT_INFO_FMT = "H3B"
COMPONENT_SIZE_FMT = "iI"


class CreatePackage(object):
    """
    Create the update.bin file
    """

    def __init__(self, head_list, component_list, save_path, key_path):
        self.head_list = head_list
        self.component_list = component_list
        self.save_path = save_path
        self.key_path = key_path
        self.compinfo_offset = 0
        self.component_offset = 0
        self.sign_offset = 0

        if OPTIONS_MANAGER.not_l2:
            self.upgrade_compinfo_size = UPGRADE_COMPINFO_SIZE
            self.header_tlv_type = HEADER_TLV_TYPE
        else:
            self.upgrade_compinfo_size = UPGRADE_COMPINFO_SIZE_L2
            self.header_tlv_type = HEADER_TLV_TYPE_L2

    def verify_param(self):
        if self.head_list is None or self.component_list is None or \
            self.save_path is None or self.key_path is None:
            UPDATE_LOGGER.print_log("Check param failed!", UPDATE_LOGGER.ERROR_LOG)
            return False
        if os.path.isdir(self.key_path):
            UPDATE_LOGGER.print_log("Invalid keyname", UPDATE_LOGGER.ERROR_LOG)
            return False
        if self.head_list.__sizeof__() <= 0 or self.component_list.__sizeof__() <= 0:
            UPDATE_LOGGER.print_log("Invalid param", UPDATE_LOGGER.ERROR_LOG)
            return False
        return True

    def write_pkginfo(self, package_file):
        try:
            # Type is 1 for package header in TLV format
            header_tlv = struct.pack(TLV_FMT, self.header_tlv_type, UPGRADE_PKG_HEADER_SIZE)
            pkg_info_length = \
                UPGRADE_RESERVE_LEN + TLV_SIZE + TLV_SIZE + TLV_SIZE + \
                UPGRADE_PKG_HEADER_SIZE + UPGRADE_PKG_TIME_SIZE + \
                self.upgrade_compinfo_size * self.head_list.entry_count
            upgrade_pkg_header = struct.pack(
                UPGRADE_PKG_HEADER_FMT, pkg_info_length, self.head_list.update_file_version,
                self.head_list.product_update_id, self.head_list.software_version)

            # Type is 2 for time in TLV format
            time_tlv = struct.pack(TLV_FMT, 0x02, UPGRADE_PKG_TIME_SIZE)
            upgrade_pkg_time = struct.pack(
                UPGRADE_PKG_TIME_FMT, self.head_list.date, self.head_list.time)

            # Type is 5 for component in TLV format
            component_tlv = struct.pack(
                TLV_FMT, 0x05, self.upgrade_compinfo_size * self.head_list.entry_count)
        except struct.error:
            UPDATE_LOGGER.print_log("Pack fail!", log_type=UPDATE_LOGGER.ERROR_LOG)
            return False

        # write pkginfo
        pkginfo = header_tlv + upgrade_pkg_header + time_tlv + upgrade_pkg_time + component_tlv
        try:
            package_file.write(pkginfo)
        except IOError:
            UPDATE_LOGGER.print_log("write fail!", log_type=UPDATE_LOGGER.ERROR_LOG)
            return False
        UPDATE_LOGGER.print_log("Write package header complete")
        return True

    def write_component_info(self, component, package_file):
        UPDATE_LOGGER.print_log("component information  StartOffset:%s"\
            % self.compinfo_offset)
        if OPTIONS_MANAGER.not_l2:
            component_addr_size = COMPONEBT_ADDR_SIZE
        else:
            component_addr_size = COMPONEBT_ADDR_SIZE_L2

        try:
            package_file.seek(self.compinfo_offset)
            package_file.write(component.component_addr)
            self.compinfo_offset += component_addr_size

            package_file.seek(self.compinfo_offset)
            component_info = struct.pack(
                COMPONENT_INFO_FMT, component.id, component.res_type,
                component.flags, component.type)
            package_file.write(component_info)
            self.compinfo_offset += COMPONENT_INFO_FMT_SIZE

            package_file.seek(self.compinfo_offset)
            package_file.write(component.version)
            self.compinfo_offset += COMPONENT_VERSION_SIZE

            package_file.seek(self.compinfo_offset)
            component_size = struct.pack(
                COMPONENT_SIZE_FMT, component.size, component.original_size)
            package_file.write(component_size)
            self.compinfo_offset += COMPONENT_SIZE_FMT_SIZE

            package_file.seek(self.compinfo_offset)
            package_file.write(component.digest)
            self.compinfo_offset += COMPONENT_DIGEST_SIZE
        except (struct.error, IOError):
            return False
        return True

    def write_component(self, component, package_file):
        UPDATE_LOGGER.print_log("Add component to package  StartOffset:%s"\
            % self.component_offset)
        try:
            with open(component.file_path, "rb") as component_file:
                component_data = component_file.read()
                package_file.seek(self.component_offset)
                package_file.write(component_data)
                component_len = len(component_data)
                self.component_offset += component_len
        except IOError:
            return False
        UPDATE_LOGGER.print_log("Write component complete  ComponentSize:%s"\
            % component_len)
        return True

    def calculate_hash(self, package_file):
        hash_sha256 = hashlib.sha256()
        remain_len = self.component_offset

        package_file.seek(0)
        while remain_len > BLCOK_SIZE:
            hash_sha256.update(package_file.read(BLCOK_SIZE))
            remain_len -= BLCOK_SIZE
        if remain_len > 0:
            hash_sha256.update(package_file.read(remain_len))
        return hash_sha256.digest()

    def sign_digest_with_pss(self, digset):
        try:
            with open(self.key_path, 'rb') as f_r:
                key_data = f_r.read()
            private_key = serialization.load_pem_private_key(
                key_data,
                password=None,
                backend=default_backend())

            pad = padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH)

            signature = private_key.sign(digset, pad, hashes.SHA256())
        except (OSError, ValueError):
            return False
        return signature

    def sign_digest(self, digset):
        try:
            with open(self.key_path, 'rb') as f_r:
                key_data = f_r.read()
            private_key = serialization.load_pem_private_key(
                key_data,
                password=None,
                backend=default_backend())
            signature = private_key.sign(digset, padding.PKCS1v15(), hashes.SHA256())
        except (OSError, ValueError):
            return False
        return signature

    def sign(self, sign_algo):
        with open(self.save_path, "rb+") as package_file:
            # calculate hash for .bin package
            digest = self.calculate_hash(package_file)
            if not digest:
                UPDATE_LOGGER.print_log("calculate hash for .bin package failed",
                    log_type=UPDATE_LOGGER.ERROR_LOG)
                return False

            # sign .bin package
            if sign_algo == SIGN_ALGO_RSA:
                signature = self.sign_digest(digest)
            elif sign_algo == SIGN_ALGO_PSS:
                signature = self.sign_digest_with_pss(digest)
            else:
                UPDATE_LOGGER.print_log("invalid sign_algo!", log_type=UPDATE_LOGGER.ERROR_LOG)
                return False
            if not signature:
                UPDATE_LOGGER.print_log("sign .bin package failed!", log_type=UPDATE_LOGGER.ERROR_LOG)
                return False

            if len(signature) == SIGN_SHA384_LEN:
                self.sign_offset += SIGN_SHA256_LEN

            # write signed .bin package
            package_file.seek(self.sign_offset)
            package_file.write(signature)
            UPDATE_LOGGER.print_log(
                ".bin package signing success! SignOffset: %s" % self.sign_offset)
            return True

    def create_package(self):
        """
        Create the update.bin file
        return: update package creation result
        """
        if not self.verify_param():
            UPDATE_LOGGER.print_log("verify param failed!", UPDATE_LOGGER.ERROR_LOG)
            return False
        package_fd = os.open(self.save_path, os.O_RDWR | os.O_CREAT, 0o755)
        with os.fdopen(package_fd, "wb+") as package_file:
            # Add information to package
            if not self.write_pkginfo(package_file):
                UPDATE_LOGGER.print_log(
                    "Write pkginfo failed!", log_type=UPDATE_LOGGER.ERROR_LOG)
                return False
            # Add component to package
            self.compinfo_offset = UPGRADE_FILE_HEADER_LEN
            self.component_offset = UPGRADE_FILE_HEADER_LEN + \
                self.head_list.entry_count * self.upgrade_compinfo_size + \
                UPGRADE_RESERVE_LEN + SIGN_SHA256_LEN + SIGN_SHA384_LEN
            for i in range(0, self.head_list.entry_count):
                UPDATE_LOGGER.print_log("Add component %s"
                    % self.component_list[i].component_addr)
                if not self.write_component_info(self.component_list[i], package_file):
                    UPDATE_LOGGER.print_log("write component info failed: %s"
                        % self.component_list[i].component_addr, UPDATE_LOGGER.ERROR_LOG)
                    return False
                if not self.write_component(self.component_list[i], package_file):
                    UPDATE_LOGGER.print_log("write component failed: %s"
                        % self.component_list[i].component_addr, UPDATE_LOGGER.ERROR_LOG)
                    return False
            try:
                # Add descriptPackageId to package
                package_file.seek(self.compinfo_offset)
                package_file.write(self.head_list.describe_package_id)
            except IOError:
                UPDATE_LOGGER.print_log(
                    "Add descriptPackageId failed!", log_type=UPDATE_LOGGER.ERROR_LOG)
                return False
            try:
                # Sign
                self.sign_offset = self.compinfo_offset + UPGRADE_RESERVE_LEN
                package_file.seek(self.sign_offset)
                sign_buffer = bytes(UPGRADE_SIGNATURE_LEN)
                package_file.write(sign_buffer)
            except IOError:
                UPDATE_LOGGER.print_log(
                    "Add Sign failed!", log_type=UPDATE_LOGGER.ERROR_LOG)
                return False
        UPDATE_LOGGER.print_log("Write update package complete")
        return True