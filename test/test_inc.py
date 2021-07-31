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

from blocks_manager import BlocksManager
from transfers_manager import ActionInfo
from transfers_manager import ActionType


class TestUtils(unittest.TestCase):

    def setUp(self):
        print("set up")

    def tearDown(self):
        print("tear down")

    def test_blocks_manager(self):
        """
        Cases for BlocksManager
        :return:
        """
        bm1 = BlocksManager("5-10")
        bm2 = BlocksManager("5-9")
        check_re = bm1 == bm2
        self.assertEqual(check_re, False)

        check_re2 = bm1.get_map_within(bm2).range_data
        self.assertEqual(check_re2, (0, 5))

    def test_action_info(self):
        """
        Cases for ActionInfo
        :return:
        """
        bm1 = BlocksManager("5-10")
        bm2 = BlocksManager("5-9")
        action_info = ActionInfo(
            ActionType.NEW, "test.txt", "test.txt", bm1, bm2)
        check_re = action_info.net_stash_change()
        self.assertEqual(check_re, 0)
