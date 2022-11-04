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

"""
The tool for making updater package.

positional arguments:
  target_package        Target package file path.
  update_package        Update package file path.

optional arguments:
  -h, --help            show this help message and exit
  -s SOURCE_PACKAGE, --source_package SOURCE_PACKAGE
                        Source package file path.
  -nz, --no_zip         No zip mode,
                        which means to output the update package without zip.
  -pf PARTITION_FILE, --partition_file PARTITION_FILE
                        Variable partition mode, Partition list file path.
  -sa {ECC,RSA}, --signing_algorithm {ECC,RSA}
                        The signing algorithms
                        supported by the tool include ['ECC', 'RSA'].
  -ha {sha256,sha384}, --hash_algorithm {sha256,sha384}
                        The hash algorithms
                        supported by the tool include ['sha256', 'sha384'].
  -pk PRIVATE_KEY, --private_key PRIVATE_KEY
                        Private key file path.
  -nl2, --not_l2        Not L2 mode, Distinguish between L1 and L2.
  -sl {256,384}, --signing_length {256,384}
                        The signing content length
                        supported by the tool include ['256', '384'].
  -xp, --xml_path       XML file path.
  -sc, --sd_card        SD Card mode, Create update package for SD Card.
"""
import filecmp
import os
import sys
import argparse
import subprocess
import tempfile
import hashlib
import xmltodict
import patch_package_process

from gigraph_process import GigraphProcess
from image_class import FullUpdateImage
from image_class import IncUpdateImage
from transfers_manager import TransfersManager
from log_exception import UPDATE_LOGGER
from script_generator import PreludeScript
from script_generator import VerseScript
from script_generator import RefrainScript
from script_generator import EndingScript
from update_package import build_update_package
from unpack_updater_package import UnpackPackage
from utils import OPTIONS_MANAGER
from utils import UPDATER_CONFIG
from utils import parse_partition_file_xml
from utils import unzip_package
from utils import clear_resource
from utils import PRODUCT
from utils import XML_FILE_PATH
from utils import get_update_info
from utils import SCRIPT_KEY_LIST
from utils import PER_BLOCK_SIZE
from utils import E2FSDROID_PATH
from utils import MAXIMUM_RECURSION_DEPTH
from utils import VERSE_SCRIPT_EVENT
from utils import INC_IMAGE_EVENT
from utils import DIFF_EXE_PATH
from utils import get_update_config_softversion
from vendor_script import create_vendor_script_class

sys.setrecursionlimit(MAXIMUM_RECURSION_DEPTH)


def type_check(arg):
    """
    Argument check, which is used to check whether the specified arg is a file.
    :param arg: the arg to check
    :return:  Check result, which is False if the arg is invalid.
    """
    if arg is not None and not os.path.exists(arg):
        UPDATE_LOGGER.print_log(
            "FileNotFoundError, path: %s" % arg, UPDATE_LOGGER.ERROR_LOG)
        return False
    return arg


def private_key_check(arg):
    """
    Argument check, which is used to check whether
    the specified arg is a private_key.
    :param arg:  The arg to check.
    :return: Check result, which is False if the arg is invalid.
    """
    if arg != "ON_SERVER" and not os.path.isfile(arg):
        UPDATE_LOGGER.print_log(
            "FileNotFoundError, path: %s" % arg, UPDATE_LOGGER.ERROR_LOG)
        return False
    return arg


def check_update_package(arg):
    """
    Argument check, which is used to check whether
    the update package path exists.
    :param arg: The arg to check.
    :return: Check result
    """
    make_dir_path = None
    if os.path.exists(arg):
        if os.path.isfile(arg):
            UPDATE_LOGGER.print_log(
                "Update package must be a dir path, not a file path. "
                "path: %s" % arg, UPDATE_LOGGER.ERROR_LOG)
            return False
    else:
        try:
            UPDATE_LOGGER.print_log(
                "Update package path does  not exist. The dir will be created!"
                "path: %s" % arg, UPDATE_LOGGER.WARNING_LOG)
            os.makedirs(arg)
            make_dir_path = arg
        except OSError:
            UPDATE_LOGGER.print_log(
                "Make update package path dir failed! "
                "path: %s" % arg, UPDATE_LOGGER.ERROR_LOG)
            return False
    if make_dir_path is not None:
        OPTIONS_MANAGER.make_dir_path = make_dir_path
    OPTIONS_MANAGER.update_package = arg
    return arg


def unpack_check(arg):
    """
    Argument check, which is used to check whether
    the update package path exists.
    :param arg: The arg to check.
    :return: Check result
    """
    unpack_package = os.path.join(OPTIONS_MANAGER.update_package, arg)
    if not os.path.isfile(unpack_package):
        UPDATE_LOGGER.print_log(
            "FileNotFoundError, path: %s" % unpack_package, UPDATE_LOGGER.ERROR_LOG)
        OPTIONS_MANAGER.unpack_package_path = None
        return False
    OPTIONS_MANAGER.unpack_package_path = unpack_package
    return arg


def create_entrance_args():
    """
    Arguments for the tool to create an update package
    :return source_package : source version package
            target_package : target version package
            update_package : update package output path
            no_zip : whether to enable the update package zip function.
            partition_file : partition table XML file
            signing_algorithm : signature algorithm (ECC and RSA (default))
            private_key : path of the private key file
    """
    parser = OPTIONS_MANAGER.parser
    parser.description = "Tool for creating update package."
    parser.add_argument("-unpack", "--unpack_package", type=unpack_check,
                        default=None, help="Unpack updater package.")
    parser.add_argument("-s", "--source_package", type=type_check,
                        default=None, help="Source package file path.")
    parser.add_argument("target_package", type=type_check,
                        help="Target package file path.")
    parser.add_argument("update_package", type=check_update_package,
                        help="Update package file path.")
    parser.add_argument("-nz", "--no_zip", action='store_true',
                        help="No zip mode, Output update package without zip.")
    parser.add_argument("-pf", "--partition_file", default=None,
                        help="Variable partition mode, "
                             "Partition list file path.")
    parser.add_argument("-sa", "--signing_algorithm", default='RSA',
                        choices=['ECC', 'RSA'],
                        help="The signing algorithm "
                             "supported by the tool include ['ECC', 'RSA'].")
    parser.add_argument("-ha", "--hash_algorithm", default='sha256',
                        choices=['sha256', 'sha384'],
                        help="The hash algorithm "
                             "supported by the tool include "
                             "['sha256', 'sha384'].")
    parser.add_argument("-pk", "--private_key", type=private_key_check,
                        default=None, help="Private key file path.")
    parser.add_argument("-nl2", "--not_l2", action='store_true',
                        help="Not L2 mode, Distinguish between L1 and L2.")
    parser.add_argument("-sl", "--signing_length", default='256',
                        choices=['256', '384'],
                        help="The signing content length "
                             "supported by the tool include "
                             "['256', '384'].")
    parser.add_argument("-xp", "--xml_path", type=private_key_check,
                        default=None, help="XML file path.")
    parser.add_argument("-sc", "--sd_card", action='store_true',
                        help="SD Card mode, "
                             "Create update package for SD Card.")


def parse_args():
    args = OPTIONS_MANAGER.parser.parse_args()
    OPTIONS_MANAGER.source_package = args.source_package
    OPTIONS_MANAGER.target_package = args.target_package
    OPTIONS_MANAGER.update_package = args.update_package
    OPTIONS_MANAGER.no_zip = args.no_zip
    OPTIONS_MANAGER.partition_file = args.partition_file
    OPTIONS_MANAGER.signing_algorithm = args.signing_algorithm
    OPTIONS_MANAGER.hash_algorithm = args.hash_algorithm
    OPTIONS_MANAGER.private_key = args.private_key
    OPTIONS_MANAGER.not_l2 = args.not_l2
    OPTIONS_MANAGER.signing_length = int(args.signing_length)
    OPTIONS_MANAGER.xml_path = args.xml_path
    OPTIONS_MANAGER.sd_card = args.sd_card


def get_args():
    ret_args = \
        [OPTIONS_MANAGER.source_package,
        OPTIONS_MANAGER.target_package,
        OPTIONS_MANAGER.update_package,
        OPTIONS_MANAGER.no_zip,
        OPTIONS_MANAGER.not_l2,
        OPTIONS_MANAGER.partition_file,
        OPTIONS_MANAGER.signing_algorithm,
        OPTIONS_MANAGER.hash_algorithm,
        OPTIONS_MANAGER.private_key]
    return ret_args


def get_script_obj():
    """
    Obtain Opera script object
    :return:
    """
    script_obj_list = create_vendor_script_class()
    if script_obj_list == [None] * len(SCRIPT_KEY_LIST):
        prelude_script = PreludeScript()
        verse_script = VerseScript()
        refrain_script = RefrainScript()
        ending_script = EndingScript()

        generate_verse_script = \
            OPTIONS_MANAGER.init.invoke_event(VERSE_SCRIPT_EVENT)
        if generate_verse_script:
            verse_script = generate_verse_script()
    else:
        UPDATE_LOGGER.print_log(
            "Get vendor extension object completed!"
            "The vendor extension script will be generated.")
        prelude_script = script_obj_list[0]
        verse_script = script_obj_list[1]
        refrain_script = script_obj_list[2]
        ending_script = script_obj_list[3]
    return prelude_script, verse_script, refrain_script, ending_script


def get_source_package_path(source_package):
    """
    get_source_package_path.
    :param source_package: source package path
    :return:
    """
    if os.path.isdir(source_package):
        OPTIONS_MANAGER.source_package_dir = source_package
    elif source_package.endswith('.zip'):
        # Decompress the source package.
        tmp_dir_obj, unzip_dir = unzip_package(source_package)
        if tmp_dir_obj is False or unzip_dir is False:
            clear_resource(err_clear=True)
            return False
        OPTIONS_MANAGER.source_package_dir = unzip_dir
        OPTIONS_MANAGER.source_package_temp_obj = tmp_dir_obj
    else:
        UPDATE_LOGGER.print_log("Input Update Package type exception!"
            "path: %s" % source_package, UPDATE_LOGGER.ERROR_LOG)
        clear_resource(err_clear=True)
        return False
    return True


def check_incremental_args(no_zip, partition_file, source_package,
                           incremental_img_list):
    """
    When the incremental list is not empty, incremental processing is required.
    In this case, check related arguments.
    :param no_zip: no zip mode
    :param partition_file:
    :param source_package:
    :param incremental_img_list:
    :return:
    """
    if "boot" in incremental_img_list:
        UPDATE_LOGGER.print_log(
            "boot cannot be incrementally processed!",
            UPDATE_LOGGER.ERROR_LOG)
        clear_resource(err_clear=True)
        return False
    if source_package is None:
        UPDATE_LOGGER.print_log(
            "The source package is missing, "
            "cannot be incrementally processed!",
            UPDATE_LOGGER.ERROR_LOG)
        clear_resource(err_clear=True)
        return False
    if no_zip:
        UPDATE_LOGGER.print_log(
            "No ZIP mode, cannot be incrementally processed!",
            UPDATE_LOGGER.ERROR_LOG)
        clear_resource(err_clear=True)
        return False
    if partition_file is not None:
        UPDATE_LOGGER.print_log(
            "Partition file is not None, "
            "cannot be incrementally processed!",
            UPDATE_LOGGER.ERROR_LOG)
        clear_resource(err_clear=True)
        return False

    if not get_source_package_path(source_package):
        return False
    xml_path = ''
    if OPTIONS_MANAGER.source_package_dir is not False:
        xml_path = os.path.join(OPTIONS_MANAGER.source_package_dir,
                                UPDATER_CONFIG, XML_FILE_PATH)
    if OPTIONS_MANAGER.source_package_dir is False:
        OPTIONS_MANAGER.source_package_temp_obj = None
        OPTIONS_MANAGER.source_package_dir = None
    if os.path.exists(xml_path):
        with open(xml_path, 'r') as xml_file:
            xml_str = xml_file.read()
    else:
        UPDATE_LOGGER.print_log("XML file does not exist! xml path: %s" %
                                xml_path, UPDATE_LOGGER.ERROR_LOG)
        return False
    xml_content_dict = xmltodict.parse(xml_str, encoding='utf-8')
    package_dict = xml_content_dict.get('package', {})
    get_update_config_softversion(OPTIONS_MANAGER.source_package_dir, package_dict.get('head', {}))
    head_dict = package_dict.get('head', {}).get('info')
    OPTIONS_MANAGER.source_package_version = head_dict.get("@softVersion")
    if check_package_version(OPTIONS_MANAGER.target_package_version,
                             OPTIONS_MANAGER.source_package_version) is False:
        clear_resource(err_clear=True)
        return False
    return True


def check_userdata_image():
    """
    Check the userdata image. Updating this image is prohibited.
    :return:
    """
    if 'userdata' in OPTIONS_MANAGER.full_img_list or \
            'userdata' in OPTIONS_MANAGER.incremental_img_list:
        UPDATE_LOGGER.print_log(
            "userdata image does not participate in update!"
            "Please check xml config, path: %s!" %
            os.path.join(OPTIONS_MANAGER.target_package_config_dir,
                         XML_FILE_PATH),
            UPDATE_LOGGER.ERROR_LOG)
        clear_resource(err_clear=True)
        return False
    return True


def check_images_list():
    """
    Check full_img_list and incremental_img_list.
    If their lengths are 0, an error will be logged.
    :return:
    """
    if len(OPTIONS_MANAGER.full_img_list) == 0 and \
            len(OPTIONS_MANAGER.incremental_img_list) == 0:
        UPDATE_LOGGER.print_log(
            "The image list is empty!"
            "Please check xml config, path: %s!" %
            os.path.join(OPTIONS_MANAGER.target_package_config_dir,
                         XML_FILE_PATH),
            UPDATE_LOGGER.ERROR_LOG)
        clear_resource(err_clear=True)
        return False
    return True


def check_target_package_path(target_package):
    """
    Check the target_package path.
    :param target_package: target package path
    :return:
    """
    if os.path.isdir(target_package):
        OPTIONS_MANAGER.target_package_dir = target_package
        temp_dir_list = os.listdir(target_package)
        if UPDATER_CONFIG in temp_dir_list:
            OPTIONS_MANAGER.target_package_config_dir = \
                os.path.join(target_package, UPDATER_CONFIG)
        else:
            UPDATE_LOGGER.print_log(
                "Exception's target package path! path: %s" %
                target_package, UPDATE_LOGGER.ERROR_LOG)
            return False
    elif target_package.endswith('.zip'):
        # Decompress the target package.
        tmp_dir_obj, unzip_dir = unzip_package(target_package)
        if tmp_dir_obj is False or unzip_dir is False:
            clear_resource(err_clear=True)
            return False
        OPTIONS_MANAGER.target_package_dir = unzip_dir
        OPTIONS_MANAGER.target_package_temp_obj = tmp_dir_obj
        OPTIONS_MANAGER.target_package_config_dir = \
            os.path.join(unzip_dir, UPDATER_CONFIG)
    else:
        UPDATE_LOGGER.print_log(
            "Input Update Package type exception! path: %s" %
            target_package, UPDATE_LOGGER.ERROR_LOG)
        clear_resource(err_clear=True)
        return False
    return True


def check_miss_private_key(private_key):
    """
    Check private key.
    :param private_key:
    :return:
    """
    if private_key is None:
        UPDATE_LOGGER.print_log(
            "Private key is None, update package cannot be signed! "
            "Please specify the signature private key by -pk.",
            UPDATE_LOGGER.ERROR_LOG)
        clear_resource(err_clear=True)
        return False
    return True


def check_package_version(target_ver, source_ver):
    """
    target_ver: target version
    source_ver: source version
    return:
    """
    try:
        target_num = ''.join(target_ver.split(' ')[-1].replace('.', ''))
        source_num = ''.join(source_ver.split(' ')[-1].replace('.', ''))
        if int(target_num) <= int(source_num):
            UPDATE_LOGGER.print_log(
                'Target package version %s <= Source package version!'
                'Unable to make updater package!',
                UPDATE_LOGGER.ERROR_LOG)
            return False
    except ValueError:
        UPDATE_LOGGER.print_log('your package version number is not compliant.'
                                'Please check your package version number!',
                                UPDATE_LOGGER.ERROR_LOG)
        return False
    return True


def generate_image_map_file(image_path, map_path, image_name):
    """
    :param image_path: image path
    :param map_path: image map file path
    :param image_name: image name
    :return:
    """
    if not os.path.exists(image_path):
        UPDATE_LOGGER.print_log("The source %s.img file is missing from the"
            "source package, cannot be incrementally processed. ",
            image_name, UPDATE_LOGGER.ERROR_LOG)
        return False

    cmd = \
        [E2FSDROID_PATH, "-B", map_path, "-a", "/%s" % image_name, image_path, "-e"]

    sub_p = subprocess.Popen(
            cmd, shell=False, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
    sub_p.wait()

    if not os.path.exists(map_path):
        UPDATE_LOGGER.print_log("%s generate image map file failed."
                                % image_path)
        return False
    return True


def get_file_sha256(update_package):
    sha256obj = hashlib.sha256()
    maxbuf = 8192
    with open(update_package, 'rb') as package_file:
        while True:
            buf = package_file.read(maxbuf)
            if not buf:
                break
            sha256obj.update(buf)
    hash_value = sha256obj.hexdigest()
    return str(hash_value).upper()


def write_image_patch_script(partition, src_image_path, tgt_image_path,
                             script_check_cmd_list, script_write_cmd_list, verse_script):
    """
    Add command content to the script.
    :param partition: image name
    :param script_check_cmd_list: incremental check command list
    :param script_write_cmd_list: incremental write command list
    :param verse_script: verse script object
    :return:
    """
    src_sha = get_file_sha256(src_image_path)
    src_size = os.path.getsize(src_image_path)
    tgt_sha = get_file_sha256(tgt_image_path)
    tgt_size = os.path.getsize(tgt_image_path)

    sha_check_cmd = verse_script.image_sha_check(partition,
        src_size, src_sha, tgt_size, tgt_sha)

    first_block_check_cmd = verse_script.first_block_check(partition)

    abort_cmd = verse_script.abort(partition)

    cmd = 'if ({sha_check_cmd} != 0)' \
            '{{\n    {abort_cmd}}}\n'.format(
            sha_check_cmd=sha_check_cmd,
            abort_cmd=abort_cmd)

    script_check_cmd_list.append(cmd)

    image_patch_cmd = verse_script.image_patch(partition, os.path.getsize(src_image_path),
        get_file_sha256(src_image_path), os.path.getsize(tgt_image_path),
        get_file_sha256(tgt_image_path))

    cmd = '%s_WRITE_FLAG%s' % (partition, image_patch_cmd)
    script_write_cmd_list.append(cmd)
    return True


def increment_image_diff_processing(
        partition, src_image_path, tgt_image_path,
        script_check_cmd_list, script_write_cmd_list, verse_script):
    """
    Incremental image processing
    :param verse_script: verse script
    :param incremental_img_list: incremental image list
    :param source_package_dir: source package path
    :param target_package_dir: target package path
    :return:
    """
    patch_file_obj = tempfile.NamedTemporaryFile(
            prefix="%s_patch.dat-" % partition, mode='wb')
    OPTIONS_MANAGER.incremental_image_file_obj_list.append(
            patch_file_obj)
    cmd = [DIFF_EXE_PATH]

    cmd.extend(['-s', src_image_path, '-d', tgt_image_path,
                '-p', patch_file_obj.name, '-l', '4096'])
    sub_p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
    try:
        output, _ = sub_p.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        sub_p.kill()

    sub_p.wait()
    if sub_p.returncode != 0:
        raise ValueError(output)
    return write_image_patch_script(partition, src_image_path, tgt_image_path,
        script_check_cmd_list, script_write_cmd_list, verse_script)


def increment_image_processing(
        verse_script, incremental_img_list, source_package_dir,
        target_package_dir):
    """
    Incremental image processing
    :param verse_script: verse script
    :param incremental_img_list: incremental image list
    :param source_package_dir: source package path
    :param target_package_dir: target package path
    :return:
    """
    script_check_cmd_list = []
    script_write_cmd_list = []
    patch_process = None
    block_diff = 0
    for each_img_name in OPTIONS_MANAGER.incremental_img_name_list:
        each_img = each_img_name[:-4]
        each_src_image_path = \
            os.path.join(source_package_dir,
                         '%s.img' % each_img)
        each_src_map_path = \
            os.path.join(source_package_dir,
                         '%s.map' % each_img)
        each_tgt_image_path = \
            os.path.join(target_package_dir,
                         '%s.img' % each_img)
        each_tgt_map_path = \
            os.path.join(target_package_dir,
                         '%s.map' % each_img)

        check_make_map_path(each_img)

        if filecmp.cmp(each_src_image_path, each_tgt_image_path):
            UPDATE_LOGGER.print_log(
                "Source Image is the same as Target Image!"
                "src image path: %s, tgt image path: %s" %
                (each_src_image_path, each_tgt_image_path),
                UPDATE_LOGGER.INFO_LOG)

        src_generate_map = True
        tgt_generate_map = True
        if not os.path.exists(each_src_map_path):
            src_generate_map = generate_image_map_file(each_src_image_path,
                                    each_src_map_path, each_img)
            if not src_generate_map:
                UPDATE_LOGGER.print_log("The source %s.img file"
                        "generate map file failed. " % each_img)

        if not os.path.exists(each_tgt_map_path):
            tgt_generate_map = generate_image_map_file(each_tgt_image_path,
                                    each_tgt_map_path, each_img)
            if not tgt_generate_map:
                UPDATE_LOGGER.print_log("The target %s.img file"
                        "generate map file failed. " % each_img)

        if not src_generate_map or not tgt_generate_map:
            if increment_image_diff_processing(each_img, each_src_image_path, each_tgt_image_path,
                script_check_cmd_list, script_write_cmd_list, verse_script) is True:
                continue
            UPDATE_LOGGER.print_log("increment_image_diff_processing %s failed" % each_img)
            clear_resource(err_clear=True)
            return False

        block_diff += 1
        src_image_class = \
            IncUpdateImage(each_src_image_path, each_src_map_path)
        tgt_image_class = \
            IncUpdateImage(each_tgt_image_path, each_tgt_map_path)
        OPTIONS_MANAGER.src_image = src_image_class
        OPTIONS_MANAGER.tgt_image = tgt_image_class

        inc_image = OPTIONS_MANAGER.init.invoke_event(INC_IMAGE_EVENT)
        if inc_image:
            src_image_class, tgt_image_class = inc_image()

        transfers_manager = TransfersManager(
            each_img, tgt_image_class, src_image_class)
        transfers_manager.find_process_needs()
        actions_list = transfers_manager.get_action_list()

        graph_process = GigraphProcess(actions_list, src_image_class,
                                       tgt_image_class)
        actions_list = graph_process.actions_list
        patch_process = \
            patch_package_process.PatchProcess(
                each_img, tgt_image_class, src_image_class, actions_list)
        patch_process.patch_process()
        patch_process.package_patch_zip.package_patch_zip()
        patch_process.write_script(each_img, script_check_cmd_list,
                                   script_write_cmd_list, verse_script)
    if block_diff > 0:
        if not check_patch_file(patch_process):
            UPDATE_LOGGER.print_log(
                'Verify the incremental result failed!',
                UPDATE_LOGGER.ERROR_LOG)
            raise RuntimeError
    UPDATE_LOGGER.print_log(
            'Verify the incremental result successfully!',
            UPDATE_LOGGER.INFO_LOG)

    verse_script.add_command(
        "\n# ---- start incremental check here ----\n")
    for each_check_cmd in script_check_cmd_list:
        verse_script.add_command(each_check_cmd)
    verse_script.add_command(
        "\n# ---- start incremental write here ----\n")
    for each_write_cmd in script_write_cmd_list:
        verse_script.add_command(each_write_cmd)
    return True


def check_patch_file(patch_process):
    new_dat_file_obj, patch_dat_file_obj, transfer_list_file_obj = \
        patch_process.package_patch_zip.get_file_obj()
    with open(transfer_list_file_obj.name) as f_t:
        num = 0
        diff_str = None
        diff_num = 0
        for line in f_t:
            if line.startswith('new '):
                each_line_list = \
                    line.strip().replace("new ", "").split(",")[1:]
                for idx in range(0, len(each_line_list), 2):
                    num += \
                        int(each_line_list[idx + 1]) - int(each_line_list[idx])
                continue
            if line.startswith('bsdiff ') or line.startswith('pkgdiff '):
                diff_str = line
        if diff_str:
            diff_list = diff_str.split('\n')[0].split(' ')
            diff_num = int(diff_list[1]) + int(diff_list[2])
    check_flag = \
        (os.path.getsize(new_dat_file_obj.name) == num * PER_BLOCK_SIZE) and \
        (os.path.getsize(patch_dat_file_obj.name) == diff_num)
    return check_flag


def check_make_map_path(each_img):
    """
    If env does not exist, the command for map generation does not exist
    in the environment variable, and False will be returned.
    """
    try:
        cmd = [E2FSDROID_PATH, " -h"]
        subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    except FileNotFoundError:
        UPDATE_LOGGER.print_log(
            "Command not found, need check the env! "
            "Make %s.map failed!" % each_img,
            UPDATE_LOGGER.ERROR_LOG)
        clear_resource(err_clear=True)
        raise RuntimeError
    return True


def incremental_processing(no_zip, partition_file, source_package,
                           verse_script):
    """
    Incremental processing.
    :param no_zip: no zip mode
    :param partition_file: partition xml file path
    :param source_package: source package path
    :param verse_script: verse script obj
    :return : processing result
    """
    if len(OPTIONS_MANAGER.incremental_img_list) != 0:
        if check_incremental_args(no_zip, partition_file, source_package,
                                  OPTIONS_MANAGER.incremental_img_list) \
                is False:
            return False
        if increment_image_processing(
                verse_script, OPTIONS_MANAGER.incremental_img_list,
                OPTIONS_MANAGER.source_package_dir,
                OPTIONS_MANAGER.target_package_dir) is False:
            return False
    else:
        if source_package is not None:
            UPDATE_LOGGER.print_log(
                "There is no incremental image, "
                "the - S parameter is not required!",
                UPDATE_LOGGER.ERROR_LOG)
            raise RuntimeError


def check_args(private_key, source_package, target_package, update_package):
    """
    Input args check.
    :param private_key: private key path
    :param source_package: source package path
    :param target_package: target package path
    :param update_package: output package path
    :return : Judgment result
    """
    if source_package is False or private_key is False or \
            target_package is False or update_package is False:
        return False
    if check_miss_private_key(private_key) is False:
        return False
    if check_target_package_path(target_package) is False:
        return False
    if get_update_info() is False:
        return False
    if check_images_list() is False:
        return False
    return True


create_entrance_args()


def main():
    """
    Entry function.
    """
    parse_args()

    OPTIONS_MANAGER.product = PRODUCT

    source_package, target_package, update_package, no_zip, not_l2, \
        partition_file, signing_algorithm, hash_algorithm, private_key = \
        get_args()
    if not_l2:
        no_zip = True
    
    # Unpack updater package
    if OPTIONS_MANAGER.unpack_package_path:
        package = UnpackPackage()
        if not package.unpack_package():
            UPDATE_LOGGER.print_log(
                "Unpack update package .bin failed!", UPDATE_LOGGER.ERROR_LOG)
            clear_resource(err_clear=True)
            return
        UPDATE_LOGGER.print_log("Unpack update package .bin success!")
        clear_resource(err_clear=True)
        return

    if OPTIONS_MANAGER.sd_card:
        if source_package is not None or \
                OPTIONS_MANAGER.xml_path is not None or \
                partition_file is not None:
            UPDATE_LOGGER.print_log(
                "SD Card updater, "
                "the -S/-xp/-pf parameter is not required!",
                UPDATE_LOGGER.ERROR_LOG)
            raise RuntimeError
    if check_args(private_key, source_package,
                  target_package, update_package) is False:
        clear_resource(err_clear=True)
        return

    if not OPTIONS_MANAGER.sd_card:
        if check_userdata_image() is False:
            clear_resource(err_clear=True)
            return

    # Create a Script object.
    prelude_script, verse_script, refrain_script, ending_script = \
        get_script_obj()

    # Create partition.
    if partition_file is not None:
        verse_script.add_command("\n# ---- do updater partitions ----\n")
        updater_partitions_cmd = verse_script.updater_partitions()
        verse_script.add_command(updater_partitions_cmd)

        partition_file_obj, partitions_list, partitions_file_path_list = \
            parse_partition_file_xml(partition_file)
        if partition_file_obj is False:
            clear_resource(err_clear=True)
            return False
        OPTIONS_MANAGER.partition_file_obj = partition_file_obj
        OPTIONS_MANAGER.full_img_list = partitions_list
        OPTIONS_MANAGER.full_image_path_list = partitions_file_path_list
        OPTIONS_MANAGER.two_step = False

    # Upgrade the updater image.
    if OPTIONS_MANAGER.two_step:
        get_status_cmd = verse_script.get_status()
        set_status_0_cmd = verse_script.set_status('0')
        set_status_1_cmd = verse_script.set_status('1')
        reboot_now_cmd = verse_script.reboot_now()
        create_updater_script_command = \
            '\n# ---- do updater partitions ----\n\n' \
            'if ({get_status_cmd} == 0){{\nUPDATER_WRITE_FLAG\n' \
            '    {set_status_1_cmd}    {reboot_now_cmd}}}\n' \
            'else{{    \nALL_WRITE_FLAG\n    {set_status_0_cmd}}}'.format(
                get_status_cmd=get_status_cmd,
                set_status_1_cmd=set_status_1_cmd,
                set_status_0_cmd=set_status_0_cmd,
                reboot_now_cmd=reboot_now_cmd)
        verse_script.add_command(create_updater_script_command)

    if incremental_processing(
            no_zip, partition_file, source_package, verse_script) is False:
        clear_resource(err_clear=True)
        return

    # Full processing
    if len(OPTIONS_MANAGER.full_img_list) != 0:
        verse_script.add_command("\n# ---- full image ----\n")
        full_update_image = \
            FullUpdateImage(OPTIONS_MANAGER.target_package_dir,
                            OPTIONS_MANAGER.full_img_list,
                            OPTIONS_MANAGER.full_img_name_list,
                            verse_script, OPTIONS_MANAGER.full_image_path_list,
                            no_zip=OPTIONS_MANAGER.no_zip)
        full_image_content_len_list, full_image_file_obj_list = \
            full_update_image.update_full_image()
        if full_image_content_len_list is False or \
                full_image_file_obj_list is False:
            clear_resource(err_clear=True)
            return
        OPTIONS_MANAGER.full_image_content_len_list, \
            OPTIONS_MANAGER.full_image_file_obj_list = \
            full_image_content_len_list, full_image_file_obj_list

    # Generate the update package.
    build_re = build_update_package(no_zip, update_package,
                                    prelude_script, verse_script,
                                    refrain_script, ending_script)
    if build_re is False:
        clear_resource(err_clear=True)
        return
    # Clear resources.
    clear_resource()


if __name__ == '__main__':
    main()
