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

import os
import subprocess
import unittest

from image_class import IncUpdateImage
from image_class import FullUpdateImage
from test.create_package_data import create_input_package
from test.create_package_data import clear_package
from script_generator import VerseScript
from utils import clear_resource
from blocks_manager import BlocksManager


class TestImage(unittest.TestCase):

    def setUp(self):
        print("set up")

    def tearDown(self):
        print("tear down")

    def test_update_full_image(self):
        """
        update_full_image，raw image script content
        :return:
        """
        create_input_package("test_target_package", package_type="source")
        with open('vendor.img', 'wb') as w_f:
            with open('./test_target_package/vendor.img', "rb") as\
                    r_f:
                r_f.seek(10)
                content = r_f.read()
            w_f.write(content)
        verse_script = VerseScript()
        FullUpdateImage("", ["vendor"], verse_script, ["vendor.img"]).\
            update_full_image()
        clear_resource()
        check_re = len(verse_script.script) != 0
        print(verse_script.script)
        if os.path.exists('vendor.img'):
            os.remove('vendor.img')
        self.assertEqual(check_re, True)
        clear_package("test_target_package")

    def test_get_file_data(self):
        """
        get_file_data，file_pos is None
        :return:
        """
        create_input_package("test_target_package", package_type="source")
        with open('./test_target_package/vendor.img', 'rb') as wo_f:
            f_r = wo_f
        default_zero_block = ('\0' * 4096).encode()
        fill_data = ('\0' * 4096).encode()[:4]
        check_re = IncUpdateImage.get_file_data(
            4096, 0, default_zero_block, 0,
            None, fill_data, f_r)
        self.assertEqual(check_re, default_zero_block)

        fill_data = ('\1' * 4096).encode()[:4]
        check_re = IncUpdateImage.get_file_data(
            4096, 0, default_zero_block, 0,
            None, fill_data, f_r)
        self.assertEqual(check_re, None)

        clear_resource()
        f_r.close()
        clear_package("test_target_package")

    def test_get_blocks_list(self):
        """
        get_zero_nonzero_blocks_list，data == default_zero_block
        :return:
        """
        default_zero_block = ('\0' * 4096).encode()
        data = ('\0' * 4096).encode()
        zero_blocks_list, nonzero_blocks_list, nonzero_groups_list = [], [], []
        zero_blocks_list, nonzero_blocks_list, nonzero_groups_list = \
            IncUpdateImage.get_zero_nonzero_blocks_list(
                data, default_zero_block, 1, nonzero_blocks_list,
                nonzero_groups_list, zero_blocks_list)
        check_re = len(zero_blocks_list) != 0
        self.assertEqual(check_re, True)

        data = ('\1' * 4096).encode()
        zero_blocks_list, nonzero_blocks_list, nonzero_groups_list = \
            [], [0] * 4096, []
        zero_blocks_list, nonzero_blocks_list, nonzero_groups_list = \
            IncUpdateImage.get_zero_nonzero_blocks_list(
                data, default_zero_block, 1, nonzero_blocks_list,
                nonzero_groups_list, zero_blocks_list)
        check_re = len(nonzero_groups_list) != 0
        self.assertEqual(check_re, True)

        clear_resource()

    def test_get_file_map(self):
        """
        get_file_map，if zero_blocks_list
        :return:
        """
        zero_blocks_list, nonzero_blocks_list, nonzero_groups_list = \
            [0] * 4096, [], []
        reserved_blocks = BlocksManager("0")
        temp_file_map = {}
        temp_file_map = \
            IncUpdateImage.get_file_map(
                nonzero_blocks_list, nonzero_groups_list, reserved_blocks,
                temp_file_map, zero_blocks_list)
        check_re = len(temp_file_map) != 0
        self.assertEqual(check_re, True)

        clear_resource()

    def test_read_ranges(self):
        """
        read_ranges, SparseImage reads ranges.
        :return:
        """
        create_input_package("test_target_package", package_type="source")
        image_path = "./test_target_package/vendor.img"
        map_path = "./test_target_package/vendor.map"
        cmd = ["e2fsdroid", "-B", map_path,
               "-a", "/vendor", image_path, "-e"]
        sub_p = subprocess.Popen(
            cmd, shell=False, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        sub_p.wait()
        ranges_list = IncUpdateImage(image_path, map_path).\
            get_ranges(BlocksManager("2"))
        check_re = len(ranges_list) != 0
        self.assertEqual(check_re, True)

        clear_resource()
        clear_package("test_target_package")

    def test_get_range_data(self):
        """
        _get_range_data, SparseImage _get_range_data
        :return:
        """
        create_input_package("test_target_package", package_type="source")
        image_path = "./test_target_package/vendor.img"
        map_path = "./test_target_package/vendor.map"
        cmd = ["e2fsdroid", "-B", map_path,
               "-a", "/vendor", image_path, "-e"]
        sub_p = subprocess.Popen(
            cmd, shell=False, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        sub_p.wait()
        s_image = IncUpdateImage(image_path, map_path)
        s_image.offset_value_list = [[39, 0, None, 10]]
        ranges_list = s_image.get_ranges(BlocksManager("2"))
        check_re = len(ranges_list) != 0
        self.assertEqual(check_re, True)

        s_image.offset_value_list = [(2, 0, None, 1), (2, 2, None, 1)]
        ranges_list = s_image.get_ranges(BlocksManager("2"))
        check_re = len(ranges_list) != 0
        self.assertEqual(check_re, True)

        s_image.offset_value_list = [(2, 0, None, 1), (2, 2, 1, 1)]
        ranges_list = s_image.get_ranges(BlocksManager("2"))
        check_re = len(ranges_list) != 0
        self.assertEqual(check_re, True)

        clear_resource()
        clear_package("test_target_package")
