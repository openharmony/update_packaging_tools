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
Description : pack chunks to update.bin.
"""
import os
import subprocess
import build_module_img
import tempfile
from utils import OPTIONS_MANAGER
from utils import DIFF_EXE_PATH
from transfers_manager import ActionType

DIFF_BLOCK_LIMIT = 10240


class PatchPackageChunk:

    def __init__(self, *args):
        self.src_file, self.tgt_file, self.do_pkg_diff, self.transfer_content, self.diff_offset, self.patch_dat_file_obj,\
            self.src_img_obj, self.tgt_img_obj, each_action, self.chunk_data_list = args
        self.chunk_src_obj = tempfile.NamedTemporaryFile(prefix="chunk_src_file", mode='wb')
        self.chunk_tgt_obj = tempfile.NamedTemporaryFile(prefix="chunk_tft_file", mode='wb')
        self.chunk_patch_obj = tempfile.NamedTemporaryFile(prefix="chunk_patch_file", mode='wb')
        self.patch_obj = tempfile.NamedTemporaryFile(prefix="chunk_patch_file", mode='wb')
        self.limit_size = OPTIONS_MANAGER.chunk_limit * build_module_img.BLOCK_SIZE
        
        self.__apply_compute_patch(self.src_file, self.tgt_file, self.patch_obj,
                                   4096)
        print(os.stat(self.patch_obj.name).st_size)
        print(f'src:{each_action.src_block_set.to_string_raw()}({each_action.src_block_set.size()}) tgt:{each_action.tgt_block_set.to_string_raw()}({each_action.tgt_block_set.size()})')
        self.__apply_compute_patch(self.src_file, self.tgt_file, self.patch_obj, int(self.limit_size / DIFF_BLOCK_LIMIT)) # 45KB
        
        self.__chunk_patch(self.patch_obj.name, int(self.limit_size / DIFF_BLOCK_LIMIT), each_action)
    
    def split_into_closest_multiples_of_ten(self, n):
        """
        Split an integer into two parts, such that the sum of the parts is a multiple of 10.
        :param n: The integer to split.
        :return: A tuple containing the two parts.
        """
        # Check if the input is a multiple of 10
        if n % 10 != 0:
            raise ValueError("Input must be a multiple of 10.")     
        # Calculate the two parts
        half = n // 2        
        # Ensure both parts are multiples of 10
        part1 = (half // 10) * 10  # Nearest lower multiple of 10
        part2 = n - part1           # Remaining part
        # If part2 is not a multiple of 10, adjust part1 and part2
        if part2 % 10 != 0:
            part1 += 10
            part2 = n - part1
        return part1, part2
    
    def split_old_file(self, each_action, start_blocks, blocks, src_file_blocks, src_file_obj, src_file_bytes):
        """处理旧文件的分块逻辑"""
        if (start_blocks + blocks) > each_action.src_block_set.size():
            src_file_blocks = each_action.src_block_set
            temp_blocks = each_action.src_block_set.size() - blocks
            if temp_blocks < 0:
                temp_blocks = 0
            else:
                temp_src_blocks_to_write = src_file_blocks.get_first_block_obj(temp_blocks)
                src_file_blocks = src_file_blocks.get_subtract_with_other(temp_src_blocks_to_write)
            src_blocks_to_write = src_file_blocks.get_first_block_obj(blocks)
            src_start = src_file_bytes - blocks * build_module_img.BLOCK_SIZE
            if src_start < 0:
                src_start = 0
        else:
            src_start = start_blocks * build_module_img.BLOCK_SIZE
            src_blocks_to_write = src_file_blocks.get_first_block_obj(blocks)
            src_file_blocks = src_file_blocks.get_subtract_with_other(src_blocks_to_write)

        if src_file_bytes == 0:
            print(f'error: {src_file_bytes}')
            raise RuntimeError

        src_file_obj.seek(src_start)
        self.chunk_src_obj.seek(0)
        self.chunk_src_obj.truncate(0)
        bytes_obj = src_file_obj.read(int(blocks * build_module_img.BLOCK_SIZE))
        if len(bytes_obj) == 0:
            src_total_size = each_action.src_block_set.size()
            print(f'in: {src_total_size}')
            raise RuntimeError

        try:
            self.chunk_src_obj.write(bytes_obj)
        except Exception as e:
            print(f'error:{e}')
            raise RuntimeError

        return src_file_blocks, src_blocks_to_write, src_start
    
    def split_new_tgt_file(self, each_action, start_blocks, blocks, tgt_file_blocks, tgt_file_obj):
        """处理新目标文件的分块逻辑"""
        tgt_blocks_to_write = tgt_file_blocks.get_first_block_obj(blocks)
        tgt_file_blocks = tgt_file_blocks.get_subtract_with_other(tgt_blocks_to_write)
        tgt_file_obj.seek(int(start_blocks * build_module_img.BLOCK_SIZE))
        self.chunk_tgt_obj.seek(0)
        self.chunk_tgt_obj.truncate(0)
        bytes_obj = tgt_file_obj.read(int(blocks * build_module_img.BLOCK_SIZE))
        if len(bytes_obj) == 0:
            tgt_total_size = each_action.tgt_block_set.size()
            print(f'in: {tgt_total_size}')
            raise RuntimeError
        self.chunk_tgt_obj.write(bytes_obj)

        return tgt_file_blocks, tgt_blocks_to_write
    
    def process_patch_chunk(self, src_blocks_to_write, tgt_blocks_to_write, chunk_patch_size, start_blocks, blocks):
        """
        处理每个 chunk patch 的逻辑，包括打印信息、更新状态、保存 patch 内容等。
        """
        subfile_patch_totalsize = chunk_patch_size
        start_blocks += blocks

        # 打印 patch 文件的信息
        print(f'self.chunk_patch_obj len: {os.stat(self.chunk_patch_obj.name).st_size} '
            f'old: {os.stat(self.patch_dat_file_obj.name).st_size} total: {self.diff_offset}')

        # 读取 patch 文件内容并保存
        with open(self.chunk_patch_obj.name, 'rb') as file_read:
            patch_value = file_read.read()
            self.patch_dat_file_obj.write(patch_value)

        # 如果 patch 有内容，保存到 transfer_content 和其他相关变量
        if len(patch_value) > 0:
            diff_type = "pkgdiff" if self.do_pkg_diff else "bsdiff"
            diff_str = ("%s %d %d %s %s %s %d %s\n" % (
                diff_type,
                self.diff_offset, len(patch_value),
                self.src_img_obj.range_sha256(src_blocks_to_write),
                self.tgt_img_obj.range_sha256(tgt_blocks_to_write),
                tgt_blocks_to_write.to_string_raw(), src_blocks_to_write.size(), src_blocks_to_write.to_string_raw()))
            print(diff_str)

            self.diff_offset += len(patch_value)
            self.chunk_data_list.append(patch_value)
            self.transfer_content.append(diff_str)

            # 打印 transfer_content 长度信息
            print(f'in transfer_content len: {len(self.transfer_content)} '
                f'self.chunk_patch_obj len: {os.stat(self.patch_dat_file_obj.name).st_size}')

        # 返回更新后的 totalsize 和 start_blocks
        return subfile_patch_totalsize, start_blocks
    
    def cut_files(self, subblocks_list, each_action):
        start_blocks = 0
        subfile_patch_sizelist = []
        subfile_patch_totalsize = 0
        src_file_blocks = each_action.src_block_set
        tgt_file_blocks = each_action.tgt_block_set

        src_file_obj = open(self.src_file, 'rb')
        file_stat = os.stat(self.src_file)
        src_file_bytes = file_stat.st_size
        tgt_file_obj = open(self.tgt_file, 'rb')
        file_stat = os.stat(self.tgt_file)
        tgt_file_bytes = file_stat.st_size
        src_start = 0
        
        # 遍历 subblocks_list
        i = 0
        while i < len(subblocks_list):
            blocks = subblocks_list[i]

            # Store the original state for restoration
            original_src_file_blocks = src_file_blocks
            original_tgt_file_blocks = tgt_file_blocks
            original_start_blocks = start_blocks

            # Splite old files
            src_file_blocks, src_blocks_to_write, src_start = self.split_old_file(each_action, start_blocks, blocks, src_file_blocks, src_file_obj, src_file_bytes)

            # Splite new tgt file
            tgt_file_blocks, tgt_blocks_to_write = self.split_new_tgt_file(each_action, start_blocks, blocks, tgt_file_blocks, tgt_file_obj)

            # Here's a patch
            self.chunk_patch_obj = self.__apply_compute_patch(self.chunk_src_obj.name, self.chunk_tgt_obj.name, self.chunk_patch_obj, 4096)
            chunk_patch_size = os.stat(self.chunk_patch_obj.name).st_size

            # 如果patch大小超过限制，将blocks切分为两部分插入subblocks_list中
            if chunk_patch_size > self.limit_size:
                print(f'Patch size {chunk_patch_size} exceeds limit {self.limit_size}, splitting blocks...')
                block_one, block_two = self.split_into_closest_multiples_of_ten(blocks)
                if block_one % 10 != 0 or block_two % 10 != 0 or block_one + block_two != blocks:
                    print(f"Error: blocks size split error.")
                    raise RuntimeError
                
                # Restore the previous state
                src_file_blocks = original_src_file_blocks
                tgt_file_blocks = original_tgt_file_blocks
                start_blocks = original_start_blocks
        
                # 在当前位置插入两个新的blocks
                subblocks_list[i : i + 1] = [block_one, block_two]
                print(f'Inserted two new blocks: {block_one, block_two}')
                print(f'Current subblocks_list: {subblocks_list}')
                continue  # 跳出这次循环，重新处理新分解的块
            else:
                print(f'Patch size {chunk_patch_size} within limit {self.limit_size}, no splitting needed.')
                subfile_patch_sizelist.append(chunk_patch_size)
                    
            print(f'[{int(src_start)}, {int(os.stat(self.chunk_src_obj.name).st_size / build_module_img.BLOCK_SIZE)}] '
            f'diff [{start_blocks}, {int(os.stat(self.chunk_tgt_obj.name).st_size / build_module_img.BLOCK_SIZE)}] => {chunk_patch_size}')
            
            subfile_patch_totalsize, start_blocks = self.process_patch_chunk(
                src_blocks_to_write, tgt_blocks_to_write, chunk_patch_size, start_blocks, blocks)
            # 继续处理下一个块
            i += 1
        
        src_file_obj.close()
        tgt_file_obj.close()
            
        return subfile_patch_sizelist, subfile_patch_totalsize

    def __apply_compute_patch(self, src_file, tgt_file, patch_obj, limit):
        """
        Add command content to the script.
        :param src_file: source file name
        :param tgt_file: target file name
        :return:
        """
        patch_obj.seek(0)
        patch_obj.truncate(0)
        cmd = [DIFF_EXE_PATH] if self.do_pkg_diff else [DIFF_EXE_PATH, '-b', '1']

        cmd.extend(['-s', src_file, '-d', tgt_file,
                    '-p', patch_obj.name, '-l', f'{limit}'])
        sub_p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
        output, _ = sub_p.communicate(timeout=300)
        sub_p.wait()
        patch_obj.seek(0)
        
        if sub_p.returncode != 0:
            raise ValueError(output)
        
        return patch_obj
    
    def __chunk_patch(self, patch_file_obj, file_limit_size, each_action):   
        # 1.Parase patch
        patch_list = []
        file_limit_size = int(file_limit_size * DIFF_BLOCK_LIMIT / build_module_img.BLOCK_SIZE)
        file_stat = os.stat(patch_file_obj)
        file_size_bytes = file_stat.st_size
        with open(patch_file_obj, 'rb') as file:
            print(file.read(8))  # title
            blocks = int.from_bytes(file.read(4), byteorder='little')
            print({blocks})
            lastoffset = 0
            for i in range(blocks):
                file.read(20)  # Ignore 20B
                offset = int.from_bytes(file.read(8), byteorder='little')  # patchOffset
                if lastoffset == 0:
                    lastoffset = offset
                else:
                    patch_list.append(offset - lastoffset)
                    lastoffset = offset
            patch_list.append(file_size_bytes - lastoffset)
            print(patch_list)
            print(f'fileLen:{file_size_bytes}')

        # 2.Split files
        total = 0
        blocks = 0
        index = 0
        subblocks_list = []
        for dt in patch_list:
            total += dt
            if total < 0:
                total = 0
            blocks += file_limit_size
            if total > self.limit_size:
                subblocks_list.append(blocks - file_limit_size)  # 确保结果小于45 * 102
                blocks = file_limit_size
                total = dt
        if blocks > 0:
            subblocks_list.append(blocks)
        print(subblocks_list)
        # 3、Cut files
        subfile_patch_sizelist, subfile_patch_totalsize = self.cut_files(subblocks_list, each_action)
            
        # 4.Stats
        print(f'\ndebug do over\n')
        print(subfile_patch_sizelist)
        print(subfile_patch_totalsize)
        # 5.Comparison with Native
        print(f'old:{file_stat.st_size} new:{subfile_patch_totalsize}')
        