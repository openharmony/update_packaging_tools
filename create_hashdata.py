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
Description : Generate the update.bin hash check data
"""
import os
import struct
import hashlib
import enum
from log_exception import UPDATE_LOGGER

# hash data sample
# hash info module:
# hash info:1 32 3 4194304
# hash value module:
# /version_list                   (32bytes)
# 1 176
# 1 176 bf10259a1fc1b2f780a49ce6XXXXXXXX
# hash sign module:
# hash sign:45ef8ec12e56e3b82c9a05XXXXXX

HashType = enum.Enum('HashType', ('SHA256', 'SHA384', 'SHA512'))
HashAlgo = {HashType.SHA256 : hashlib.sha256,
            HashType.SHA384 : hashlib.sha384,
            HashType.SHA512 : hashlib.sha512}
HASH_TYPE_SIZE = 2
HASH_LENGTH_SIZE = 4
HASH_TLV_SIZE = HASH_TYPE_SIZE + HASH_LENGTH_SIZE
UPGRADE_HASHINFO_SIZE = 10
HASH_DATA_HEADER_SIZE = 38
HASH_DATA_ADDR_SIZE = 8
COMPONENT_NAME_SIZE = 32
# hash block size
HASH_BLOCK_SIZE = 4 * 1024 * 1024

"""
Format
H: unsigned short
I: unsigned int
B: unsigned char
s: char[]
"""
HASH_TLV_FMT = "<HI"
HASH_INFO_FMT = "<3HI"
HASH_DATA_HEADER_FMT = "<32sHI"
HASH_DATA_ADDR_FMT = "<2I"


class CreateHash(object):
    """
    Create the component hash data
    """

    def __init__(self, hash_type, count):
        self.hashinfo_tlv_type = 0x06
        self.hashdata_tlv_type = 0x07
        self.sign_tlv_type = 0x08
        self.hash_type = hash_type
        self.hash_digest_size = HashAlgo[hash_type]().digest_size
        self.component_num = count
        self.block_size = HASH_BLOCK_SIZE
        self.hashinfo_value = bytes()
        self.hashdata = bytes()
        self.signdata = bytes()
        self.hashdata_list = []

    def write_hashinfo(self):
        try:
            hashinfo_tlv = struct.pack(HASH_TLV_FMT, self.hashinfo_tlv_type, UPGRADE_HASHINFO_SIZE)
            hashinfo_header = struct.pack(HASH_INFO_FMT, self.hash_type.value, self.hash_digest_size,
                self.component_num, self.block_size)
        except struct.error:
            UPDATE_LOGGER.print_log("Pack fail!", log_type=UPDATE_LOGGER.ERROR_LOG)
            return False

        # write hashinfo
        self.hashinfo_value = hashinfo_tlv + hashinfo_header
        return True

    def write_hashdata(self):
        try:
            hashdata_len = len(self.hashdata)
            hashdata_tlv = struct.pack(HASH_TLV_FMT, self.hashdata_tlv_type, hashdata_len)
        except struct.error:
            UPDATE_LOGGER.print_log("Pack fail!", log_type=UPDATE_LOGGER.ERROR_LOG)
            return False

        UPDATE_LOGGER.print_log("Write hashdata hash len %d" % hashdata_len)
        # write hashdata
        self.hashdata = hashdata_tlv + self.hashdata
        UPDATE_LOGGER.print_log("Write hashdata hash tlv complete")
        return True

    def write_signdata(self, signdata):
        try:
            signdata_len = len(signdata)
            signdata_tlv = struct.pack(HASH_TLV_FMT, self.sign_tlv_type, signdata_len)
        except struct.error:
            UPDATE_LOGGER.print_log("Pack fail!", log_type=UPDATE_LOGGER.ERROR_LOG)
            return False

        # write signdata
        self.signdata = signdata_tlv + signdata
        UPDATE_LOGGER.print_log("Write hashdata sign tlv complete")
        return True

    def calculate_hash_data(self, data):
        hash_algo = HashAlgo[self.hash_type]()
        hash_algo.update(data)
        return hash_algo.digest()

    def write_component_hash_data(self, component):
        UPDATE_LOGGER.print_log("calc component hash")
        try:
            with open(component.file_path, "rb") as component_file:
                component_len = os.path.getsize(component.file_path)
                block_num = component_len // HASH_BLOCK_SIZE
                component_name = component.component_addr.decode().ljust(COMPONENT_NAME_SIZE, "\0")
                UPDATE_LOGGER.print_log("calc component hash  component name:%s %d" % (component_name, len(component_name)))
                total_block = block_num + 1 if component_len % HASH_BLOCK_SIZE > 0 else block_num
                self.hashdata += struct.pack(HASH_DATA_HEADER_FMT, component_name.encode(),
                    total_block, component_len)
                UPDATE_LOGGER.print_log("calc component hash  block_num:%d" % total_block)
                write_len = 0
                for i in range(0, block_num):
                    component_file.seek(write_len)
                    component_data = component_file.read(HASH_BLOCK_SIZE)
                    write_len += HASH_BLOCK_SIZE
                    self.hashdata += struct.pack(HASH_DATA_ADDR_FMT, (i * HASH_BLOCK_SIZE if i != 0 else 0),
                        write_len - 1) + self.calculate_hash_data(component_data)
                if component_len - write_len > 0 :
                    component_file.seek(write_len)
                    component_data = component_file.read(component_len - write_len)
                    self.hashdata += struct.pack(HASH_DATA_ADDR_FMT, (write_len if write_len != 0 else 0),
                        component_len - 1) + self.calculate_hash_data(component_data)
        except (struct.error, IOError):
            return False
        UPDATE_LOGGER.print_log("calc component hash complete  ComponentSize:%d" % component_len)
        return True

    def parse_hashinfo(self, data):
        # parse hashinfo
        hash_type_value = 0
        try:
            hash_type_value, self.hash_digest_size, self.component_num, self.block_size = \
                struct.unpack(HASH_INFO_FMT, data[:UPGRADE_HASHINFO_SIZE])
            self.hash_type = HashType(hash_type_value)
        except struct.error:
            return False

        UPDATE_LOGGER.print_log("parese hashinfo complete, %d %d %d %d" % (hash_type_value,
            self.hash_digest_size, self.component_num, self.block_size))
        return True

    def parse_hashdata(self, data):
        offset = 0
        try:
            for i in range(0, self.component_num):
                img_name, hash_num, img_size = struct.unpack(HASH_DATA_HEADER_FMT,
                    data[offset: HASH_DATA_HEADER_SIZE + offset])
                UPDATE_LOGGER.print_log("parese hashinfo complete, %s %d %d" % (img_name,
                    hash_num, img_size))
                offset += HASH_DATA_HEADER_SIZE
                self.hashdata_list.append((img_name.decode(), hash_num, img_size))
                for j in range(0, hash_num):
                    hash_data_star, hash_data_end = struct.unpack(HASH_DATA_ADDR_FMT,
                        data[offset: HASH_DATA_ADDR_SIZE + offset])
                    hash_data = data[HASH_DATA_ADDR_SIZE + offset:HASH_DATA_ADDR_SIZE + self.hash_digest_size + offset]
                    offset += (HASH_DATA_ADDR_SIZE + self.hash_digest_size)
                    self.hashdata_list.append((hash_data_star, hash_data_end, hash_data))
        except struct.error:
            return False

        UPDATE_LOGGER.print_log("parese hashdata complete")
        return True

    def parse_signdata(self, data):
        # parse signdata
        self.signdata = data
        UPDATE_LOGGER.print_log("parese hashdata sign complete")
        return True

    def parse_print_hashdata(self, save_path):
        hash_check_file_p = open(os.path.join(save_path + "hash_check_file_parse"), "wb+")
        hash_check_file_p.write(("hash info:").encode())
        hash_check_file_p.write((HashType(self.hash_type.value).name + ' ' + str(self.hash_digest_size) + \
            ' ' + str(self.component_num) + ' ' + str(self.block_size) + '\n').encode())

        offset = 0
        for i in range(0, self.component_num):
            hash_check_file_p.write((self.hashdata_list[offset][0] + '\n').encode())
            hash_check_file_p.write((str(self.hashdata_list[offset][1]) + ' ' + \
                str(self.hashdata_list[offset][2]) + '\n').encode())
            for j in range(0, self.hashdata_list[offset][1]):
                index = offset + 1
                hashdata_hexstr = "".join("%02x" % b for b in self.hashdata_list[j + index][2])
                hash_check_file_p.write((str(self.hashdata_list[j + index][0]) + ' ' + \
                    str(self.hashdata_list[j + index][1]) + ' ' + hashdata_hexstr + \
                    '\n').encode())
            offset += (1 + self.hashdata_list[offset][1])

        signdata_hexstr = "".join("%02x" % b for b in self.signdata)
        hash_check_file_p.write(("hash sign:").encode())
        hash_check_file_p.write(signdata_hexstr.encode())
        hash_check_file_p.close()