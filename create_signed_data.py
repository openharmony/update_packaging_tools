#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (c) 2023 Huawei Device Co., Ltd.
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

import hashlib
from base64 import b64encode
from build_pkcs7 import BLOCK_SIZE, sign_digest
from log_exception import UPDATE_LOGGER
from utils import OPTIONS_MANAGER


def sign_func_sha256(sign_file, private_key_file):
    """
    sign one file with private key
    :param sign_file: path of file ready to be signed
    :param private_key_file: private key path, ex. rsa_private_key2048.pem
    :return: base64 code of the signature
    """
    hash_sha256 = hashlib.sha256()
    with open(sign_file, 'rb') as file:
        chunk = file.read(BLOCK_SIZE)
        while chunk:
            hash_sha256.update(chunk)
            chunk = file.read(BLOCK_SIZE)
    signature = sign_digest(hash_sha256.digest(), private_key_file)
    if signature == False:
        UPDATE_LOGGER.print_log("sign digest failed", log_type=UPDATE_LOGGER.ERROR_LOG)
        return ""
    return str(b64encode(signature).decode("ascii"))


def generate_signed_data(file_lists, sign_func, private_key_file):
    """
    get hash signed data of file lists, hash signed data format:
    Name: build_tools/updater_binary
    signed-data: xxxxxxx

    Name: build_tools/updater_binary
    signed-data: xxxxxxx

    ....
    :param file_lists: path list of file ready to be signed, list item contains file_path and name_in_signed_data
    :param sign_func: signature function, ex. sign_func_sha256
    :param private_key_file: private key path, ex. rsa_private_key2048.pem
    :return: hash signed data of the file_lists
    """
    max_file_num = 32
    if not sign_func:
        UPDATE_LOGGER.print_log("please provide a sign function", log_type=UPDATE_LOGGER.ERROR_LOG)
        return ""

    if len(file_lists) > max_file_num:
        UPDATE_LOGGER.print_log("signed file can't be more than %d" % max_file_num,
            log_type=UPDATE_LOGGER.ERROR_LOG)
        return ""
    sign_res_list = []
    for file, name in file_lists:
        sign_res = sign_func(file, private_key_file)
        if sign_res == "":
            UPDATE_LOGGER.print_log("sign file {} failed".format(name), log_type=UPDATE_LOGGER.ERROR_LOG)
            return ""
        sign_res_list += ["Name: {}\nsigned-data: {}\n".format(name, sign_res)]
    return "\n".join(sign_res_list)


def generate_signed_data_default(file_lists):
    return generate_signed_data(file_lists, sign_func_sha256, OPTIONS_MANAGER.private_key)