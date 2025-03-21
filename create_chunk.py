#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (c) 2024 Hunan OpenValley Digital Industry Development Co., Ltd.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Description : Generate the update.bin chunk info data
"""
import os
import struct
import hashlib
import enum
import tempfile
import zipfile
from log_exception import UPDATE_LOGGER
from utils import OptionsManager
from utils import ZIP_EVENT

CHUNK_LIST_COUNT_SIZE = 4
CHUNK_LIST_SIZE = 8
CHUNK_RESERVE = 244
UPGRADE_CHUNKINFO_SIZE = 256

CHUNK_TLV_FMT = "<HI"
CHUNK_INFO_FMT = "<HI"
CHUNK_DATA_HEADER_FMT = "<HI"
CHUNK_SIGN_HEADER_FMT = '<HI'
CHUNK_DATA_PARTITION_FMT = '<HH'
CHUNK_DATA_CMD_FMT = '<HH'
CHUNK_DATA_DATA_FMT = '<HI'
CHUNK_HASH_HEADER_FMT = '<3H'
CHUNK_HASH_PARTITION_FMT = '<HH'
CHUNK_HASH_VALUE_FMT = '<HH'
CHUNK_LARGE_PARTITION_FMT = '<HH'
CHUNK_SIGN_PARTITON_FMT = "<HH"
CHUNK_SIGN_VALUE_FMT = '<HI'


OPTIONS_MANAGER = OptionsManager()


def get_file_sha256(update_package):
    """
    Get the SHA256 value of the package file
    """
    sha256obj = hashlib.sha256()
    maxbuf = 8192
    with open(update_package, 'rb') as package_file:
        while True:
            buf = package_file.read(maxbuf)
            if not buf:
                break
            sha256obj.update(buf)
    hash_value_hex = sha256obj.hexdigest()
    hash_value = sha256obj.digest()
    return str(hash_value_hex).upper()


def get_chunk_sha256(chunk):
    """
    Get the SHA256 value of the chunk
    """
    sha256obj = hashlib.sha256()
    sha256obj.update(chunk)
    hash_value_hex = sha256obj.hexdigest()
    hash_value = sha256obj.digest()
    return str(hash_value_hex).upper()


class CreateChunk(object):
    """
    Create the image chunk data
    """
    def __init__(self, num, count):
        self.chunkinfo_tlv_type = 0x10
        self.chunkdata_tlv_type = 0x11
        self.chunkdata_partition_tlv_type = 0x12
        self.chunkdata_cmd_tlv_type = 0x13
        self.chunkdata_value_tlv_type = 0x14
        self.chunkhash_tlv_type = 0x15
        self.chunkhash_info_tlv_type = 0x16
        self.chunkhash_partition_tlv_type = 0x17
        self.chunkhash_value_tlve_type = 0x18
        self.chunkimage_large_tlv_type = 0x19
        self.chunksign_value_tlv_type = 0x1a
        
        self.chunk_list_count = count
        self.chunk_list_num = num
        self.chunk_list_length = 0
        self.chunkinfo_value = bytes()
        self.pkg_chunk = bytes()
        self.hash_chunk = bytes()
        self.sign_chunk = bytes()
        self.chunkdata_value = bytes()
        self.chunk_list = []
        self.hash_list = []
        self.sign_list = []
        self.all_image_hash_data = []
        self.write_chunk_hashdata = bytes()
        self.signdata = bytes()

        
    def write_chunkinfo(self, package_file, startoffset):
        UPDATE_LOGGER.print_log("write_chunkinfo Startoffset %s!"\
            % startoffset)
        try:
            chunkinfo_tlv = struct.pack(CHUNK_TLV_FMT, self.chunkinfo_tlv_type, UPGRADE_CHUNKINFO_SIZE)
            chunkinfo_header = struct.pack(CHUNK_INFO_FMT, self.chunk_list_count, self.chunk_list_num)
        except struct.error:
            UPDATE_LOGGER.print_log("Pack fail!", log_type=UPDATE_LOGGER.ERROR_LOG)
            raise RuntimeError
        
        # write chunkinfo
        self.chunkinfo_value = chunkinfo_tlv + chunkinfo_header
        package_file.seek(startoffset)
        package_file.write(self.chunkinfo_value)
        return True

    def write_chunklist(self, image, package_file, startoffset):
        UPDATE_LOGGER.print_log("write pkg chunklist StartOffset:%s"\
            % startoffset)
        try:
            chunk_count = 0
            patch_index = 0
            new_index = 0 
            for chunk in OPTIONS_MANAGER.image_transfer_dict_contents[image].splitlines()[4:]:
                chunk_count += 1
                partiton_info = image
                cmd_info = chunk
                
                # Step 1: Pack partition name        
                partition_tlv = struct.pack(CHUNK_DATA_PARTITION_FMT, self.chunkdata_partition_tlv_type, len(partiton_info)) + partiton_info.encode('utf-8')
                print(f"Packed partition TLV{chunk_count}: {partition_tlv}")
                # Write to binary file
                package_file.seek(startoffset)
                package_file.write(partition_tlv)
                startoffset += len(partition_tlv)
            
                # Step 2: Pack command info 
                cmd_len = len(cmd_info)
                cmd_tlv = struct.pack(CHUNK_DATA_CMD_FMT, self.chunkdata_cmd_tlv_type, cmd_len) + cmd_info.encode('utf-8')
                print(f"Packed command TLV{chunk_count}: {cmd_tlv}")
                print(f'length:{cmd_len}')
                # Write to binary file
                package_file.seek(startoffset)
                package_file.write(cmd_tlv)
                startoffset += len(cmd_tlv)
                
                # Step 3: Pack patch dependency data
                data_tlv, patch_index, new_index = self.pack_dependency_data(image, cmd_info, chunk, patch_index, new_index)
                # Write to bin file 
                data_len = len(data_tlv)
                package_file.seek(startoffset)
                package_file.write(data_tlv)
                startoffset += data_len
            
        except (struct.error) as e:
            UPDATE_LOGGER.print_log(f"Unexpected error: {e}", log_type=UPDATE_LOGGER.ERROR_LOG)
            UPDATE_LOGGER.print_log("write chunk error!", log_type=UPDATE_LOGGER.ERROR_LOG)
            raise RuntimeError
        except Exception as e:
            UPDATE_LOGGER.print_log(f"An unexpected error occurred: {e}", log_type=UPDATE_LOGGER.ERROR_LOG)
            UPDATE_LOGGER.print_log("write chunklist complete", log_type=UPDATE_LOGGER.ERROR_LOG)
            raise RuntimeError
        
        return startoffset
    
    def write_hash_info(self, image_number, package_file, startoffset):
        UPDATE_LOGGER.print_log("write image hash info StartOffset:%s"\
            % startoffset)
        try:
            # pack hash info head
            hash_info_tlv = struct.pack(CHUNK_HASH_HEADER_FMT, 
                                        self.chunkhash_info_tlv_type, 
                                        2, image_number)
            # Write to bin file
            package_file.seek(startoffset)
            package_file.write(hash_info_tlv)
            startoffset += len(hash_info_tlv)
            
            print(f"Packed image name TLV: {hash_info_tlv}")
            
        except struct.error:
            UPDATE_LOGGER.print_log("Pack fail!", log_type=UPDATE_LOGGER.ERROR_LOG)
            raise RuntimeError
        
        return startoffset  
        
    
    def write_image_hashdata(self, image_file, package_file, startoffset):
        UPDATE_LOGGER.print_log("write image hash StartOffset:%s"\
            % startoffset)
        try:
            # Step 1: Pack hash partition name
            image_name_tlv = struct.pack(CHUNK_HASH_PARTITION_FMT,
                                         self.chunkhash_partition_tlv_type, 
                                         len(image_file)) + image_file.encode('utf-8')
            partition_len = len(image_name_tlv)
            # Write to bin file
            package_file.seek(startoffset)
            package_file.write(image_name_tlv)
            startoffset += partition_len
            
            print(f"Packed image name TLV: {image_name_tlv}")
            
            # Step 2: Pack target partition hash value
            each_image_file = os.path.join(
                OPTIONS_MANAGER.target_package_dir,
                '%s.img' % image_file)
            image_hash_data = get_file_sha256(each_image_file)
            image_hash_tlv = struct.pack(CHUNK_HASH_VALUE_FMT, 
                                         self.chunkhash_value_tlve_type,
                                         len(image_hash_data)) + image_hash_data.lower().encode('utf-8')
            image_hash_data_len = len(image_hash_tlv)
            print(f'hash data:{image_hash_data.lower}')
            # Write to bin file
            package_file.seek(startoffset)
            package_file.write(image_hash_tlv)
            startoffset += image_hash_data_len
            
            print(f"Packed hash data TLV: {image_hash_tlv}")
            
        except struct.error:
            UPDATE_LOGGER.print_log("Pack fail!", log_type=UPDATE_LOGGER.ERROR_LOG)
            raise RuntimeError
        return startoffset
      
    def write_image_large(self, image_file, package_file, startoffset):
        UPDATE_LOGGER.print_log("write image large StartOffset:%s"\
            % startoffset)
        try:
            if OPTIONS_MANAGER.full_img_list:
                image_length = len(OPTIONS_MANAGER.full_image_new_data[image_file])
            else:
                image_length = len(OPTIONS_MANAGER.diff_image_new_data[image_file])
            # Step 1: Pack hash partition name
            image_large_tlv = struct.pack(CHUNK_LARGE_PARTITION_FMT,
                                         self.chunkimage_large_tlv_type,
                                         8) + image_length.to_bytes(8, byteorder='little')
            partition_large_len = len(image_large_tlv)
            # Write to bin file
            package_file.seek(startoffset)
            package_file.write(image_large_tlv)
            startoffset += partition_large_len

            print(f"Packed image large TLV: {image_large_tlv}")
            
        except struct.error:
            UPDATE_LOGGER.print_log("Pack fail!", log_type=UPDATE_LOGGER.ERROR_LOG)
            raise RuntimeError    
        return startoffset
    
    def write_all_image_signdata(self, signdata):
        try:
            signdata_len = len(signdata)
            signdata_tlv = struct.pack(CHUNK_SIGN_VALUE_FMT, 
                                       self.chunksign_value_tlv_type, 
                                       signdata_len)
        except struct.error:
            UPDATE_LOGGER.print_log("Pack fail!", log_type=UPDATE_LOGGER.ERROR_LOG)
            raise RuntimeError

        # write signdata
        self.signdata = signdata_tlv + signdata
        UPDATE_LOGGER.print_log("Write hashdata sign tlv complete") 
        return True
    
    def write_chunklist_full_image(self, image_name, package_file, chunks, block_sets, startoffset):
        try:
            UPDATE_LOGGER.print_log("write chunk StartOffset:%s"\
            % startoffset)
            
            chunk_index = 0
            for chunk in chunks:
                # Step 1: Pack partition name
                partition_tlv = struct.pack(CHUNK_DATA_PARTITION_FMT, 
                                            self.chunkdata_partition_tlv_type, 
                                            len(image_name)) + image_name.encode()
                # Write to binary file
                package_file.seek(startoffset)
                package_file.write(partition_tlv)
                startoffset += len(partition_tlv)
                
                # Step 2: Pack command info
                cmd_str = ("%s %s %d,%s,%s" % ("new", get_chunk_sha256(chunk), 2,
                                        min(block_sets[chunk_index]), 
                                        max(block_sets[chunk_index]) + 1))
                cmd_tlv = struct.pack(CHUNK_DATA_CMD_FMT, 
                                      self.chunkdata_cmd_tlv_type, 
                                      len(cmd_str)) + cmd_str.encode()
                # Write to binary file
                package_file.seek(startoffset)
                package_file.write(cmd_tlv)
                startoffset += len(cmd_tlv)
                
                # Step 3: Pack the sliced image data
                data_tlv = struct.pack(CHUNK_DATA_DATA_FMT, 
                                       self.chunkdata_value_tlv_type, 
                                       len(chunk)) + chunk
                # Write to binary file
                package_file.seek(startoffset)
                package_file.write(data_tlv)
                startoffset += len(data_tlv)
                chunk_index += 1
        except struct.error:
            UPDATE_LOGGER.print_log("Pack fail!", log_type=UPDATE_LOGGER.ERROR_LOG)
            raise RuntimeError
        
        return startoffset
    
    def pack_dependency_data(self, image, cmd_info, chunk, patch_index, new_index):
        if "pkgdiff" in cmd_info:
            if OPTIONS_MANAGER.image_patch_dic[image]:
                data_value = OPTIONS_MANAGER.image_patch_dic[image][patch_index]
                if not data_value:
                    UPDATE_LOGGER.print_log("data_value is empty, using chunk instead.", 
                                            log_type=UPDATE_LOGGER.INFO_LOG)
                    data_value = chunk
                    data_tlv = struct.pack(CHUNK_DATA_DATA_FMT, 
                                            self.chunkdata_value_tlv_type, 
                                            len(data_value)) + data_value.encode('utf-8')
                    patch_index += 1 
                data_tlv = struct.pack(CHUNK_DATA_DATA_FMT, 
                                        self.chunkdata_value_tlv_type, 
                                        len(data_value)) + data_value
                patch_index += 1
            else:
                data_value = chunk
                UPDATE_LOGGER.print_log("patch.data is empty!", log_type=UPDATE_LOGGER.ERROR_LOG)
                raise RuntimeError
            # Determine if the line in transfer.list contains new, if it does, take new.data with it.
        elif "new" in cmd_info:
            if OPTIONS_MANAGER.image_new_dic[image]:
                data_value = OPTIONS_MANAGER.image_new_dic[image][new_index]
                if not data_value:
                    UPDATE_LOGGER.print_log("data_value is empty, using chunk instead.", 
                                            log_type=UPDATE_LOGGER.INFO_LOG)
                    data_value = chunk
                    data_tlv = struct.pack(CHUNK_DATA_DATA_FMT, 
                                            self.chunkdata_value_tlv_type, 
                                            len(data_value)) + data_value.encode('utf-8')
                    new_index += 1
                data_tlv = struct.pack(CHUNK_DATA_DATA_FMT, 
                                        self.chunkdata_value_tlv_type, 
                                        len(data_value)) + data_value
                new_index += 1
            else: 
                data_value = chunk 
                UPDATE_LOGGER.print_log("new.data is empty!", log_type=UPDATE_LOGGER.ERROR_LOG)
                raise RuntimeError
        else:
            # If none of the above instructions are met, put 0 in data_value
            data_value = b''
            data_tlv = struct.pack(CHUNK_DATA_DATA_FMT, 
                                    self.chunkdata_value_tlv_type, 0) + data_value
        return data_tlv, patch_index, new_index
        
    
    