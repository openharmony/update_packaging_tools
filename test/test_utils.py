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
import tempfile
import unittest
import zipfile

from test.fake_data import PARTITION_FILE_CONVERSION_FAILED
from test.fake_data import UPDATER_SPECIFIED_CONFIG_REPEATS
from utils import unzip_package
from utils import clear_resource
from utils import OPTIONS_MANAGER
from utils import parse_update_config
from utils import get_update_info
from utils import VERSION_MBN_PATH
from utils import BOARD_LIST_PATH
from utils import UPDATER_CONFIG
from utils import parse_partition_file_xml
from patch_package_process import PatchProcess
from transfers_manager import ActionInfo
from transfers_manager import ActionType
from blocks_manager import BlocksManager


class TestUtils(unittest.TestCase):

    def setUp(self):
        print("set up")

    def tearDown(self):
        print("tear down")

    def test_unzip_package(self):
        """
        unzip_package, Missing updater_config dir.
        :return:
        """
        target_package = "test.zip"
        zip_obj = zipfile.ZipFile(target_package, "w")
        os.makedirs('test_dir')
        zip_obj.write('test_dir', 'test_dir')
        zip_obj.close()
        check_re = unzip_package(target_package, origin='target')
        os.remove(target_package)
        os.rmdir('test_dir')
        self.assertEqual(check_re, (False, False))

        target_package = "test.zip"
        zip_obj = zipfile.ZipFile(target_package, "w")
        os.makedirs(UPDATER_CONFIG)
        with open('test.file', 'w') as w_f:
            w_f.write('test')
        zip_obj.write(UPDATER_CONFIG, UPDATER_CONFIG)
        zip_obj.write('test.file', 'test.file')
        zip_obj.close()
        check_re = unzip_package(target_package, origin='target')
        os.remove(target_package)
        os.rmdir(UPDATER_CONFIG)
        os.remove('test.file')
        self.assertEqual((type(check_re[0]), os.path.exists(check_re[1])),
                         (tempfile.TemporaryDirectory, True))

    def test_parse_update_config(self):
        """
        parse_update_config, return False
        :return:
        """
        with open("./updater_specified_config_repeats.xml", "wb") as w_f:
            w_f.write(UPDATER_SPECIFIED_CONFIG_REPEATS.encode())
        check_re = parse_update_config("test.xml")
        clear_resource()
        self.assertEqual(
            check_re, [False, False, False, False, False, False, False])

        OPTIONS_MANAGER.target_package_dir = "./"
        check_re = parse_update_config(
            "./updater_specified_config_repeats.xml")
        clear_resource()
        self.assertEqual(
            check_re, [False, False, False, False, False, False, False])
        if os.path.exists("./updater_specified_config_repeats.xml"):
            os.remove("./updater_specified_config_repeats.xml")

    def test_clear_resource(self):
        """
        clear_resource, Clean up resources,
        OPTIONS_MANAGER.update_package_file_path
        :return:
        """
        with open('test.file', 'w') as w_f:
            w_f.write('test')
        OPTIONS_MANAGER.update_package_file_path = 'test.file'
        clear_resource(err_clear=True)
        clear_re = os.path.exists('test.file')
        clear_resource()
        self.assertEqual(clear_re, False)

    def test_get_update_info(self):
        """
        get_update_info, return False
        :return:
        """
        OPTIONS_MANAGER.target_package_config_dir = ""
        check_re = get_update_info()
        clear_resource()
        self.assertEqual(check_re, False)

        with open(VERSION_MBN_PATH, 'w') as w_f:
            w_f.write('test content')
        OPTIONS_MANAGER.target_package_config_dir = ""
        check_re = get_update_info()
        clear_resource()
        if os.path.exists(VERSION_MBN_PATH):
            os.remove(VERSION_MBN_PATH)
        self.assertEqual(check_re, False)

    def test_get_update_info_2(self):
        """
        get_update_info，parse_update_config, return False
        :return:
        """
        with open(VERSION_MBN_PATH, 'w') as w_f:
            w_f.write('test content')
        with open(BOARD_LIST_PATH, 'w') as w_f:
            w_f.write('test content')
        OPTIONS_MANAGER.target_package_config_dir = ""
        check_re = get_update_info()
        clear_resource()
        if os.path.exists(VERSION_MBN_PATH):
            os.remove(VERSION_MBN_PATH)
        if os.path.exists(BOARD_LIST_PATH):
            os.remove(BOARD_LIST_PATH)
        self.assertEqual(check_re, False)

    def test_parse_partition_file_xml(self):
        """
        parse_partition_file_xml, return False
        :return:
        """
        with open("./partition_file_conversion_failed.xml", "wb") as w_f:
            w_f.write(PARTITION_FILE_CONVERSION_FAILED)
        check_re = parse_partition_file_xml(
            "./partition_file_conversion_failed.xml")
        clear_resource()
        self.assertEqual(check_re, (False, False, False))
        if os.path.exists("./partition_file_conversion_failed.xml"):
            os.remove("./partition_file_conversion_failed.xml")

    def test_apply_zero_type(self):
        """
        apply_zero_type
        :return:
        """
        patch_process = PatchProcess("vendor", None, None, [])
        action_obj = ActionInfo(
                        ActionType.ZERO, "tgt_file_name", "__ZERO",
                        BlocksManager("0-5"), BlocksManager("0-5"))
        transfer_content = []
        patch_process.apply_zero_type(action_obj, 0, transfer_content)
        check_re = len(transfer_content) == 0
        clear_resource()
        self.assertEqual(check_re, True)
