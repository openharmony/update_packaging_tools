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

from log_exception import UPDATE_LOGGER
from log_exception import handle_exception
from log_exception import VendorExpandError
from script_generator import Script


class TestLogException(unittest.TestCase):

    def setUp(self):
        print("set up")

    def tearDown(self):
        print("tear down")

    def test_print_log_error_type(self):
        """
        print_log, Input exception type
        :return:
        """
        UPDATE_LOGGER.print_log("Test log!", log_type="TEST_TYPE")

    def test_handle_exception1(self):
        """
        handle_exception1, Exception occurred.
        :return:
        """
        vendor_error = VendorExpandError(type(Script), 'test_func')
        handle_exception(VendorExpandError, None, None)
        vendor_error.__str__()

    def test_handle_exception2(self):
        """
        handle_exception2, Exception occurred.
        :return:
        """
        handle_exception(KeyboardInterrupt, None, None)
