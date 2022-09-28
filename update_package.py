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
import binascii
import copy
import os
import subprocess
import tempfile
import time
import collections as collect
import enum
import ctypes
import zipfile

from log_exception import UPDATE_LOGGER
from script_generator import create_script
from utils import sign_package
from utils import HASH_CONTENT_LEN_DICT
from utils import OPTIONS_MANAGER
from utils import REGISTER_SCRIPT_FILE_NAME
from utils import ON_SERVER
from utils import SCRIPT_KEY_LIST
from utils import EXTEND_OPTIONAL_COMPONENT_LIST
from utils import COMPONENT_INFO_INNIT
from utils import UPDATE_EXE_FILE_NAME
from utils import TOTAL_SCRIPT_FILE_NAME
from utils import EXTEND_COMPONENT_LIST
from utils import LINUX_HASH_ALGORITHM_DICT
from utils import BUILD_TOOLS_FILE_NAME
from utils import SIGN_PACKAGE_EVENT
from create_update_package import CreatePackage
from create_update_package import SIGN_ALGO_RSA
from create_update_package import SIGN_ALGO_PSS

IS_DEL = 0
SIGNING_LENGTH_256 = 256
DIGEST_LEN = 32
HASH_VALUE_MAX_LEN = 128


class SignMethod(enum.Enum):
    RSA = 1
    ECC = 2


class PkgHeader(ctypes.Structure):
    _fields_ = [("digest_method", ctypes.c_ubyte),
                ("sign_method", ctypes.c_ubyte),
                ("pkg_type", ctypes.c_ubyte),
                ("pkg_flags", ctypes.c_ubyte),
                ("entry_count", ctypes.c_int),
                ("update_file_version", ctypes.c_int),
                ("product_update_id", ctypes.c_char_p),
                ("software_version", ctypes.c_char_p),
                ("date", ctypes.c_char_p),
                ("time", ctypes.c_char_p),
                ("describe_package_id", ctypes.c_char_p)]


class PkgComponent(ctypes.Structure):
    _fields_ = [("digest", ctypes.c_ubyte * DIGEST_LEN),
                ("file_path", ctypes.c_char_p),
                ("component_addr", ctypes.c_char_p),
                ("version", ctypes.c_char_p),
                ("size", ctypes.c_int),
                ("id", ctypes.c_int),
                ("original_size", ctypes.c_int),
                ("res_type", ctypes.c_ubyte),
                ("type", ctypes.c_ubyte),
                ("flags", ctypes.c_ubyte)]


class SignInfo(ctypes.Structure):
    _fields_ = [("sign_offset", ctypes.c_int),
                ("hash_len", ctypes.c_int),
                ("hash_code", ctypes.c_ubyte * (HASH_VALUE_MAX_LEN + 1))]


def create_update_bin():
    """
    Call the interface to generate the update.bin file.
    :return update_bin_obj: Update file object.
                            If exception occurs, return False.
    """
    update_bin_obj = tempfile.NamedTemporaryFile(
        dir=OPTIONS_MANAGER.update_package, prefix="update_bin-")

    head_value_list = OPTIONS_MANAGER.head_info_list
    component_dict = OPTIONS_MANAGER.component_info_dict
    full_image_file_obj_list = OPTIONS_MANAGER.full_image_file_obj_list
    full_img_list = OPTIONS_MANAGER.full_img_list
    incremental_img_list = OPTIONS_MANAGER.incremental_img_list
    incremental_image_file_obj_list = \
        OPTIONS_MANAGER.incremental_image_file_obj_list

    all_image_file_obj_list = \
        incremental_image_file_obj_list + full_image_file_obj_list
    if not OPTIONS_MANAGER.not_l2:
        if OPTIONS_MANAGER.partition_file_obj is not None:
            all_image_name = \
                EXTEND_COMPONENT_LIST + EXTEND_OPTIONAL_COMPONENT_LIST + \
                incremental_img_list + full_img_list
        else:
            all_image_name = \
                EXTEND_COMPONENT_LIST + incremental_img_list + full_img_list
    else:
        all_image_name = \
            incremental_img_list + full_img_list
    sort_component_dict = collect.OrderedDict()
    for each_image_name in all_image_name:
        sort_component_dict[each_image_name] = \
            component_dict.get(each_image_name)
    component_dict = copy.deepcopy(sort_component_dict)
    head_list = get_head_list(len(component_dict), head_value_list)

    component_list = get_component_list(
        all_image_file_obj_list, component_dict)

    save_patch = update_bin_obj.name.encode("utf-8")
    if OPTIONS_MANAGER.private_key == ON_SERVER:
        private_key = "./update_package.py"
    else:
        private_key = OPTIONS_MANAGER.private_key.encode("utf-8")

    if OPTIONS_MANAGER.not_l2:
        sign_algo = SIGN_ALGO_PSS
    else:
        sign_algo = SIGN_ALGO_RSA
    
    # create bin
    package = CreatePackage(head_list, component_list, save_patch,
        OPTIONS_MANAGER.private_key)
    if not package.create_package():
        UPDATE_LOGGER.print_log(
            "Create update package .bin failed!", UPDATE_LOGGER.ERROR_LOG)
        return False
    if not package.sign(sign_algo):
        UPDATE_LOGGER.print_log(".bin package signing failed", UPDATE_LOGGER.ERROR_LOG)
        return False

    UPDATE_LOGGER.print_log(
        "Create update package .bin complete! path: %s" % update_bin_obj.name)
    return update_bin_obj


def get_component_list(all_image_file_obj_list, component_dict):
    """
    Get the list of component information according to
    the component information structure.
    :param all_image_file_obj_list: all image object file list
    :param component_dict: Component information content dict
    :return component_list: List of component information.
                            If exception occurs, return False.
    """
    pkg_components = PkgComponent * len(component_dict)
    component_list = pkg_components()
    if not OPTIONS_MANAGER.not_l2:
        if OPTIONS_MANAGER.partition_file_obj is not None:
            extend_component_list = \
                EXTEND_COMPONENT_LIST + EXTEND_OPTIONAL_COMPONENT_LIST
            extend_path_list = [OPTIONS_MANAGER.version_mbn_file_path,
                                OPTIONS_MANAGER.board_list_file_path,
                                OPTIONS_MANAGER.partition_file_obj.name]
        else:
            extend_component_list = EXTEND_COMPONENT_LIST
            extend_path_list = [OPTIONS_MANAGER.version_mbn_file_path,
                                OPTIONS_MANAGER.board_list_file_path]
    else:
        extend_component_list = []
        extend_path_list = []
    idx = 0
    for key, component in component_dict.items():
        if idx < len(extend_component_list):
            file_path = extend_path_list[idx]
        else:
            file_path = \
                all_image_file_obj_list[idx - len(extend_component_list)].name
        digest = get_hash_content(file_path, OPTIONS_MANAGER.hash_algorithm)
        if not digest:
            return
        if component is None:
            component = copy.copy(COMPONENT_INFO_INNIT)
            component[0] = key
        component_list[idx].digest = (ctypes.c_ubyte * 32).from_buffer_copy(
            binascii.a2b_hex(digest.encode('utf-8')))
        component_list[idx].file_path = file_path.encode("utf-8")
        if not OPTIONS_MANAGER.not_l2:
            component_list[idx].component_addr = \
                ('/%s' % component[0]).encode("utf-8")
        else:
            component_list[idx].component_addr = \
                ('%s' % component[0]).encode("utf-8")
        component_list[idx].version = component[4].encode("utf-8")
        component_list[idx].size = os.path.getsize(file_path)
        component_list[idx].id = int(component[1])
        if component[3] == 1:
            component_list[idx].original_size = os.path.getsize(file_path)
        else:
            component_list[idx].original_size = 0
        component_list[idx].res_type = int(component[2])
        component_list[idx].type = int(component[3])
        component_list[idx].flags = IS_DEL

        idx += 1
    return component_list


def get_head_list(component_count, head_value_list):
    """
    According to the header structure, get the list of HEAD headers.
    :param component_count: number of components
    :param head_value_list: list of header values
    :return head_list: header list
    """
    head_list = PkgHeader()
    if OPTIONS_MANAGER.signing_length != SIGNING_LENGTH_256:
        # PKG_DIGEST_TYPE_SHA384   3,use sha384
        head_list.digest_method = 3
    else:
        # PKG_DIGEST_TYPE_SHA256   2,use sha256
        head_list.digest_method = 2
    if OPTIONS_MANAGER.private_key == ON_SERVER:
        head_list.sign_method = 0
    else:
        if OPTIONS_MANAGER.signing_algorithm == "ECC":
            # signing algorithm use ECC
            head_list.sign_method = SignMethod.ECC.value
        else:
            # signing algorithm use RSA
            head_list.sign_method = SignMethod.RSA.value
    head_list.pkg_type = 1
    if OPTIONS_MANAGER.not_l2:
        head_list.pkg_flags = 1
    else:
        head_list.pkg_flags = 0
    head_list.entry_count = component_count
    head_list.update_file_version = int(head_value_list[0])
    head_list.product_update_id = head_value_list[1].encode("utf-8")
    head_list.software_version = head_value_list[2].encode("utf-8")
    head_list.date = head_value_list[3].encode("utf-8")
    head_list.time = head_value_list[4].encode("utf-8")
    head_list.describe_package_id = ctypes.c_char_p("update/info.bin".encode())
    return head_list


def get_tools_component_list(count, opera_script_dict):
    """
    Get the list of component information according to
    the component information structure.
    :param count: number of components
    :param opera_script_dict: script file name and path dict
    :return component_list: list of component information.
                            If exception occurs, return False.
    """
    pkg_components = PkgComponent * count
    component_list = pkg_components()
    component_value_list = list(opera_script_dict.keys())
    component_num = 0
    for i, component in enumerate(component_value_list):
        component_list[i].file_path = component.encode("utf-8")
        component_list[i].component_addr = \
            (opera_script_dict[component]).encode("utf-8")
        component_num += 1
    return component_list, component_num


def get_tools_head_list(component_count):
    """
    According to the header structure, get the list of HEAD headers.
    :param component_count: number of components
    :return head_list: header list
    """
    head_list = PkgHeader()
    head_list.digest_method = 0
    head_list.sign_method = 0
    head_list.pkg_type = 2
    head_list.pkg_flags = 0
    head_list.entry_count = component_count
    return head_list


def get_signing_from_server(package_path, hash_algorithm, hash_code=None):
    """
    Server update package signature requires the vendor to
    implement its own service signature interface, as shown below:
    ip = ""
    user_name = ""
    pass_word = ""
    signe_jar = ""
    signing_config = [signe_jar, ip, user_name, pass_word,
                      hash_code, hash_algorithm]
    cmd = ' '.join(signing_config)
    subprocess.Popen(
        cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    :param package_path: update package file path
    :param hash_algorithm: hash algorithm
    :param hash_code: hash code
    :return:
    """
    UPDATE_LOGGER.print_log("Signing %s, hash algorithm is: %s, "
                            "Signing hash code: %s" %
                            (package_path, hash_algorithm, hash_code))
    signing_content = ""
    return signing_content.encode()


def create_build_tools_zip():
    """
    Create the update package file.
    :param lib: lib object
    :return:
    """
    opera_script_file_name_dict = OPTIONS_MANAGER.opera_script_file_name_dict
    tmp_dict = {}
    for each in SCRIPT_KEY_LIST:
        tmp_dict[each] = []
    if opera_script_file_name_dict == tmp_dict:
        UPDATE_LOGGER.print_log(
            "Script dict is null!",
            log_type=UPDATE_LOGGER.ERROR_LOG)
        return False
    count = 0
    opera_script_dict = {}
    for each_value in opera_script_file_name_dict.values():
        for each in each_value:
            opera_script_dict[each[1].name] = each[0]
            count += 1
    # other_file_count --> 1(updater_binary) + 1(loadScript.us)
    other_file_count = 2
    count += other_file_count
    if OPTIONS_MANAGER.register_script_file_obj is not None:
        count += 1
    head_list = get_tools_head_list(count)
    component_list, num = \
        get_tools_component_list(count, opera_script_dict)
    total_script_file_obj = OPTIONS_MANAGER.total_script_file_obj
    register_script_file_obj = OPTIONS_MANAGER.register_script_file_obj
    update_exe_path = os.path.join(OPTIONS_MANAGER.target_package_dir,
                                   UPDATE_EXE_FILE_NAME)
    if not os.path.exists(update_exe_path):
        UPDATE_LOGGER.print_log(
            "updater_binary file does not exist!path: %s" % update_exe_path,
            log_type=UPDATE_LOGGER.ERROR_LOG)
        return False

    file_obj = tempfile.NamedTemporaryFile(
        dir=OPTIONS_MANAGER.update_package, prefix="build_tools-")
    zip_file = zipfile.ZipFile(file_obj.name, 'w', zipfile.ZIP_DEFLATED)
    # add opera_script to build_tools.zip
    for key, value in opera_script_dict.items():
        zip_file.write(key, value)

    # add update_binary to build_tools.zip
    zip_file.write(update_exe_path, UPDATE_EXE_FILE_NAME)

    # add loadScript to build_tools.zip
    zip_file.write(total_script_file_obj.name, TOTAL_SCRIPT_FILE_NAME)

    if OPTIONS_MANAGER.register_script_file_obj is not None:
        zip_file.write(register_script_file_obj.name, REGISTER_SCRIPT_FILE_NAME)
    zip_file.close()

    return file_obj


def build_update_package(no_zip, update_package, prelude_script,
                         verse_script, refrain_script, ending_script):
    """
    Create the update package file.
    :param no_zip: no zip
    :param update_package: update package path
    :param prelude_script: prelude object
    :param verse_script: verse object
    :param refrain_script: refrain object
    :param ending_script: ending object
    :return: If exception occurs, return False.
    """
    update_bin_obj = create_update_bin()
    if update_bin_obj:
        OPTIONS_MANAGER.update_bin_obj = update_bin_obj
    else:
        return False

    if OPTIONS_MANAGER.sd_card :
        package_type = "sd"
    elif OPTIONS_MANAGER.source_package :
        package_type = "diff"
    else :
        package_type = "full"
    if OPTIONS_MANAGER.not_l2:
        update_file_name = ''.join(
            ["updater_", OPTIONS_MANAGER.target_package_version.replace(" ", "_")])
    else :
        update_file_name = ''.join(
            ["updater_", package_type])
            
    if not no_zip:
        update_package_path = os.path.join(
            update_package, '%s_unsigned.zip' % update_file_name)
        OPTIONS_MANAGER.update_package_file_path = update_package_path

        create_script(prelude_script, verse_script,
                      refrain_script, ending_script)

        build_tools_zip_obj = create_build_tools_zip()
        if build_tools_zip_obj is False:
            UPDATE_LOGGER.print_log(
                "Create build tools zip failed!",
                log_type=UPDATE_LOGGER.ERROR_LOG)
            return False
        OPTIONS_MANAGER.build_tools_zip_obj = build_tools_zip_obj

        zip_file = zipfile.ZipFile(update_package_path, 'w', zipfile.ZIP_DEFLATED, allowZip64=True)
        # add update.bin to update package
        zip_file.write(OPTIONS_MANAGER.update_bin_obj.name, "update.bin")
        # add build_tools.zip to update package
        zip_file.write(OPTIONS_MANAGER.build_tools_zip_obj.name, BUILD_TOOLS_FILE_NAME)
        zip_file.close()

        signed_package = os.path.join(
            update_package, "%s.zip" % update_file_name)
        OPTIONS_MANAGER.signed_package = signed_package
        if os.path.exists(signed_package):
            os.remove(signed_package)

        sign_ota_package = \
            OPTIONS_MANAGER.init.invoke_event(SIGN_PACKAGE_EVENT)
        if sign_ota_package:
            sign_result = sign_ota_package()
        else:
            sign_result = sign_package()

        if not sign_result:
            UPDATE_LOGGER.print_log("Sign ota package fail", UPDATE_LOGGER.ERROR_LOG)
            return False
        if os.path.exists(update_package_path):
            os.remove(update_package_path)
    else:
        update_package_path = os.path.join(
            update_package, '%s.bin' % update_file_name)
        if os.path.exists(update_package_path):
            os.remove(update_package_path)
        OPTIONS_MANAGER.update_package_file_path = update_package_path
        with open(OPTIONS_MANAGER.update_bin_obj.name, 'rb') as r_f:
            content = r_f.read()
        with open(update_package_path, 'wb') as w_f:
            w_f.write(content)
    return True


def get_hash_content(file_path, hash_algorithm):
    """
    Use SHA256SUM to get the hash value of the file.
    :param file_path : file path
    :param hash_algorithm: hash algorithm
    :return hash_content: hash value
    """
    try:
        cmd = [LINUX_HASH_ALGORITHM_DICT[hash_algorithm], file_path]
    except KeyError:
        UPDATE_LOGGER.print_log(
            "Unsupported hash algorithm! %s" % hash_algorithm,
            log_type=UPDATE_LOGGER.ERROR_LOG)
        return False
    if not os.path.exists(file_path):
        UPDATE_LOGGER.print_log(
            "%s failed!" % LINUX_HASH_ALGORITHM_DICT[hash_algorithm],
            UPDATE_LOGGER.ERROR_LOG)
        raise RuntimeError
    process_obj = subprocess.Popen(
        cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    process_obj.wait()
    hash_content = \
        process_obj.stdout.read().decode(encoding='gbk').split(' ')[0]
    if len(hash_content) != HASH_CONTENT_LEN_DICT.get(hash_algorithm):
        UPDATE_LOGGER.print_log(
            "Get hash content failed! The length of the hash_content is 0!",
            UPDATE_LOGGER.ERROR_LOG)
        raise RuntimeError
    if process_obj.returncode == 0:
        UPDATE_LOGGER.print_log(
            "Get hash content success! path: %s" % file_path)
    return hash_content
