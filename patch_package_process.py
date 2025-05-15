#!/usr/bin/env python3
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

import multiprocessing
import subprocess
import tempfile
import zipfile
from ctypes import pointer
from log_exception import UPDATE_LOGGER
from blocks_manager import BlocksManager
from transfers_manager import ActionType
from update_package import PkgHeader
from update_package import PkgComponent
from utils import OPTIONS_MANAGER
from utils import ON_SERVER
from utils import DIFF_EXE_PATH
from patch_package_chunk import PatchPackageChunk
from create_chunk import get_chunk_sha256

NEW_DAT = "new.dat"
PATCH_DAT = "patch.dat"
TRANSFER_LIST = "transfer.list"


class PatchProcess:
    def __init__(self, partition, tgt_image, src_image,
                 actions_list):
        self.actions_list = actions_list
        self.worker_threads = multiprocessing.cpu_count() // 2
        self.partition = partition
        self.tgt_img_obj = tgt_image
        self.src_img_obj = src_image
        self.version = 1
        self.touched_src_ranges = BlocksManager()
        self.touched_src_sha256 = None
        self.package_patch_zip = PackagePatchZip(partition)
        # ab copy param
        self.chunk_data_list = []
        self.chunk_new_list = []
        self.transfer_content_in_chunk = []
    
    @staticmethod
    def get_transfer_content(max_stashed_blocks, total_blocks_count,
                             transfer_content):
        """
        Get the tranfer content.
        """
        transfer_content = ''.join(transfer_content)
        transfer_content = \
            transfer_content.replace("TOTAL_MARK", str(total_blocks_count))
        transfer_content = \
            transfer_content.replace("MAX_STASH_MARK", str(max_stashed_blocks))
        transfer_content = \
            transfer_content.replace("ActionType.MOVE", "move")
        transfer_content = \
            transfer_content.replace("ActionType.ZERO", "zero")
        transfer_content = \
            transfer_content.replace("ActionType.NEW", "new")
        return transfer_content
    
    @staticmethod
    def check_partition(total, seq):
        so_far = BlocksManager()
        for i in seq:
            if so_far.is_overlaps(i):
                raise RuntimeError
            so_far = so_far.get_union_with_other(i)
        if so_far != total:
            raise RuntimeError

    @staticmethod
    def write_split_transfers(self, transfer_content, type_str, target_blocks, each_img_file):
        """
        Limit the size of operand in command 'new' and 'zero' to 1024 blocks.
        :param transfer_content: transfer content list
        :param type_str: type of the action to be processed.
        :param target_blocks: BlocksManager of the target blocks
        :return: total
        """
        if type_str not in (ActionType.NEW, ActionType.ZERO):
            raise RuntimeError
        if OPTIONS_MANAGER.stream_update and type_str == ActionType.NEW:
            blocks_limit = OPTIONS_MANAGER.chunk_limit
        else:
            blocks_limit = 1024
        total = 0
        while target_blocks.size() != 0:
            blocks_to_write = target_blocks.get_first_block_obj(blocks_limit)
            # Find the corresponding new.dat from the set of blocks
            new_data = b''
            if type_str == ActionType.NEW:
                new_data = self.process_new_blocks(self, new_data, blocks_to_write, each_img_file)
                self.chunk_new_list.append(new_data)       
            UPDATE_LOGGER.print_log("blocks_to_write: %s! and blocks_limit: %d" % (
                                        blocks_to_write.to_string_raw(), blocks_limit))
            # 为流式升级new添加hash值
            if OPTIONS_MANAGER.stream_update and type_str == ActionType.NEW:
                transfer_content.append(
                    "%s %s %s\n" % (type_str, get_chunk_sha256(new_data),
                                    blocks_to_write.to_string_raw()))
            else:
                transfer_content.append(
                    "%s %s\n" % (type_str, blocks_to_write.to_string_raw()))
            total += blocks_to_write.size()
            target_blocks = \
                target_blocks.get_subtract_with_other(blocks_to_write)       
        return total
    
    @staticmethod
    def process_new_blocks(self, new_data, blocks_to_write, each_img_file):
        """
        Process the new blocks to read data from the image file.
        :param blocks_to_write: The blocks to write.
        :param each_img_file: The image file to read from.
        :return: new_data
        """
         # 解析写入的块
        parse_range = self.parse_ranges(blocks_to_write.to_string_raw())
        for start, end in parse_range:
            start_index = start * 4096
            end_index = end * 4096
            print(f'start_index: {start}, end_index: {end}')
            with open(each_img_file, 'rb') as f:
                tartget_new_content = f.read()
                new_data += tartget_new_content[start_index:end_index]
        OPTIONS_MANAGER.len_block += len(new_data)
        print(f'new_data: {len(new_data)}')
        print(f'total blcok length: {OPTIONS_MANAGER.len_block}')
        return new_data
    
    @staticmethod
    def apply_compute_patch(src_file, tgt_file, limit, pkgdiff=False):
        """
        Add command content to the script.
        :param src_file: source file name
        :param tgt_file: target file name
        :param pkgdiff: whether to execute pkgdiff judgment
        :return:
        """
        patch_file_obj = \
            tempfile.NamedTemporaryFile(prefix="patch-", mode='wb')

        OPTIONS_MANAGER.incremental_temp_file_obj_list.append(
            patch_file_obj)
        cmd = [DIFF_EXE_PATH] if pkgdiff else [DIFF_EXE_PATH, '-b', '1']

        cmd.extend(['-s', src_file, '-d', tgt_file,
                    '-p', patch_file_obj.name, '-l', f'{limit}'])
        sub_p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
        output, _ = sub_p.communicate()
        sub_p.wait()
        patch_file_obj.seek(0)

        if sub_p.returncode != 0:
            raise ValueError(output)

        with open(patch_file_obj.name, 'rb') as file_read:
            patch_content = file_read.read()
        return patch_content, pkgdiff

    def patch_process(self, each_img_file):
        """
        Generate patches through calculation.
        """
        UPDATE_LOGGER.print_log("Patch Process!")

        new_dat_file_obj, patch_dat_file_obj, transfer_list_file_obj = \
            self.package_patch_zip.get_file_obj()

        stashes = {}
        total_blocks_count = 0
        stashed_blocks = 0
        max_stashed_blocks = 0
        transfer_content = ["%d\n" % self.version, "TOTAL_MARK\n",
                            "0\n", "MAX_STASH_MARK\n"]

        diff_offset = 0
        for each_action in self.actions_list:
            max_stashed_blocks, stashed_blocks = self.add_stash_command(
                each_action, max_stashed_blocks, stashed_blocks, stashes,
                transfer_content)

            free_commands_list, free_size, src_str_list = \
                self.add_free_command(each_action, stashes)

            src_str = " ".join(src_str_list)
            tgt_size = each_action.tgt_block_set.size()

            if each_action.type_str == ActionType.ZERO:
                total_blocks_count = \
                    self.apply_zero_type(each_action, total_blocks_count,
                                         transfer_content)
            elif each_action.type_str == ActionType.NEW:
                total_blocks_count = \
                    self.apply_new_type(each_action, new_dat_file_obj,
                                        tgt_size, total_blocks_count,
                                        transfer_content, each_img_file)
            elif each_action.type_str == ActionType.DIFFERENT:              
                max_stashed_blocks, stashed_blocks, total_blocks_count, diff_offset = \
                    self.apply_diff_style(
                        diff_offset, each_action, max_stashed_blocks,
                        patch_dat_file_obj, src_str, stashed_blocks, tgt_size,
                        total_blocks_count, transfer_content, self.chunk_data_list, each_img_file)
            else:
                UPDATE_LOGGER.print_log("Unknown action type: %s!" %
                                        each_action.type_str)
                raise RuntimeError
            if free_commands_list:
                transfer_content.append("".join(free_commands_list))
                stashed_blocks -= free_size

        self.after_for_process(max_stashed_blocks, total_blocks_count,
                               transfer_content, transfer_list_file_obj, each_img_file)
        
    def apply_new_type(self, each_action, new_dat_file_obj, tgt_size,
                       total_blocks_count, transfer_content, each_img_file):
        self.tgt_img_obj.write_range_data_2_fd(
            each_action.tgt_block_set, new_dat_file_obj)
        UPDATE_LOGGER.print_log("%7s %s %s" % (
            each_action.type_str, each_action.tgt_name,
            str(each_action.tgt_block_set)))
        temp_size = self.write_split_transfers(self,
            transfer_content,
            each_action.type_str, each_action.tgt_block_set, each_img_file)
        if tgt_size != temp_size:
            raise RuntimeError
        total_blocks_count += temp_size
        return total_blocks_count

    def apply_zero_type(self, each_action, total_blocks_count,
                        transfer_content, each_img_file):
        UPDATE_LOGGER.print_log("%7s %s %s" % (
            each_action.type_str, each_action.tgt_name,
            str(each_action.tgt_block_set)))
        to_zero = \
            each_action.tgt_block_set.get_subtract_with_other(
                each_action.src_block_set)
        if self.write_split_transfers(self, transfer_content, each_action.type_str,
                                      to_zero, each_img_file) != to_zero.size():
            raise RuntimeError
        total_blocks_count += to_zero.size()
        return total_blocks_count

    def apply_diff_style(self, *args):
        """
        Process actions of the diff type.
        """
        diff_offset, each_action, max_stashed_blocks,\
            patch_dat_file_obj, src_str, stashed_blocks, tgt_size,\
            total_blocks_count, transfer_content, chunk_data_list, each_img_file = args
        if self.tgt_img_obj. \
                range_sha256(each_action.tgt_block_set) == \
                self.src_img_obj.\
                range_sha256(each_action.src_block_set):
            each_action.type_str = ActionType.MOVE
            UPDATE_LOGGER.print_log("%7s %s %s (from %s %s)" % (
                each_action.type_str, each_action.tgt_name,
                str(each_action.tgt_block_set),
                each_action.src_name,
                str(each_action.src_block_set)))

            max_stashed_blocks, stashed_blocks, total_blocks_count = \
                self.add_move_command(
                    each_action, max_stashed_blocks, src_str,
                    stashed_blocks, tgt_size, total_blocks_count,
                    transfer_content)
        elif each_action.tgt_block_set.size() > 125 * 1024: # target_file_size > 125 * 1024 * 4KB = 500M
            each_action.type_str = ActionType.NEW
            new_dat_file_obj, patch_dat_file_obj, transfer_list_file_obj = \
                self.package_patch_zip.get_file_obj()
            total_blocks_count = \
                self.apply_new_type(each_action, new_dat_file_obj,
                                    tgt_size, total_blocks_count,
                                    transfer_content, each_img_file)
        else:
            # Streaming update for files larger than 45KB, sliced
            do_pkg_diff, patch_value, diff_offset = self.compute_diff_patch(  
                each_action, patch_dat_file_obj, diff_offset, src_str, transfer_content,
                chunk_data_list, tgt_size, total_blocks_count, each_img_file)
            if len(patch_value) > 0:
                stashed_blocks, max_stashed_blocks = self.update_stashed_blocks(each_action, stashed_blocks, max_stashed_blocks)

                self.add_diff_command(diff_offset, do_pkg_diff,
                                      each_action, patch_value, src_str,
                                      transfer_content)
                # Add dependency patch
                self.chunk_data_list.append(patch_value)
                
                diff_offset += len(patch_value)
                total_blocks_count += tgt_size
            else:
                UPDATE_LOGGER.print_log("0 patch: %s", patch_value)
        return max_stashed_blocks, stashed_blocks, total_blocks_count, diff_offset

    def update_stashed_blocks(self, each_action, stashed_blocks, max_stashed_blocks):
        """
        Update the stashed blocks based on overlaps between source and target block sets.
        """
        if each_action.src_block_set.is_overlaps(
                each_action.tgt_block_set):
            stashed_blocks = \
                stashed_blocks + each_action.src_block_set.size()
            if stashed_blocks > max_stashed_blocks:
                max_stashed_blocks = stashed_blocks
        return stashed_blocks, max_stashed_blocks
    
    def after_for_process(self, max_stashed_blocks, total_blocks_count,
                          transfer_content, transfer_list_file_obj, each_img):
        """
        Implement processing after cyclical actions_list processing.
        :param max_stashed_blocks: maximum number of stashed blocks in actions
        :param total_blocks_count: total number of blocks
        :param transfer_content: transfer content
        :param transfer_list_file_obj: transfer file object
        :return:
        """
        self.touched_src_sha256 = self.src_img_obj.range_sha256(
            self.touched_src_ranges)
        if self.tgt_img_obj.extended_range:
            if self.write_split_transfers(self,
                    transfer_content, ActionType.ZERO,
                    self.tgt_img_obj.extended_range, each_img) != \
                    self.tgt_img_obj.extended_range.size():
                raise RuntimeError
            total_blocks_count += self.tgt_img_obj.extended_range.size()
        all_tgt = BlocksManager(
            range_data=(0, self.tgt_img_obj.total_blocks))
        all_tgt_minus_extended = all_tgt.get_subtract_with_other(
            self.tgt_img_obj.extended_range)
        new_not_care = all_tgt_minus_extended.get_subtract_with_other(
            self.tgt_img_obj.care_block_range)
        self.add_erase_content(new_not_care, transfer_content)
        transfer_content = self.get_transfer_content(
            max_stashed_blocks, total_blocks_count, transfer_content)
        # Print the transfer_content before writing it to the file
        if OPTIONS_MANAGER.stream_update:
            # 暂时先不写入transfer_list 等到copy命令处理完，再统一写入
            self.transfer_content_in_chunk = transfer_content
            OPTIONS_MANAGER.max_stash_size = max(max_stashed_blocks * 4096, OPTIONS_MANAGER.max_stash_size)
        else: 
            transfer_list_file_obj.write(transfer_content.encode())
            OPTIONS_MANAGER.max_stash_size = max(max_stashed_blocks * 4096, OPTIONS_MANAGER.max_stash_size)
        
    def add_diff_command(self, *args):
        """
        Add the diff command.
        """
        diff_offset, do_pkg_diff, each_action,\
            patch_value, src_str, transfer_content = args
        self.touched_src_ranges = self.touched_src_ranges.get_union_with_other(
            each_action.src_block_set)
        diff_type = "pkgdiff" if do_pkg_diff else "bsdiff"
        transfer_content.append("%s %d %d %s %s %s %s\n" % (
            diff_type,
            diff_offset, len(patch_value),
            self.src_img_obj.range_sha256(each_action.src_block_set),
            self.tgt_img_obj.range_sha256(each_action.tgt_block_set),
            each_action.tgt_block_set.to_string_raw(), src_str))

    def compute_diff_patch(self, each_action, patch_dat_file_obj, diff_offset,
                           src_str, transfer_content, chunk_data_list, tgt_size, total_blocks_count, each_img_file):
        """
        Run the command to calculate the differential patch.
        """
        src_file_obj = \
            tempfile.NamedTemporaryFile(prefix="src-", mode='wb')
        self.src_img_obj.write_range_data_2_fd(
            each_action.src_block_set, src_file_obj)
        src_file_obj.seek(0)
        tgt_file_obj = tempfile.NamedTemporaryFile(
            prefix="tgt-", mode='wb')
        self.tgt_img_obj.write_range_data_2_fd(
            each_action.tgt_block_set, tgt_file_obj)
        tgt_file_obj.seek(0)
        OPTIONS_MANAGER.incremental_temp_file_obj_list.append(
            src_file_obj)
        OPTIONS_MANAGER.incremental_temp_file_obj_list.append(
            tgt_file_obj)
        do_pkg_diff = True
        try:
            patch_value, do_pkg_diff = self.apply_compute_patch(
                src_file_obj.name, tgt_file_obj.name, 4096, do_pkg_diff)
            # If the patch is larger than 45kb
            if OPTIONS_MANAGER.stream_update and len(patch_value) > OPTIONS_MANAGER.chunk_limit * 4096:
                self.touched_src_ranges = self.touched_src_ranges.get_union_with_other(
                    each_action.src_block_set)  
                if each_action.tgt_block_set.size() % 10 == 1 or each_action.src_block_set.size() <= 1:
                    each_action.type_str = ActionType.NEW
                    new_dat_file_obj, patch_dat_file_obj, transfer_list_file_obj = \
                        self.package_patch_zip.get_file_obj()
                    total_blocks_count = \
                        self.apply_new_type(each_action, new_dat_file_obj,
                                            tgt_size, total_blocks_count,
                                            transfer_content, each_img_file)
                # Do the slicing here
                else:
                    patch_package_chunk_obj = PatchPackageChunk(src_file_obj.name, tgt_file_obj.name, do_pkg_diff, transfer_content,
                                                                diff_offset, patch_dat_file_obj, self.src_img_obj, self.tgt_img_obj, each_action,
                                                                chunk_data_list)
                    diff_offset = patch_package_chunk_obj.diff_offset
                patch_value = ''                                         
            src_file_obj.close()
            tgt_file_obj.close()
        except ValueError:
            UPDATE_LOGGER.print_log("Patch process Failed!")
            UPDATE_LOGGER.print_log("%7s %s %s (from %s %s)" % (
                each_action.type_str, each_action.tgt_name,
                str(each_action.tgt_block_set),
                each_action.src_name,
                str(each_action.src_block_set)),
                                    UPDATE_LOGGER.ERROR_LOG)
            raise ValueError
        if len(patch_value) > 0:
            patch_dat_file_obj.write(patch_value)
            
        return do_pkg_diff, patch_value, diff_offset
    
    def add_move_command(self, *args):
        """
        Add the move command.
        """
        each_action, max_stashed_blocks, src_str,\
            stashed_blocks, tgt_size, total_blocks_count,\
            transfer_content = args
        src_block_set = each_action.src_block_set
        tgt_block_set = each_action.tgt_block_set
        if src_block_set != tgt_block_set:
            if src_block_set.is_overlaps(tgt_block_set):
                stashed_blocks = stashed_blocks + \
                                   src_block_set.size()
                if stashed_blocks > max_stashed_blocks:
                    max_stashed_blocks = stashed_blocks

            self.touched_src_ranges = \
                self.touched_src_ranges.get_union_with_other(src_block_set)

            transfer_content.append(
                "{type_str} {tgt_hash} {tgt_string} {src_str}\n".
                format(type_str=each_action.type_str,
                       tgt_hash=self.tgt_img_obj.
                       range_sha256(each_action.tgt_block_set),
                       tgt_string=tgt_block_set.to_string_raw(),
                       src_str=src_str))
            total_blocks_count += tgt_size
        return max_stashed_blocks, stashed_blocks, total_blocks_count

    def add_free_command(self, each_action, stashes):
        """
        Add the free command.
        :param each_action: action object to be processed
        :param stashes: Stash dict
        :return: free_commands_list, free_size, src_str_list
        """
        free_commands_list = []
        free_size = 0
        src_blocks_size = each_action.src_block_set.size()
        src_str_list = [str(src_blocks_size)]
        un_stashed_src_ranges = each_action.src_block_set
        mapped_stashes = []
        for _, each_stash_before in each_action.use_stash:
            un_stashed_src_ranges = \
                un_stashed_src_ranges.get_subtract_with_other(
                    each_stash_before)
            src_range_sha = \
                self.src_img_obj.range_sha256(each_stash_before)
            each_stash_before = \
                each_action.src_block_set.get_map_within(each_stash_before)
            mapped_stashes.append(each_stash_before)
            if src_range_sha not in stashes:
                raise RuntimeError
            src_str_list.append(
                "%s:%s" % (src_range_sha, each_stash_before.to_string_raw()))
            stashes[src_range_sha] -= 1
            if stashes[src_range_sha] == 0:
                free_commands_list.append("free %s\n" % (src_range_sha,))
                free_size += each_stash_before.size()
                stashes.pop(src_range_sha)
        self.apply_stashed_range(each_action, mapped_stashes, src_blocks_size,
                                 src_str_list, un_stashed_src_ranges)
        return free_commands_list, free_size, src_str_list

    def apply_stashed_range(self, *args):
        each_action, mapped_stashes, src_blocks_size,\
            src_str_list, un_stashed_src_ranges = args
        if un_stashed_src_ranges.size() != 0:
            src_str_list.insert(1, un_stashed_src_ranges.to_string_raw())
            if each_action.use_stash:
                mapped_un_stashed = each_action.src_block_set.get_map_within(
                    un_stashed_src_ranges)
                src_str_list.insert(2, mapped_un_stashed.to_string_raw())
                mapped_stashes.append(mapped_un_stashed)
                self.check_partition(
                    BlocksManager(range_data=(0, src_blocks_size)),
                    mapped_stashes)
        else:
            src_str_list.insert(1, "-")
            self.check_partition(
                BlocksManager(range_data=(0, src_blocks_size)), mapped_stashes)

    def add_stash_command(self, each_action, max_stashed_blocks,
                          stashed_blocks, stashes, transfer_content):
        """
        Add the stash command.
        :param each_action: action object to be processed
        :param max_stashed_blocks: number of max stash blocks in all actions
        :param stashed_blocks: number of stash blocks
        :param stashes: Stash dict
        :param transfer_content: transfer content list
        :return: max_stashed_blocks, stashed_blocks
        """
        for _, each_stash_before in each_action.stash_before:
            src_range_sha = \
                self.src_img_obj.range_sha256(each_stash_before)
            if src_range_sha in stashes:
                stashes[src_range_sha] += 1
            else:
                stashes[src_range_sha] = 1
                stashed_blocks += each_stash_before.size()
                self.touched_src_ranges = \
                    self.touched_src_ranges.\
                    get_union_with_other(each_stash_before)
                transfer_content.append("stash %s %s\n" % (
                    src_range_sha, each_stash_before.to_string_raw()))
        if stashed_blocks > max_stashed_blocks:
            max_stashed_blocks = stashed_blocks
        return max_stashed_blocks, stashed_blocks

    def write_script(self, partition, script_check_cmd_list,
                     script_write_cmd_list, verse_script):
        """
        Add command content to the script.
        :param partition: image name
        :param script_check_cmd_list: incremental check command list
        :param script_write_cmd_list: incremental write command list
        :param verse_script: verse script object
        :return:
        """
        ranges_str = self.touched_src_ranges.to_string_raw()
        expected_sha = self.touched_src_sha256

        sha_check_cmd = verse_script.sha_check(
            ranges_str, expected_sha, partition)

        first_block_check_cmd = verse_script.first_block_check(partition)

        abort_cmd = verse_script.abort(partition)

        cmd = 'if ({sha_check_cmd} != 0 || ' \
              '{first_block_check_cmd} != 0)' \
              '{{\n    {abort_cmd}}}\n'.format(
                sha_check_cmd=sha_check_cmd,
                first_block_check_cmd=first_block_check_cmd,
                abort_cmd=abort_cmd)

        script_check_cmd_list.append(cmd)

        block_update_cmd = verse_script.block_update(partition)

        cmd = '%s_WRITE_FLAG%s' % (partition, block_update_cmd)
        script_write_cmd_list.append(cmd)

    def add_erase_content(self, new_not_care, transfer_content):
        """
        Add the erase command.
        :param new_not_care: blocks that don't need to be cared about
        :param transfer_content: transfer content list
        :return:
        """
        erase_first = new_not_care.\
            get_subtract_with_other(self.touched_src_ranges)
        if erase_first.size() != 0:
            transfer_content.insert(
                4, "erase %s\n" % (erase_first.to_string_raw(),))
        erase_last = new_not_care.get_subtract_with_other(erase_first)
        if erase_last.size() != 0:
            transfer_content.append(
                "erase %s\n" % (erase_last.to_string_raw(),))

    def add_ab_copy_content(self, blocks_length, need_copy_blocks_list, transfer_content):
        """
        Add the copy command.
        :param all_blocks: all blocks of data in a image
        :param no_copy_blocks: remove blocks operated on in action_list
        :param transfer_content: transfer content list
        :return:transfer_content
        """
        new_dat_file_obj, patch_dat_file_obj, transfer_list_file_obj = \
            self.package_patch_zip.get_file_obj()
        transfer_lines = transfer_content.splitlines()
        if len(need_copy_blocks_list):
            tgt_string = ','.join(map(str, need_copy_blocks_list))
            
            new_line = "{type_str} {tgt_string_len},{tgt_string} {length} {src_str_len},{src_str}".format(\
                type_str='copy',
                tgt_string_len=len(need_copy_blocks_list),
                tgt_string=tgt_string,
                length=blocks_length,
                src_str_len=len(need_copy_blocks_list),
                src_str=tgt_string)
        else:
            new_line = "copy 2,0,1 1 2,0,1"
        if len(transfer_lines) >= 4:  # Check if there are at least 3 lines
            transfer_lines.insert(4, new_line)  # Insert before the fourth line
        else:
            transfer_lines.append(new_line)  # If there are less than 4 lines, just append    
        transfer_content = "\n".join(transfer_lines)
        transfer_list_file_obj.write(transfer_content.encode())
        UPDATE_LOGGER.print_log('AB Copy block[%s]' % need_copy_blocks_list, UPDATE_LOGGER.INFO_LOG)
        return transfer_content
    
    def parse_ranges(self, ranges_str):
        """Parses the range string and returns a list of tuples with start and end."""
        ranges = []
        parts = ranges_str.split(',')[1:]  # Skip the first part
        # Iterate through the parts in pairs
        for i in range(0, len(parts), 2):
            start = int(parts[i])
            end = int(parts[i + 1]) if (i + 1) < len(parts) else start + 1  # Handle last range case
        # Append the range as (start, end) where end is exclusive
            ranges.append((start, end))
        print(f'Parase blocks Ranges: {ranges}')
        return ranges
    
    def get_chunk_pkgdiff_list(self):
        return self.chunk_data_list
    
    def get_chunk_new_list(self):
        return self.chunk_new_list
    
    def get_transfer_content_in_chunk(self):
        return self.transfer_content_in_chunk
    

class PackagePatchZip:
    """
    Compress the patch file generated by the
    differential calculation as *.zip file.
    """
    def __init__(self, partition):
        self.partition = partition
        self.partition_new_dat_file_name = "%s.%s" % (partition, NEW_DAT)
        self.partition_patch_dat_file_name = "%s.%s" % (partition, PATCH_DAT)
        self.partition_transfer_file_name = "%s.%s" % (partition, TRANSFER_LIST)

        self.new_dat_file_obj = tempfile.NamedTemporaryFile(
            dir=OPTIONS_MANAGER.target_package, prefix="%s-" % NEW_DAT, mode='wb')
        self.patch_dat_file_obj = tempfile.NamedTemporaryFile(
            dir=OPTIONS_MANAGER.target_package, prefix="%s-" % PATCH_DAT, mode='wb')
        self.transfer_list_file_obj = tempfile.NamedTemporaryFile(
            dir=OPTIONS_MANAGER.target_package, prefix="%s-" % TRANSFER_LIST, mode='wb')

        OPTIONS_MANAGER.incremental_temp_file_obj_list.append(
            self.new_dat_file_obj)
        OPTIONS_MANAGER.incremental_temp_file_obj_list.append(
            self.patch_dat_file_obj)
        OPTIONS_MANAGER.incremental_temp_file_obj_list.append(
            self.transfer_list_file_obj)

        self.partition_file_obj = tempfile.NamedTemporaryFile(
            dir=OPTIONS_MANAGER.target_package, prefix="partition_patch-")

    def get_file_obj(self):
        """
        Obtain file objects.
        """
        self.new_dat_file_obj.flush()
        self.patch_dat_file_obj.flush()
        self.transfer_list_file_obj.flush()
        return self.new_dat_file_obj, self.patch_dat_file_obj, \
            self.transfer_list_file_obj

    def package_block_patch(self, zip_file):
        self.new_dat_file_obj.flush()
        self.patch_dat_file_obj.flush()
        self.transfer_list_file_obj.flush()
        if not OPTIONS_MANAGER.stream_update:
            # add new.dat to ota.zip
            zip_file.write(self.new_dat_file_obj.name, self.partition_new_dat_file_name)
            # add patch.dat to ota.zip
            zip_file.write(self.patch_dat_file_obj.name, self.partition_patch_dat_file_name)
            # add transfer.list to ota.zip
            zip_file.write(self.transfer_list_file_obj.name, self.partition_transfer_file_name)
