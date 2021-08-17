#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2021 Huawei Device Co., Ltd.
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
import bisect
import copy
import os
import struct
import tempfile
from hashlib import sha256

from log_exception import UPDATE_LOGGER
from blocks_manager import BlocksManager
from utils import SPARSE_IMAGE_MAGIC
from utils import HEADER_INFO_FORMAT
from utils import HEADER_INFO_LEN
from utils import EXTEND_VALUE
from utils import FILE_MAP_ZERO_KEY
from utils import FILE_MAP_NONZERO_KEY
from utils import FILE_MAP_COPY_KEY
from utils import MAX_BLOCKS_PER_GROUP


class FullUpdateImage:
    """
    Full image processing class
    """

    def __init__(self, target_package_images_dir, full_img_list, verse_script,
                 full_image_path_list, no_zip=False):
        self.__target_package_images_dir = target_package_images_dir
        self.__full_img_list = full_img_list
        self.__verse_script = verse_script
        self.__full_image_path_list = full_image_path_list
        self.__no_zip = no_zip

    def update_full_image(self):
        """
        Processing of the full image
        :return full_image_content_len_list: full image content length list
        :return full_image_file_obj_list: full image temporary file list
        """
        full_image_file_obj_list = []
        full_image_content_len_list = []
        for idx, each_name in enumerate(self.__full_img_list):
            full_image_content = self.get_full_image_content(
                self.__full_image_path_list[idx])
            if full_image_content is False:
                UPDATE_LOGGER.print_log(
                    "Get full image content failed!",
                    log_type=UPDATE_LOGGER.ERROR_LOG)
                return False, False
            each_img = tempfile.NamedTemporaryFile(
                prefix="full_image%s" % each_name, mode='wb')
            each_img.write(full_image_content)
            each_img.seek(0)
            full_image_content_len_list.append(len(full_image_content))
            full_image_file_obj_list.append(each_img)
            UPDATE_LOGGER.print_log(
                "Image %s full processing completed" % each_name)
            if not self.__no_zip:
                # No zip mode (no script command)
                if is_sparse_image(each_img.name):
                    sparse_image_write_cmd = \
                        self.__verse_script.sparse_image_write(each_name)
                    cmd = '%s_WRITE_FLAG%s' % (
                        each_name, sparse_image_write_cmd)
                else:
                    raw_image_write_cmd = \
                        self.__verse_script.raw_image_write(
                            each_name)
                    cmd = '%s_WRITE_FLAG%s' % (
                        each_name, raw_image_write_cmd)
                if each_name not in ("boot", "updater_boot",
                                     "updater", "updater_b"):
                    self.__verse_script.add_command(
                        cmd=cmd)

        UPDATE_LOGGER.print_log(
            "All full image processing completed! image count: %d" %
            len(self.__full_img_list))
        return full_image_content_len_list, full_image_file_obj_list

    @staticmethod
    def get_full_image_content(each_name):
        """
        Obtain the full image content.
        :param each_name: image name
        :return content: full image content if available; false otherwise
        """
        each_image_path = each_name
        if not os.path.exists(each_image_path):
            UPDATE_LOGGER.print_log(
                "The file is missing "
                "from the target package, "
                "the component: %s cannot be full update processed. " %
                each_image_path)
            return False
        with open(each_image_path, 'rb') as f_r:
            content = f_r.read()
        return content


def is_sparse_image(img_path):
    """
    Check whether the image is a sparse image.
    :param img_path: image path
    :return:
    """
    with open(img_path, 'rb') as f_r:
        image_content = f_r.read(HEADER_INFO_LEN)
        try:
            header_info = struct.unpack(HEADER_INFO_FORMAT, image_content)
        except struct.error:
            return False
        is_sparse = IncUpdateImage.image_header_info_check(header_info)[-1]
    if is_sparse:
        UPDATE_LOGGER.print_log("Sparse image is not supported!")
        raise RuntimeError
    return is_sparse


class IncUpdateImage:
    """
    Increment update image class
    """

    def __init__(self, image_path, map_path):
        """
        Initialize the inc image.
        :param image_path: img file path
        :param map_path: map file path
        """
        self.image_path = image_path
        self.offset_value_list = []
        self.care_block_range = None
        self.extended_range = None
        self.reserved_blocks = BlocksManager("0")
        self.file_map = []
        self.offset_index = []
        self.block_size = None
        self.total_blocks = None
        self.parse_sparse_image_file(image_path, map_path)

    def parse_sparse_image_file(self, image_path, map_path):
        """
        Parse the .img file.
        :param image_path: img file path
        :param map_path: map file path
        """
        self.block_size = block_size = 4096
        self.total_blocks = total_blocks = \
            os.path.getsize(self.image_path) // self.block_size
        reference = b'\0' * self.block_size
        with open(image_path, 'rb') as f_r:
            care_value_list, offset_value_list = [], []
            nonzero_blocks = []
            for i in range(self.total_blocks):
                blocks_data = f_r.read(self.block_size)
                if blocks_data != reference:
                    nonzero_blocks.append(i)
                    nonzero_blocks.append(i + 1)
            self.care_block_range = BlocksManager(nonzero_blocks)
            care_value_list = list(self.care_block_range.range_data)
            for idx, value in enumerate(care_value_list):
                if idx != 0 and (idx + 1) % 2 == 0:
                    be_value = int(care_value_list[idx - 1])
                    af_value = int(care_value_list[idx])
                    file_tell = be_value * block_size
                    offset_value_list.append(
                        (be_value, af_value - be_value,
                         file_tell, None))

            self.offset_index = [i[0] for i in offset_value_list]
            self.offset_value_list = offset_value_list
            extended_range = \
                self.care_block_range.extend_value_to_blocks(EXTEND_VALUE)
            all_blocks = BlocksManager(range_data=(0, total_blocks))
            self.extended_range = \
                extended_range.get_intersect_with_other(all_blocks). \
                get_subtract_with_other(self.care_block_range)
            self.parse_block_map_file(map_path, f_r)

    def parse_block_map_file(self, map_path, image_file_r):
        """
        Parses the map file for blocks where files are contained in the image.
        :param map_path: map file path
        :param image_file_r: file reading object
        :return:
        """
        remain_range = self.care_block_range
        temp_file_map = {}

        with open(map_path, 'r') as f_r:
            # Read the .map file and process each line.
            for each_line in f_r.readlines():
                each_map_path, ranges_value = each_line.split(None, 1)
                each_range = BlocksManager(ranges_value)
                temp_file_map[each_map_path] = each_range
                # each_range is contained in the remain range.
                if each_range.size() != each_range. \
                        get_intersect_with_other(remain_range).size():
                    raise RuntimeError
                # After the processing is complete,
                # remove each_range from remain_range.
                remain_range = remain_range.get_subtract_with_other(each_range)
        reserved_blocks = self.reserved_blocks
        # Remove reserved blocks from all blocks.
        remain_range = remain_range.get_subtract_with_other(reserved_blocks)

        # Divide all blocks into zero_blocks
        # (if there are many) and nonzero_blocks.
        zero_blocks_list = []
        nonzero_blocks_list = []
        nonzero_groups_list = []
        default_zero_block = ('\0' * self.block_size).encode()

        nonzero_blocks_list, nonzero_groups_list, zero_blocks_list = \
            self.apply_remain_range(
                default_zero_block, image_file_r, nonzero_blocks_list,
                nonzero_groups_list, remain_range, zero_blocks_list)

        temp_file_map = self.get_file_map(
            nonzero_blocks_list, nonzero_groups_list,
            reserved_blocks, temp_file_map, zero_blocks_list)
        self.file_map = temp_file_map

    def apply_remain_range(self, *args):
        """
        Implement traversal processing of remain_range.
        """
        default_zero_block, image_file_r, \
            nonzero_blocks_list, nonzero_groups_list, \
            remain_range, zero_blocks_list = args
        for start_value, end_value in remain_range:
            for each_value in range(start_value, end_value):
                # bisect 二分查找，b在self.offset_index中的位置
                idx = bisect.bisect_right(self.offset_index, each_value) - 1
                chunk_start, _, file_pos, fill_data = \
                    self.offset_value_list[idx]
                data = self.get_file_data(self.block_size, chunk_start,
                                          default_zero_block, each_value,
                                          file_pos, fill_data, image_file_r)

                zero_blocks_list, nonzero_blocks_list, nonzero_groups_list = \
                    self.get_zero_nonzero_blocks_list(
                        data, default_zero_block, each_value,
                        nonzero_blocks_list, nonzero_groups_list,
                        zero_blocks_list)
        return nonzero_blocks_list, nonzero_groups_list, zero_blocks_list

    @staticmethod
    def get_file_map(*args):
        """
        Obtain the file map.
        nonzero_blocks_list nonzero blocks list,
        nonzero_groups_list nonzero groups list,
        reserved_blocks reserved blocks ,
        temp_file_map temporary file map,
        zero_blocks_list zero block list
        :return temp_file_map file map
        """
        nonzero_blocks_list, nonzero_groups_list, \
            reserved_blocks, temp_file_map, zero_blocks_list = args
        if nonzero_blocks_list:
            nonzero_groups_list.append(nonzero_blocks_list)
        if zero_blocks_list:
            temp_file_map[FILE_MAP_ZERO_KEY] = \
                BlocksManager(range_data=zero_blocks_list)
        if nonzero_groups_list:
            for i, blocks in enumerate(nonzero_groups_list):
                temp_file_map["%s-%d" % (FILE_MAP_NONZERO_KEY, i)] = \
                    BlocksManager(range_data=blocks)
        if reserved_blocks:
            temp_file_map[FILE_MAP_COPY_KEY] = reserved_blocks
        return temp_file_map

    @staticmethod
    def get_zero_nonzero_blocks_list(*args):
        """
        Get zero_blocks_list, nonzero_blocks_list, and nonzero_groups_list.
        data: block data,
        default_zero_block: default to zero block,
        each_value: each value,
        nonzero_blocks_list: nonzero_blocks_list,
        nonzero_groups_list: nonzero_groups_list,
        zero_blocks_list: zero_blocks_list,
        :return new_zero_blocks_list: new zero blocks list,
        :return new_nonzero_blocks_list: new nonzero blocks list,
        :return new_nonzero_groups_list: new nonzero groups list.
        """
        data, default_zero_block, each_value, \
            nonzero_blocks_list, nonzero_groups_list, \
            zero_blocks_list = args
        # Check whether the data block is equal to the default zero_blocks.
        if data == default_zero_block:
            zero_blocks_list.append(each_value)
            zero_blocks_list.append(each_value + 1)
        else:
            nonzero_blocks_list.append(each_value)
            nonzero_blocks_list.append(each_value + 1)
            # The number of nonzero_blocks is greater than
            # or equal to the upper limit.
            if len(nonzero_blocks_list) >= MAX_BLOCKS_PER_GROUP:
                nonzero_groups_list.append(nonzero_blocks_list)
                nonzero_blocks_list = []
        new_zero_blocks_list, new_nonzero_blocks_list, \
            new_nonzero_groups_list = \
            copy.copy(zero_blocks_list), \
            copy.copy(nonzero_blocks_list),\
            copy.copy(nonzero_groups_list)
        return new_zero_blocks_list, new_nonzero_blocks_list, \
            new_nonzero_groups_list

    @staticmethod
    def get_file_data(*args):
        """
        Get the file data.
        block_size: blocksize,
        chunk_start: the start position of chunk,
        default_zero_block: default to zero blocks,
        each_value: each_value,
        file_pos: file position,
        fill_data: data,
        image_file_r: read file object,
        :return data: Get the file data.
        """
        block_size, chunk_start, default_zero_block, each_value, \
            file_pos, fill_data, image_file_r = args
        if file_pos is not None:
            file_pos += (each_value - chunk_start) * block_size
            image_file_r.seek(file_pos, os.SEEK_SET)
            data = image_file_r.read(block_size)
        else:
            if fill_data == default_zero_block[:4]:
                data = default_zero_block
            else:
                data = None
        return data

    def range_sha256(self, ranges):
        """
        range sha256 hash content
        :param ranges: ranges value
        :return:
        """
        hash_obj = sha256()
        for data in self.__get_blocks_set_data(ranges):
            hash_obj.update(data)
        return hash_obj.hexdigest()

    def write_range_data_2_fd(self, ranges, file_obj):
        """
        write range data to fd
        :param ranges: ranges obj
        :param file_obj: file obj
        :return:
        """
        for data in self.__get_blocks_set_data(ranges):
            file_obj.write(data)

    def get_ranges(self, ranges):
        """
        get ranges value
        :param ranges: ranges
        :return: ranges value
        """
        return [each_data for each_data in self.__get_blocks_set_data(ranges)]

    def __get_blocks_set_data(self, blocks_set_data):
        """
        Get the range data.
        """
        with open(self.image_path, 'rb') as f_r:
            for start, end in blocks_set_data:
                diff_value = end - start
                idx = bisect.bisect_right(self.offset_index, start) - 1
                chunk_start, chunk_len, file_pos, fill_data = \
                    self.offset_value_list[idx]

                remain = chunk_len - (start - chunk_start)
                this_read = min(remain, diff_value)
                if file_pos is not None:
                    pos = file_pos + ((start - chunk_start) * self.block_size)
                    f_r.seek(pos, os.SEEK_SET)
                    yield f_r.read(this_read * self.block_size)
                else:
                    yield fill_data * (this_read * (self.block_size >> 2))
                diff_value -= this_read

                while diff_value > 0:
                    idx += 1
                    chunk_start, chunk_len, file_pos, fill_data = \
                        self.offset_value_list[idx]
                    this_read = min(chunk_len, diff_value)
                    if file_pos is not None:
                        f_r.seek(file_pos, os.SEEK_SET)
                        yield f_r.read(this_read * self.block_size)
                    else:
                        yield fill_data * (this_read * (self.block_size >> 2))
                    diff_value -= this_read

    @staticmethod
    def image_header_info_check(header_info):
        """
        Check for new messages of the header_info image.
        :param header_info: header_info
        :return:
        """
        image_flag = True
        # Sparse mirroring header ID. The magic value is fixed to 0xED26FF3A.
        magic_info = header_info[0]
        # major version number
        major_version = header_info[1]
        # minor version number
        minor_version = header_info[2]
        # Length of the header information.
        # The value is fixed to 28 characters.
        header_info_size = header_info[3]
        # Header information size of the chunk.
        # The length is fixed to 12 characters.
        chunk_header_info_size = header_info[4]
        # Number of bytes of a block. The default size is 4096.
        block_size = header_info[5]
        # Total number of blocks contained in the current image
        # (number of blocks in a non-sparse image)
        total_blocks = header_info[6]
        # Total number of chunks contained in the current image
        total_chunks = header_info[7]
        if magic_info != SPARSE_IMAGE_MAGIC:
            UPDATE_LOGGER.print_log(
                "SparseImage head Magic should be 0xED26FF3A!")
            image_flag = False
        if major_version != 1 or minor_version != 0:
            UPDATE_LOGGER.print_log(
                "SparseImage Only supported major version with "
                "minor version 1.0!")
            image_flag = False
        if header_info_size != 28:
            UPDATE_LOGGER.print_log(
                "SparseImage header info size must be 28! size: %u." %
                header_info_size)
            image_flag = False
        if chunk_header_info_size != 12:
            UPDATE_LOGGER.print_log(
                "SparseImage Chunk header size mast to be 12! size: %u." %
                chunk_header_info_size)
            image_flag = False
        ret_args = [block_size, chunk_header_info_size, header_info_size,
                    magic_info, total_blocks, total_chunks, image_flag]
        return ret_args
