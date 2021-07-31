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

import unittest

from utils import SCRIPT_KEY_LIST
from utils import clear_resource
from vendor_script import create_vendor_script_class
from vendor_script import VendorPreludeScript
from vendor_script import VendorVerseScript
from vendor_script import VendorRefrainScript
from vendor_script import VendorEndingScript
from vendor_script import ExtensionCmdRegister


class TestVendorScript(unittest.TestCase):

    def setUp(self):
        print("set up")

    def tearDown(self):
        print("tear down")

    def test_vendor_script(self):
        opera_obj_list = create_vendor_script_class()
        TestVendorPreludeScript()
        test_vendor_verse_script = TestVendorVerseScript()
        test_vendor_verse_script.set_status("1")
        test_vendor_verse_script.get_status()
        test_vendor_verse_script.reboot_now()
        TestVendorRefrainScript()
        TestVendorEndingScript()

        ExtensionCmdRegister().generate_register_cmd_script()
        self.assertEqual(opera_obj_list, [None] * len(SCRIPT_KEY_LIST))
        clear_resource()


class TestVendorPreludeScript(VendorPreludeScript):
    def __init__(self):
        super().__init__()


class TestVendorVerseScript(VendorVerseScript):
    def __init__(self):
        super().__init__()


class TestVendorRefrainScript(VendorRefrainScript):
    def __init__(self):
        super().__init__()


class TestVendorEndingScript(VendorEndingScript):
    def __init__(self):
        super().__init__()
