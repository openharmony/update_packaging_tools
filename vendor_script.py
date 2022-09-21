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
import tempfile

from log_exception import UPDATE_LOGGER
from script_generator import EndingScript
from script_generator import RefrainScript
from script_generator import VerseScript
from script_generator import PreludeScript
from utils import SCRIPT_KEY_LIST
from utils import OPTIONS_MANAGER
from utils import REGISTER_SCRIPT_FILE_NAME


def create_vendor_script_class():
    """
    Obtain the extended script objects of the vendor. By default,
    the return value is [None] * len(SCRIPT_KEY_LIST).
    SCRIPT_KEY_LIST is the stage list in Opera mode.
    If needed, rewrite this function to create a Vendor{Opera}Script object
    class and return the object. Sample code is as follows:

    ExtensionCmdRegister().generate_register_cmd_script()
    prelude_script = VendorPreludeScript()
    verse_script = VendorVerseScript()
    refrain_script = VendorRefrainScript()
    ending_script = VendorEndingScript()
    opera_obj_list = [prelude_script, verse_script,
                    refrain_script, ending_script]
    :return opera_obj_list: {Opera}script object list
    """
    opera_obj_list = [None] * len(SCRIPT_KEY_LIST)
    return opera_obj_list


class VendorPreludeScript(PreludeScript):
    def __init__(self):
        super().__init__()


class VendorVerseScript(VerseScript):
    def __init__(self):
        super().__init__()


class VendorRefrainScript(RefrainScript):
    def __init__(self):
        super().__init__()


class VendorEndingScript(EndingScript):
    def __init__(self):
        super().__init__()


class ExtensionCmdRegister:
    def __init__(self):
        """
        ExtensionCmdRegister for vendor extended command registration.
        self.__cmd_in_so_dict needs the dict of extension command and
        the corresponding so path.
        like: self.__cmd_in_so_dict = \
                {"/data/updater/libtest.z.so":
                    ["extension_cmd1", "extension_cmd2"],
                "/data/updater/libtest2.z.so": ["extension_cmd3"],
                }
        """
        self.__cmd_in_so_dict = {}


    def generate_register_cmd_script(self):
        """
        Generate the register script.
        """
        if len(self.__cmd_in_so_dict.keys()) != 0:
            content_list = []
            for each_so_path, each_cmds_list in self.__cmd_in_so_dict.items():
                for each_cmd in each_cmds_list:
                    each_content = \
                        'RegisterCmder("%s" , ' \
                        '"%s");' % (each_cmd, each_so_path)
                    content_list.append(each_content)
            register_script = tempfile.NamedTemporaryFile(mode='w+')
            register_script.write('\n'.join(content_list))
            register_script.seek(0)
            OPTIONS_MANAGER.register_script_file_obj = register_script
            UPDATE_LOGGER.print_log("%s generation complete!" %
                                    REGISTER_SCRIPT_FILE_NAME)
