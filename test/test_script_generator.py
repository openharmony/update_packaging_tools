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
import unittest

from test.create_package_data import create_file
from test.create_package_data import get_target_vendor_data
from script_generator import get_proportion_value_list
from script_generator import Script
from script_generator import adjust_proportion_value_list
from script_generator import get_progress_value
from log_exception import VendorExpandError
from utils import OPTIONS_MANAGER


class TestScriptGenerator(unittest.TestCase):

    def setUp(self):
        print("set up")

    def tearDown(self):
        print("tear down")

    def test_get_proportion_value_list(self):
        """
        Get progress allocation
        :return:
        """
        proportion_value_list = get_proportion_value_list([1000, 1])
        adjusted_proportion_value_list = adjust_proportion_value_list(
            proportion_value_list, 60)
        self.assertEqual(adjusted_proportion_value_list, [59, 1])

    def test_proportion_value_list(self):
        """
        Schedule allocation adjustment guarantee sum = 60
        (default value)
        :return:
        """
        adjusted_proportion_value_list1 = adjust_proportion_value_list(
            [58, 1], 60)
        adjusted_proportion_value_list2 = adjust_proportion_value_list(
            [60, 1], 60)
        self.assertEqual(adjusted_proportion_value_list1, [58, 2])
        self.assertEqual(adjusted_proportion_value_list2, [59, 1])

    def test_proportion_value_list1(self):
        """
        Schedule allocation adjustment guarantee sum = 60
        (default value)
        :return:
        """
        adjusted_proportion_value_list = adjust_proportion_value_list(
            [], 60)
        self.assertEqual(adjusted_proportion_value_list, [])

    def test_script_command_content(self):
        """
        script, SuperClass commands.
        """
        with self.assertRaises(VendorExpandError):
            TestScript().sha_check()

        with self.assertRaises(VendorExpandError):
            TestScript().first_block_check()

        with self.assertRaises(VendorExpandError):
            TestScript().abort()

        with self.assertRaises(VendorExpandError):
            TestScript().show_progress()

        with self.assertRaises(VendorExpandError):
            TestScript().block_update()

        with self.assertRaises(VendorExpandError):
            TestScript().sparse_image_write()

        with self.assertRaises(VendorExpandError):
            TestScript().raw_image_write()

        with self.assertRaises(VendorExpandError):
            TestScript().get_status()

        with self.assertRaises(VendorExpandError):
            TestScript().set_status()

        with self.assertRaises(VendorExpandError):
            TestScript().reboot_now()

        with self.assertRaises(VendorExpandError):
            TestScript().updater_partitions()

    def test_get_progress_value(self):
        """
        script, SuperClass commands.
        """
        file_path = "./vendor.img"
        create_file(file_path, get_target_vendor_data())
        with open(file_path) as wo_f:
            file_obj = wo_f
        OPTIONS_MANAGER.two_step = True
        OPTIONS_MANAGER.full_img_list = []
        OPTIONS_MANAGER.incremental_img_list = ['vendor', 'updater']
        OPTIONS_MANAGER.incremental_image_file_obj_list = [file_obj]
        progress_value_dict = get_progress_value(distributable_value=60)
        check_re = len(progress_value_dict) != 0
        self.assertEqual(check_re, True)
        file_obj.close()
        if os.path.exists(file_path):
            os.remove(file_path)


class TestScript(Script):
    def __init__(self):
        super(TestScript, self).__init__()
