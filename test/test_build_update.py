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
import shutil
import unittest
import sys
import zipfile

from build_update import increment_image_processing
from build_update import main
from build_update import check_update_package
from build_update import check_miss_private_key
from build_update import check_target_package_path
from test.create_package_data import clear_package
from test.create_package_data import create_input_package
from script_generator import VerseScript
from build_update import check_incremental_args
from test.fake_data import RSA_PRIVATE_KEY_DATA
from utils import OPTIONS_MANAGER
from utils import clear_resource
from build_update import check_package_version
from build_update import private_key_check


class TestUpdateUtils(unittest.TestCase):

    def setUp(self):
        print("set up")

    def tearDown(self):
        print("tear down")

    def test_update_pkg(self):
        """
        The whole process
        :return:
        """
        create_input_package("test_target_package")
        create_input_package("test_source_package", package_type="source")
        if not os.path.exists("./output_test"):
            os.mkdir("./output_test")
        sys.argv.clear()
        sys.argv.append("build_update.py")
        sys.argv.append("./test_target_package/")
        sys.argv.append("./output_test/demo")
        sys.argv.append("-s")
        sys.argv.append("./test_source_package.zip")
        sys.argv.append("-pk")
        sys.argv.append("./rsa_private_key2048.pem")
        main()
        output = "./output_test/demo"
        pkg_re = os.path.join(output, os.listdir(output)[0]).endswith('zip')
        shutil.rmtree("./output_test")
        self.assertEqual(pkg_re, True)
        clear_package("test_target_package")
        clear_package("test_source_package")

    def test_updater_partitions(self):
        """
        Update partitions
        :return:
        """
        create_input_package(
            "test_target_package_updater_partition",
            package_type="source", is_updater_partitions=True)
        if not os.path.exists("./output_test"):
            os.mkdir("./output_test")
        sys.argv.clear()
        sys.argv.append("build_update.py")
        sys.argv.append(
            "./test_target_package_updater_partition.zip")
        sys.argv.append("./output_test/demo")
        sys.argv.append("-pk")
        sys.argv.append("./rsa_private_key2048.pem")
        sys.argv.append("-pf")
        sys.argv.append("./partition_file.xml")
        main()
        output = "./output_test/demo"
        pkg_re = os.path.join(output, os.listdir(output)[0]).endswith('zip')
        shutil.rmtree("./output_test")
        self.assertEqual(pkg_re, True)
        clear_package("test_target_package_updater_partition")

    def test_updater_partitions2(self):
        """
        Update partitions，The incoming file does not exist:
        nonexistent_path.xml
        :return:
        """
        create_input_package(
            "test_target_package_updater_partition",
            package_type="source", is_updater_partitions=True)
        if not os.path.exists("./output_test"):
            os.mkdir("./output_test")
        sys.argv.clear()
        sys.argv.append("build_update.py")
        sys.argv.append(
            "./test_target_package_updater_partition.zip")
        sys.argv.append("./output_test/demo")
        sys.argv.append("-pk")
        sys.argv.append("./rsa_private_key2048.pem")
        sys.argv.append("-pf")
        sys.argv.append("../nonexistent_path.xml")
        main()
        output = "./output_test"
        pkg_re = len(os.listdir(output))
        self.assertEqual(pkg_re, 0)
        shutil.rmtree("./output_test")
        clear_resource()
        clear_package("test_target_package_updater_partition")

    def test_update_pkg_nozip(self):
        """
        The whole process, no zip mode
        :return:
        """
        create_input_package(
            "test_target_package_nozip", package_type="source")
        if not os.path.exists("./output_test"):
            os.mkdir("./output_test")
        sys.argv.clear()
        sys.argv.append("build_update.py")
        sys.argv.append("./test_target_package_nozip.zip")
        sys.argv.append("./output_test/demo")
        sys.argv.append("-nz")
        sys.argv.append("-pk")
        sys.argv.append("./rsa_private_key2048.pem")
        main()
        output = "./output_test/demo"
        pkg_re = os.path.join(output, os.listdir(output)[0]).endswith('bin')
        shutil.rmtree("./output_test")
        self.assertEqual(pkg_re, True)
        clear_package("test_target_package_nozip")

    def test_type_check(self):
        """
        Input parameter type detection, type_check return False,
        -s parameter does not exist.
        :return:
        """
        create_input_package(
            "test_target_package_nozip", package_type="source")
        if not os.path.exists("./output_test"):
            os.mkdir("./output_test")
        sys.argv.clear()
        sys.argv.append("build_update.py")
        sys.argv.append("./test_target_package_nozip.zip")
        sys.argv.append("./output_test/demo")
        sys.argv.append("-s")
        sys.argv.append("../test_type_check.test")
        sys.argv.append("-pk")
        sys.argv.append("./rsa_private_key2048.pem")
        main()
        output = "./output_test/"
        pkg_re = len(os.listdir(output))
        shutil.rmtree("./output_test")
        self.assertEqual(pkg_re, 0)
        clear_resource()
        clear_package("test_target_package_nozip")

    def test_check_update_package(self):
        """
        Input parameter type detection, check_update_package return False,
        update_package parameter does not exist.
        :return:
        """
        create_input_package(
            "test_target_package_nozip", package_type="source")
        if not os.path.exists("./output_test"):
            os.mkdir("./output_test")
        output = "./output_test/demo"
        if os.path.exists(output):
            shutil.rmtree(output)
        sys.argv.clear()
        sys.argv.append("build_update.py")
        sys.argv.append("./test_target_package_nozip.zip")
        sys.argv.append("test_build_update.py")
        sys.argv.append("-pk")
        sys.argv.append("./rsa_private_key2048.pem")
        main()
        output = "./output_test/"
        pkg_re = len(os.listdir(output))
        shutil.rmtree("./output_test")
        self.assertEqual(pkg_re, 0)
        clear_resource()
        clear_package("test_target_package_nozip")

    def test_check_update_package1(self):
        """
        Input parameter type detection, check_update_package return False,
        update_package parameter is file.
        :return:
        """
        arg = check_update_package("test_build_update.py")
        self.assertEqual(arg, False)

    def test_check_update_package2(self):
        """
        Input parameter type detection, check_update_package return False,
        make update_package failed.
        :return:
        """
        arg = check_update_package("")
        self.assertEqual(arg, False)

    def test_check_miss_private_key(self):
        """
        check_miss_private_key, -pk parameter is None.
        :return:
        """
        check_re = check_miss_private_key(None)
        self.assertEqual(check_re, False)

    def test_check_target_package_path(self):
        """
        Input parameter type detection, check_target_package_path return False,
        target_package parameter does not exist.
        :return:
        """
        target_package = "nonexistent_path.test"
        check_re = check_target_package_path(target_package)
        self.assertEqual(check_re, False)

    def test_check_target_package_path2(self):
        """
        Input parameter type detection, check_target_package_path return False,
        Check target_package dir.
        :return:
        """
        target_package = "test.zip"
        zip_obj = zipfile.ZipFile(target_package, "w")
        with open('test.file', 'w') as w_f:
            w_f.write('test')
        zip_obj.write('test.file', 'test.file')
        zip_obj.write('test.file', 'test2.file')
        zip_obj.close()

        check_re = check_target_package_path(target_package)
        os.remove(target_package)
        os.remove('test.file')
        self.assertEqual(check_re, False)

    def test_check_incremental_args(self):
        """
        check_incremental_args, Parameter exception, return False
        :return:
        """
        create_input_package(
            "test_source_package", package_type="source")
        check_re = check_incremental_args(False, None, None, ["vendor"])
        self.assertEqual(check_re, False)

        check_re = check_incremental_args(True, None, "", ["vendor"])
        self.assertEqual(check_re, False)

        check_re = check_incremental_args(False, "", "", ["vendor"])
        self.assertEqual(check_re, False)

        OPTIONS_MANAGER.source_package_dir = "./"
        check_re = check_incremental_args(False, None, "", ["vendor"])
        self.assertEqual(check_re, False)

        OPTIONS_MANAGER.target_package_version = \
            "Hi3516DV300-eng 10 QP1A.190711.019"
        check_re = check_incremental_args(
            False, None, "./test_source_package.zip", ["vendor"])
        clear_resource()
        self.assertEqual(check_re, False)
        clear_package("test_source_package")

    def test_check_userdata_image(self):
        """
        check_userdata_image, userdata does not upgrade not allowed.
        :return:
        """
        create_input_package(
            "test_target_package_userdata", package_type="source",
            has_userdata=True)
        if not os.path.exists("./output_test"):
            os.mkdir("./output_test")
        sys.argv.clear()
        sys.argv.append("build_update.py")
        sys.argv.append(
            "./test_target_package_userdata.zip")
        sys.argv.append("./output_test/demo")
        sys.argv.append("-pk")
        sys.argv.append("./rsa_private_key2048.pem")
        main()
        output = "./output_test/demo"
        pkg_re = os.path.exists(output)
        shutil.rmtree("./output_test")
        self.assertEqual(pkg_re, False)
        clear_resource()
        clear_package("test_target_package_userdata")

    def test_check_images_list(self):
        """
        check_images_list, Both full list and inc list are empty.
        :return:
        """
        create_input_package(
            "test_target_package_inc_full_all_none", package_type="source",
            is_inc_full_none=True)
        if not os.path.exists("./output_test"):
            os.mkdir("./output_test")
        sys.argv.clear()
        sys.argv.append("build_update.py")
        sys.argv.append(
            "./test_target_package_inc_full_all_none.zip")
        sys.argv.append("./output_test/demo")
        sys.argv.append("-pk")
        sys.argv.append("./rsa_private_key2048.pem")
        main()
        output = "./output_test/demo"
        pkg_re = os.path.exists(output)
        shutil.rmtree("./output_test")
        self.assertEqual(pkg_re, False)
        clear_resource()
        clear_package("test_target_package_inc_full_all_none")

    def test_check_package_version(self):
        """
        check_package_version, Exception in version number comparison.
        :return:
        """
        target_package_version = \
            "test version num"
        check_re = check_package_version(
            target_package_version, "Hi3516DV300-eng 10 QP1A.190711.020")
        clear_resource()
        self.assertEqual(check_re, False)

    def test_increment_image_processing(self):
        """
        increment_image_processing，Exception in inc process, return False
        :return:
        """
        create_input_package("test_target_package", package_type="target")
        create_input_package("test_target_package_miss_image",
                             package_type="target",
                             is_miss_image=True)
        create_input_package(
            "test_source_package_miss_image", package_type="source",
            is_miss_image=True)
        if not os.path.exists("./output_test"):
            os.mkdir("./output_test")
        verse_script = VerseScript()
        # miss source .img
        check_re = increment_image_processing(
            verse_script, ['test'], "", "")
        self.assertEqual(check_re, False)

        # miss target .img
        check_re = increment_image_processing(
            verse_script, ['vendor'], "./test_target_package/",
            "./test_target_package/")
        self.assertEqual(check_re, False)

        with open('vendor.img', 'w') as f_w:
            f_w.write('test content')
        with open('vendor.map', 'w') as f_w:
            f_w.write('test content')
        check_re = increment_image_processing(
            verse_script, ['vendor'], "", "")
        os.remove('vendor.img')
        os.remove('vendor.map')
        self.assertEqual(check_re, False)

        sys.argv.clear()
        sys.argv.append("build_update.py")
        sys.argv.append(
            "./test_target_package_miss_image")
        sys.argv.append("./output_test/demo")
        sys.argv.append("-s")
        sys.argv.append("./test_source_package_miss_image.zip")
        sys.argv.append("-pk")
        sys.argv.append("./rsa_private_key2048.pem")
        main()
        output = "./output_test/demo"
        pkg_re = os.path.exists(output)
        self.assertEqual(pkg_re, False)
        shutil.rmtree("./output_test")
        clear_resource()
        clear_package("test_target_package")
        clear_package("test_target_package_miss_image")
        clear_package("test_source_package_miss_image")

    def test_target_package_path_return(self):
        """
        check_target_package_path, return False
        :return:
        """
        with open("./rsa_private_key2048.pem", "wb") as w_f:
            w_f.write(RSA_PRIVATE_KEY_DATA)
        if not os.path.exists("./output_test"):
            os.mkdir("./output_test")
        sys.argv.clear()
        sys.argv.append("build_update.py")
        sys.argv.append("./")
        sys.argv.append("./output_test/demo")
        sys.argv.append("-pk")
        sys.argv.append("./rsa_private_key2048.pem")
        main()
        output = "./output_test/demo"
        pkg_re = os.path.exists(output)
        shutil.rmtree("./output_test")
        self.assertEqual(pkg_re, False)
        clear_resource()
        if os.path.exists("./rsa_private_key2048.pem"):
            os.remove("./rsa_private_key2048.pem")

    def test_get_update_info_return(self):
        """
        get_update_info, return False
        :return:
        """
        create_input_package(
            "test_target_package_miss_version_list", package_type="source",
            is_miss_version_list=True)
        if not os.path.exists("./output_test"):
            os.mkdir("./output_test")
        sys.argv.clear()
        sys.argv.append("build_update.py")
        sys.argv.append(
            "./test_target_package_miss_version_list.zip")
        sys.argv.append("./output_test/demo")
        sys.argv.append("-pk")
        sys.argv.append("./rsa_private_key2048.pem")
        main()
        output = "./output_test/demo"
        pkg_re = os.path.exists(output)
        shutil.rmtree("./output_test")
        self.assertEqual(pkg_re, False)
        clear_resource()
        clear_package("test_target_package_miss_version_list")

    def test_build_update_package(self):
        """
        build_update_package, return False
        :return:
        """
        create_input_package(
            "test_target_package_miss_updater_binary", package_type="source",
            is_miss_updater_binary=True)
        if not os.path.exists("./output_test"):
            os.mkdir("./output_test")
        sys.argv.clear()
        sys.argv.append("build_update.py")
        sys.argv.append(
            "./test_target_package_miss_updater_binary.zip")
        sys.argv.append("./output_test/")
        sys.argv.append("-pk")
        sys.argv.append("./rsa_private_key2048.pem")
        main()
        output = "./output_test/"
        pkg_re = os.path.exists(output)
        shutil.rmtree("./output_test")
        self.assertEqual(pkg_re, True)
        clear_resource()
        clear_package("test_target_package_miss_updater_binary")

    def test_on_server(self):
        """
        Signing on server.
        :return:
        """
        create_input_package(
            "test_target_package_on_server", package_type="source")
        if not os.path.exists("./output_test"):
            os.mkdir("./output_test")
        sys.argv.clear()
        sys.argv.append("build_update.py")
        sys.argv.append(
            "./test_target_package_on_server.zip")
        sys.argv.append("./output_test/demo")
        sys.argv.append("-pk")
        sys.argv.append("ON_SERVER")
        main()
        output = "./output_test/demo"
        pkg_re = os.path.exists(output)
        shutil.rmtree("./output_test")
        self.assertEqual(pkg_re, True)
        clear_resource()
        clear_package("test_target_package_on_server")

    def test_private_key_check(self):
        """
        private_key_check, check private key param.
        :return:
        """
        check_re = private_key_check("test_private_key_check")
        self.assertEqual(check_re, False)
