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
from create_hashdata import HashType
from create_hashdata import CreateHash
from create_hashdata import HASH_BLOCK_SIZE
from create_chunk import CreateChunk
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
COMPONENT_ADDR_SIZE = 16
COMPONENT_ADDR_SIZE_L2 = 32
COMPONENT_INFO_FMT_SIZE = 5
COMPONENT_VERSION_SIZE = 10
COMPONENT_SIZE_FMT_SIZE = 8
COMPONENT_DIGEST_SIZE = 32
BLOCK_SIZE = 8192
HEADER_TLV_TYPE = 0x11
HEADER_TLV_TYPE_L2 = 0x01
ZIP_TLV_TYPE = 0xaa
# signature algorithm
SIGN_ALGO_RSA = "SHA256withRSA"
SIGN_ALGO_PSS = "SHA256withPSS"
# chunkdata offset
CHUNK_INFO_OFFSET = 262

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
        self.hash_info_offset = 0
        self.chunk_info_offset = 0
        self.chunk_data_offset = 0
        self.hash_write_start_offset = 0
        self.hash_write_end_offset = 0
        self.chunk_hash_offset = 0
        self.chunk_sign_offset = 0

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
    
    def write_update_zip(self, package_file):
        try:
            build_tools_zip_path = OPTIONS_MANAGER.signed_package
            UPDATE_LOGGER.print_log("build_tools_zip_path = %s" % build_tools_zip_path, UPDATE_LOGGER.ERROR_LOG)
            with open(build_tools_zip_path, 'rb') as f:
                value_data = f.read()
            value_length = len(value_data)
            tlv_header = struct.pack('<HI', ZIP_TLV_TYPE, value_length)
            package_file.write(tlv_header)
            package_file.write(value_data)
            UPDATE_LOGGER.print_log(
            f"Successfully wrote build_tools.zip (Type={ZIP_TLV_TYPE}, Length={value_length} bytes)",
            UPDATE_LOGGER.INFO_LOG
            )
            
            offset = len(tlv_header) + len(value_data)
        
        except Exception as e:
            UPDATE_LOGGER.print_log(
                f"Failed to write build_tools.zip: {str(e)}",
                UPDATE_LOGGER.ERROR_LOG
            )
            raise RuntimeError
        
        return offset
        
    def write_pkginfo(self, package_file, offset):
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
            package_file.seek(offset)
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
            component_addr_size = COMPONENT_ADDR_SIZE
        else:
            component_addr_size = COMPONENT_ADDR_SIZE_L2

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
        while remain_len > BLOCK_SIZE:
            hash_sha256.update(package_file.read(BLOCK_SIZE))
            remain_len -= BLOCK_SIZE
        if remain_len > 0:
            hash_sha256.update(package_file.read(remain_len))
        return hash_sha256.digest()

    def calculate_header_hash(self, package_file):
        hash_sha256 = hashlib.sha256()
        remain_len = self.hash_info_offset
        package_file.seek(OPTIONS_MANAGER.zip_offset)
        while remain_len > BLOCK_SIZE:
            hash_sha256.update(package_file.read(BLOCK_SIZE))
            remain_len -= BLOCK_SIZE
        if remain_len > 0:
            hash_sha256.update(package_file.read(remain_len))
        return hash_sha256.digest()

    def sign_digest_with_pss(self, digest):
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

            signature = private_key.sign(digest, pad, hashes.SHA256())
        except (OSError, ValueError):
            return False
        return signature

    def sign_digest(self, digest):
        try:
            with open(self.key_path, 'rb') as f_r:
                key_data = f_r.read()
            private_key = serialization.load_pem_private_key(
                key_data,
                password=None,
                backend=default_backend())
            signature = private_key.sign(digest, padding.PKCS1v15(), hashes.SHA256())
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

    def sign_header(self, sign_algo, hash_check_data, package_file):
        # calculate hash for .bin package
        digest = self.calculate_header_hash(package_file)
        if not digest:
            UPDATE_LOGGER.print_log("calculate hash for .bin package failed",
                log_type=UPDATE_LOGGER.ERROR_LOG)
            return False

        # sign .bin header
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

        # write signed .bin header
        hash_check_data.write_signdata(signature)
        package_file.seek(self.hash_info_offset)
        package_file.write(hash_check_data.signdata)
        self.hash_info_offset += len(hash_check_data.signdata)
        UPDATE_LOGGER.print_log(
            ".bin package header signing success! SignOffset: %s" % self.hash_info_offset)
        return True
        
    def calculate_hash_all_image(self, package_file):
        """
        Calculate the SHA-256 hash for a specified range of data in the package file.
        :param package_file: The file object representing the package from which to calculate the hash.
        :return: The SHA-256 hash digest of the specified data range.
        """
        hash_sha256 = hashlib.sha256()
        # 计算的hash从hash info head开始
        remain_len = self.hash_write_end_offset - self.hash_write_start_offset + 1
        print(f'remain_len:{remain_len}')
        package_file.seek(self.hash_write_start_offset)
        while remain_len > BLOCK_SIZE:
            hash_sha256.update(package_file.read(BLOCK_SIZE))
            remain_len -= BLOCK_SIZE
        if remain_len > 0:
            hash_sha256.update(package_file.read(remain_len))
        return hash_sha256.digest()
    
    def sign_all_imgae_hash(self, sign_algo, hash_check_data, package_file):
        """
        Sign the hash of all images using the specified signing algorithm.
        :param sign_algo: The signing algorithm to use (e.g., RSA or PSS).
        :param hash_check_data: An object that holds hash check data and methods to write signature data.
        :param package_file: The file object representing the package where the signature will be written.
        :return: True if signing is successful, False otherwise.
        """
        digest = self.calculate_hash_all_image(package_file)
        if not digest:
            UPDATE_LOGGER.print_log("calculate hash for all image hash failed",
                log_type=UPDATE_LOGGER.ERROR_LOG)
            return False

        # sign all image hash
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
        print(f'write signature:{signature}')
        # 所有镜像hash（包括hash info head）的sign打包封装
        hash_check_data.write_all_image_signdata(signature)
        UPDATE_LOGGER.print_log(
            "start write full image sign offset: %s" % self.chunk_sign_offset)
        package_file.seek(self.chunk_sign_offset)
        package_file.write(hash_check_data.signdata)
        self.chunk_sign_offset += len(hash_check_data.signdata)
        UPDATE_LOGGER.print_log(
            ".bin package header signing success! SignOffset: %s" % self.chunk_sign_offset)
        return True
    
    def handle_stream_update(self, package_file):
        # Incremental streaming update
        if OPTIONS_MANAGER.stream_update and OPTIONS_MANAGER.incremental_img_list:
            try: 
                self.create_incremental_package(package_file)
                UPDATE_LOGGER.print_log("Write incremental streaming update chunk complete!",
                                        log_type=UPDATE_LOGGER.INFO_LOG)
                    
            except IOError:
                UPDATE_LOGGER.print_log("Add Chunk data info failed!", log_type=UPDATE_LOGGER.ERROR_LOG)
                return False
            
        # Full streaming update
        if OPTIONS_MANAGER.stream_update and len(OPTIONS_MANAGER.full_img_list):
            try: 
                self.create_full_package(package_file)
                UPDATE_LOGGER.print_log("Write full streaming update chunk complete!",
                                        log_type=UPDATE_LOGGER.INFO_LOG)
                    
            except IOError:
                UPDATE_LOGGER.print_log("Add Chunk data info failed!", log_type=UPDATE_LOGGER.ERROR_LOG)
                return False
            
        return True
        
    def create_package(self):
        """
        Create the update.bin file
        return: update package creation result
        """
        if not self.verify_param():
            UPDATE_LOGGER.print_log("verify param failed!", UPDATE_LOGGER.ERROR_LOG)
            return False

        hash_check_data = CreateHash(HashType.SHA256, self.head_list.entry_count)
        hash_check_data.write_hashinfo()
        UPDATE_LOGGER.print_log("self.save_path: %s"
                        % self.save_path, UPDATE_LOGGER.INFO_LOG)
        package_fd = os.open(self.save_path, os.O_RDWR | os.O_CREAT, 0o755)
        with os.fdopen(package_fd, "wb+") as package_file:
            # 如果为流式升级，将zip嵌入到update_bin
            if OPTIONS_MANAGER.stream_update:
                zip_file_offset = self.write_update_zip(package_file)
            else:
                zip_file_offset = 0     
            OPTIONS_MANAGER.zip_offset = zip_file_offset
            # Add information to package
            if not self.write_pkginfo(package_file, zip_file_offset):
                UPDATE_LOGGER.print_log("Write pkginfo failed!", log_type=UPDATE_LOGGER.ERROR_LOG)
                return False
            # Add component to package
            self.compinfo_offset = UPGRADE_FILE_HEADER_LEN + zip_file_offset
            UPDATE_LOGGER.print_log("self.compinfo_offset: %s"
                        % self.compinfo_offset, UPDATE_LOGGER.INFO_LOG)
            self.component_offset = UPGRADE_FILE_HEADER_LEN + \
                self.head_list.entry_count * self.upgrade_compinfo_size + \
                UPGRADE_RESERVE_LEN + SIGN_SHA256_LEN + SIGN_SHA384_LEN
            for i in range(0, self.head_list.entry_count):
                UPDATE_LOGGER.print_log("Add component %s" % self.component_list[i].component_addr)
                if not self.write_component_info(self.component_list[i], package_file):
                    UPDATE_LOGGER.print_log("write component info failed: %s"
                        % self.component_list[i].component_addr, UPDATE_LOGGER.ERROR_LOG)
                    return False
                if OPTIONS_MANAGER.sd_card and (not hash_check_data.write_component_hash_data(self.component_list[i])):
                    UPDATE_LOGGER.print_log("write component hash data failed: %s"
                        % self.component_list[i].component_addr, UPDATE_LOGGER.ERROR_LOG)
                    return False

            try:
                # Add descriptPackageId to package
                package_file.seek(self.compinfo_offset)
                package_file.write(
                    (self.head_list.describe_package_id.decode().ljust(UPGRADE_RESERVE_LEN, "\0")).encode())
            except IOError:
                UPDATE_LOGGER.print_log("Add descriptPackageId failed!", log_type=UPDATE_LOGGER.ERROR_LOG)
                return False
            self.hash_info_offset = self.compinfo_offset + UPGRADE_RESERVE_LEN
            if OPTIONS_MANAGER.sd_card:
                try:
                    # Add hash check data to package
                    hash_check_data.write_hashdata()
                    package_file.seek(self.hash_info_offset)
                    package_file.write(hash_check_data.hashinfo_value + hash_check_data.hashdata)
                    self.hash_info_offset += len(hash_check_data.hashinfo_value + hash_check_data.hashdata)

                except IOError:
                    UPDATE_LOGGER.print_log("Add hash check data failed!", log_type=UPDATE_LOGGER.ERROR_LOG)
                    return False
            self.sign_header(SIGN_ALGO_RSA, hash_check_data, package_file)
            self.component_offset = self.hash_info_offset
            if not OPTIONS_MANAGER.stream_update:
                if not self.write_component_list(package_file):
                    return False
            self.chunk_info_offset = self.component_offset  
            
            if not self.handle_stream_update(package_file):
                UPDATE_LOGGER.print_log("Handle stream update failed!", log_type=UPDATE_LOGGER.ERROR_LOG)
                return False
            
        return True
    
    def write_component_list(self, package_file):
        """
        Write components to the package file.

        :param package_file: The file object to write components to.
        :return: Boolean indicating success or failure.
        """
        for i in range(0, self.head_list.entry_count):
            if not self.write_component(self.component_list[i], package_file):
                UPDATE_LOGGER.print_log("write component failed: %s"
                                        % self.component_list[i].component_addr, 
                                        UPDATE_LOGGER.ERROR_LOG)
                return False
        return True
        
    def create_incremental_package(self, package_file):
        """
        Create the incremental update.bin file
        return: incremental update package creation result
        """
        chunk_check_data = CreateChunk(1, 1)    
        # Adding chunk list of pkg chunks
        # Determine if a no_map file exists
        if OPTIONS_MANAGER.no_map_image_exist:
            UPDATE_LOGGER.print_log("OPTIONS_MANAGER.no_map_file_list:%s" % OPTIONS_MANAGER.no_map_file_list,
                                    log_type=UPDATE_LOGGER.INFO_LOG)
            self.chunk_data_offset = self.chunk_info_offset
            # Add the no map mirror chunk command
            for each_image in OPTIONS_MANAGER.no_map_file_list:
                self.chunk_data_offset = chunk_check_data.write_chunklist_full_image(each_image, package_file,
                                                            OPTIONS_MANAGER.image_chunk[each_image],
                                                            OPTIONS_MANAGER.image_block_sets[each_image],
                                                            self.chunk_data_offset)
                UPDATE_LOGGER.print_log("write pkg no map chunk partition name is %s" % each_image,
                                        log_type=UPDATE_LOGGER.INFO_LOG)
        else:
            self.chunk_data_offset = self.chunk_info_offset
            
        # Remove no map file list element
        reduce_no_map_list = [item for item in OPTIONS_MANAGER.incremental_img_list 
                                if item not in OPTIONS_MANAGER.no_map_file_list]
        for each_image in reduce_no_map_list:
            print(f'each_image_name:{each_image}')
            UPDATE_LOGGER.print_log("write pkg chunk partition name is %s" % each_image, log_type=UPDATE_LOGGER.INFO_LOG)
            self.chunk_data_offset = chunk_check_data.write_chunklist(each_image, package_file, self.chunk_data_offset)
        self.chunk_hash_offset = self.chunk_data_offset
        
        # Record where the hash starts writing
        self.hash_write_start_offset = self.chunk_hash_offset
        
        # Add the hash info header
        image_number = len(OPTIONS_MANAGER.incremental_img_list)
        self.chunk_hash_offset = chunk_check_data.write_hash_info(image_number, package_file, self.chunk_hash_offset)
        
        # Add hash for each image and the large data
        for each_image in OPTIONS_MANAGER.incremental_img_list:
            self.chunk_hash_offset = chunk_check_data.write_image_hashdata(each_image, package_file, self.chunk_hash_offset)
            UPDATE_LOGGER.print_log("write image hashdata complete!", log_type=UPDATE_LOGGER.INFO_LOG)
            self.chunk_hash_offset = chunk_check_data.write_image_large(each_image, package_file, self.chunk_hash_offset)
            UPDATE_LOGGER.print_log("write image large complete!", log_type=UPDATE_LOGGER.INFO_LOG)
        self.chunk_sign_offset = self.chunk_hash_offset
        
        # Record the location of the end-of-hash write
        self.hash_write_end_offset = self.chunk_sign_offset
        
        # Add the sign of the encapsulated hash for all images
        self.sign_all_imgae_hash(SIGN_ALGO_RSA, chunk_check_data, package_file)
        
    def create_full_package(self, package_file):
        """
        Create the full update.bin file
        return: full update package creation result
        """
        chunk_check_data = CreateChunk(1, 1)
        # Adding chunk list of pkg chunks
        for each_img_name in OPTIONS_MANAGER.full_img_name_list:
            each_img = each_img_name[:-4]
            self.chunk_info_offset = chunk_check_data.write_chunklist_full_image(each_img, package_file, 
                                                                                    OPTIONS_MANAGER.full_chunk[each_img],
                                                                                    OPTIONS_MANAGER.full_block_sets[each_img],
                                                                                    self.chunk_info_offset)
            UPDATE_LOGGER.print_log("Write full streaming update [%s] chunk complete!" % each_img, 
                                    log_type=UPDATE_LOGGER.INFO_LOG)   
        self.chunk_hash_offset = self.chunk_info_offset          
        
        # Record where the hash starts writing
        self.hash_write_start_offset = self.chunk_hash_offset
        
        # Add the hash info header
        image_number = len(OPTIONS_MANAGER.full_img_name_list)
        self.chunk_hash_offset = chunk_check_data.write_hash_info(image_number, package_file, self.chunk_hash_offset)
            
        # Add hash for each image and the large data
        for each_image_name in OPTIONS_MANAGER.full_img_name_list:
            each_img = os.path.splitext(each_image_name)[0]
            self.chunk_hash_offset = chunk_check_data.write_image_hashdata(each_img, package_file, self.chunk_hash_offset)
            UPDATE_LOGGER.print_log("write image hashdata complete!", log_type=UPDATE_LOGGER.INFO_LOG)
            self.chunk_hash_offset = chunk_check_data.write_image_large(each_img, package_file, self.chunk_hash_offset)
            UPDATE_LOGGER.print_log("write image large complete!", log_type=UPDATE_LOGGER.INFO_LOG)
        self.chunk_sign_offset = self.chunk_hash_offset
        
        # Record the location of the end-of-hash write
        self.hash_write_end_offset = self.chunk_sign_offset
        
        # Add the sign of the encapsulated hash for all images
        self.sign_all_imgae_hash(SIGN_ALGO_RSA, chunk_check_data, package_file)