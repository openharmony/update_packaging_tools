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
from collections import OrderedDict

from test.create_package_data import create_input_package
from test.create_package_data import clear_package
from utils import OPTIONS_MANAGER
from utils import clear_resource
from utils import VERSION_MBN_PATH
from utils import BOARD_LIST_PATH
from update_package import get_hash_content
from update_package import signing_package
from script_generator import PreludeScript
from script_generator import VerseScript
from script_generator import RefrainScript
from script_generator import EndingScript
from update_package import build_update_package
from update_package import get_component_list


class TestUpdatePackage(unittest.TestCase):

    def setUp(self):
        print("set up")

    def tearDown(self):
        print("tear down")

    def test_create_update_bin_failed(self):
        """
        create_update_bin, Failed to generate bin
        :return:
        """

        OPTIONS_MANAGER.head_info_list = \
            ["01", "123456", "Hi3516DV300-eng 10 QP1A.190711.020",
             "2021-01-23", "12:30"]
        OPTIONS_MANAGER.component_info_dict = \
            {"version_list": ["1"] * 5, "board_list": ["1"] * 5,
             'vendor': ["1"] * 5}
        with open(VERSION_MBN_PATH, 'w') as w_f:
            w_f.write('test content')
        with open(BOARD_LIST_PATH, 'w') as w_f:
            w_f.write('test content')
        with open(VERSION_MBN_PATH) as om_first_f:
            OPTIONS_MANAGER.full_image_file_obj_list = [om_first_f]
        OPTIONS_MANAGER.full_img_list = ['vendor']
        OPTIONS_MANAGER.incremental_img_list = []
        OPTIONS_MANAGER.hash_algorithm = 'test_algo'
        OPTIONS_MANAGER.target_package_config_dir = ""
        OPTIONS_MANAGER.version_mbn_file_path = VERSION_MBN_PATH
        OPTIONS_MANAGER.board_list_file_path = BOARD_LIST_PATH

        get_component_list(
            OPTIONS_MANAGER.full_image_file_obj_list,
            OrderedDict([('version_list', ['1', '1', '1', '1', '1']),
                         ('board_list', ['1', '1', '1', '1', '1'])]))

        create_input_package(
            "test_target_package", package_type="source")

        OPTIONS_MANAGER.hash_algorithm = 'sha256'
        OPTIONS_MANAGER.target_package_config_dir = \
            "./test_target_package/updater_config"
        OPTIONS_MANAGER.target_package_dir = \
            "./test_target_package/"
        with open(VERSION_MBN_PATH) as om_second_f:
            OPTIONS_MANAGER.total_script_file_obj = om_second_f
        OPTIONS_MANAGER.full_img_list = []
        OPTIONS_MANAGER.opera_script_file_name_dic = {}
        OPTIONS_MANAGER.private_key = "../"
        OPTIONS_MANAGER.product = 'Hi3516'
        prelude_script = PreludeScript()
        verse_script = VerseScript()
        refrain_script = RefrainScript()
        ending_script = EndingScript()
        check_re = build_update_package(
            False, 'test_dir', prelude_script, verse_script,
            refrain_script, ending_script)
        self.assertEqual(check_re, False)

        OPTIONS_MANAGER.hash_algorithm = 'sha256'
        OPTIONS_MANAGER.target_package_config_dir = ""
        OPTIONS_MANAGER.target_package_dir = \
            "./test_target_package/"
        with open(VERSION_MBN_PATH) as om_third_f:
            OPTIONS_MANAGER.total_script_file_obj = om_third_f
        OPTIONS_MANAGER.full_img_list = []
        OPTIONS_MANAGER.opera_script_file_name_dic = {}
        OPTIONS_MANAGER.private_key = "../"
        OPTIONS_MANAGER.product = 'Hi3516'
        verse_script = VerseScript()
        check_re = build_update_package(
            False, 'test_dir', prelude_script, verse_script,
            refrain_script, ending_script)
        self.assertEqual(check_re, False)

        if os.path.exists(VERSION_MBN_PATH):
            os.remove(VERSION_MBN_PATH)
        if os.path.exists(BOARD_LIST_PATH):
            os.remove(BOARD_LIST_PATH)
        clear_resource()
        clear_package("test_target_package")

    def test_get_hash_content(self):
        """
        get_hash_content, Get hash.
        :return:
        """
        with self.assertRaises(RuntimeError):
            get_hash_content("non_existent.file", 'sha256')

        re_str = get_hash_content("non_existent.file", 'test_sha')
        check_re = re_str is False
        self.assertEqual(check_re, True)
        clear_resource()

    def test_signing_package(self):
        """
        test signing_package
        :return:
        """
        package_path = 'test.zip'
        with self.assertRaises(OSError):
            signing_package(package_path, "sha256",
                            position=1, package_type='.bin')

        with open(package_path, 'wb') as w_f:
            w_f.write('test content'.encode())
        check_re = signing_package(package_path, "sha256",
                                   position=1, package_type='.bin')
        self.assertEqual(check_re, True)
        os.remove(package_path)
