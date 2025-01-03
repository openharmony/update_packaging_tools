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
  -su, --stream_update  Stream update mode, Create update package for stream update.
  -ab, --ab_partition_update  Ab partition update mode, Create update package for ab partition update.
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
import math


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
from utils import PARTITION_CHANGE_EVENT
from utils import DECOUPLED_EVENT
from utils import get_update_config_softversion
from vendor_script import create_vendor_script_class
from create_chunk import CreateChunk
from concurrent.futures import ThreadPoolExecutor

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
    parser.add_argument("-su", "--stream_update", action='store_true',
                        help="Stream update mode, "
                             "Create update package for stream update.")
    parser.add_argument("-ab", "--ab_partition_update", action='store_true',
                        help="Ab partition update mode, "
                             "Create update package for ab partition update.")


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
    OPTIONS_MANAGER.stream_update = args.stream_update
    OPTIONS_MANAGER.ab_partition_update = args.ab_partition_update


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
        UPDATE_LOGGER.print_log("boot cannot be incrementally processed!", UPDATE_LOGGER.ERROR_LOG)
        clear_resource(err_clear=True)
        return False
    if source_package is None:
        UPDATE_LOGGER.print_log("The source package is missing, "
            "cannot be incrementally processed!", UPDATE_LOGGER.ERROR_LOG)
        clear_resource(err_clear=True)
        return False
    if no_zip:
        UPDATE_LOGGER.print_log("No ZIP mode, cannot be incrementally processed!", UPDATE_LOGGER.ERROR_LOG)
        clear_resource(err_clear=True)
        return False
    if partition_file is not None:
        UPDATE_LOGGER.print_log("Partition file is not None, "
            "cannot be incrementally processed!", UPDATE_LOGGER.ERROR_LOG)
        clear_resource(err_clear=True)
        return False

    if not get_source_package_path(source_package):
        return False
    partition_change = OPTIONS_MANAGER.init.invoke_event(PARTITION_CHANGE_EVENT)
    if callable(partition_change) and partition_change() is False:
        return False
    UPDATE_LOGGER.print_log("Partition interception check finish.", UPDATE_LOGGER.INFO_LOG)
    xml_path = ''
    if OPTIONS_MANAGER.source_package_dir is not False:
        xml_path = os.path.join(OPTIONS_MANAGER.source_package_dir, UPDATER_CONFIG, XML_FILE_PATH)
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
    no_need_version_check_res = OPTIONS_MANAGER.init.invoke_event(DECOUPLED_EVENT)
    if no_need_version_check_res is False:
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
            "source package, cannot be incrementally processed. "
            % image_name, UPDATE_LOGGER.ERROR_LOG)
        return False

    cmd = [E2FSDROID_PATH, "-B", map_path, "-a", "/%s" % image_name, image_path, "-e"]
    res = subprocess.Popen(cmd, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _, err = res.communicate(timeout=300)
    if res.returncode != 0:
        UPDATE_LOGGER.print_log("%s.map generate failed, reason:%s" %
                                (image_name, err.decode()), UPDATE_LOGGER.ERROR_LOG)
        return False
    UPDATE_LOGGER.print_log("%s.map generate success" % image_name, UPDATE_LOGGER.INFO_LOG)
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
    OPTIONS_MANAGER.incremental_image_file_obj_dict[partition] = patch_file_obj
    cmd = [DIFF_EXE_PATH]

    cmd.extend(['-s', src_image_path, '-d', tgt_image_path,
                '-p', patch_file_obj.name, '-l', '4096'])
    sub_p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
    try:
        output, _ = sub_p.communicate(timeout=1800)
    except subprocess.TimeoutExpired:
        sub_p.kill()

    sub_p.wait()
    if sub_p.returncode != 0:
        raise ValueError(output)
    
    return write_image_patch_script(partition, src_image_path, tgt_image_path,
        script_check_cmd_list, script_write_cmd_list, verse_script)


def copy_in_ab_process(patch_process, src_image_class, need_copy_blocks,
                       non_continuous_blocks, each_img):
    """
    Handle the process of copying blocks in an AB partition during an update.
    :param patch_process: The patch process object responsible for managing the update.
    :param src_image_class: The source image class containing metadata about the image.
    :param need_copy_blocks: A list to store blocks that need to be copied.
    :param non_continuous_blocks: A list to store blocks that are non-continuous.
    :param each_img: The current image being processed.
    :return:
    """
    if OPTIONS_MANAGER.ab_partition_update:
        chunk_pkgdiff_list = patch_process.get_chunk_pkgdiff_list()
        transfer_content = patch_process.get_transfer_content_in_chunk()
        chunk_new_list = patch_process.get_chunk_new_list()

        # Parase transfer_content, record all blocks involved in the content
        no_copy_blocks_in_ab, transfer_content_no_startoffert = parse_transfer_content(transfer_content)
        
        # Find the blocks to copy, total blocks includeing zero, excluding total_blocks
        no_copy_blocks_set = set(no_copy_blocks_in_ab)
        
        def process_block(src_block):
            if src_block in no_copy_blocks_set:
                return None, src_block  # Not to copy
            return src_block, None  # To copy
        with ThreadPoolExecutor() as executor:
            results = executor.map(process_block, range(src_image_class.total_blocks))

        for to_copy, not_to_copy in results:
            if to_copy is not None:
                need_copy_blocks.append(to_copy)
            if not_to_copy is not None:
                non_continuous_blocks.append(not_to_copy)
        # Sort blocks consecutively
        if len(need_copy_blocks):
            group_numbers_list = group_numbers(need_copy_blocks)
        else:
            group_numbers_list = []
            print(f'there is no copy blocks in image {each_img} !')
        # Add the copy command for ab partition synchronization
        transfer_content = patch_process.add_ab_copy_content(len(need_copy_blocks), 
                                                        group_numbers_list, transfer_content_no_startoffert)
        OPTIONS_MANAGER.image_transfer_dict_contents[each_img] = transfer_content
        OPTIONS_MANAGER.image_patch_dic[each_img] = chunk_pkgdiff_list
        OPTIONS_MANAGER.image_new_dic[each_img] = chunk_new_list
                

def add_incremental_command(verse_script, script_check_cmd_list, script_write_cmd_list):
    """
    add command for increment_image_progressing to verse_script
    :param verse_script: verse script
    :param script_check_cmd_list: verse_script check command list
    :param script_write_cmd_list: verse_script write command list
    :return:
    """
    verse_script.add_command("\n# ---- start incremental check here ----\n")
    for each_check_cmd in script_check_cmd_list:
        verse_script.add_command(each_check_cmd)
    verse_script.add_command("\n# ---- start incremental write here ----\n")
    for each_write_cmd in script_write_cmd_list:
        verse_script.add_command(each_write_cmd)


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
    
    for each_img_name in OPTIONS_MANAGER.incremental_img_name_list:
        each_img = each_img_name[:-4]
        each_src_image_path = os.path.join(source_package_dir, '%s.img' % each_img)
        each_src_map_path = os.path.join(source_package_dir, '%s.map' % each_img)
        each_tgt_image_path = os.path.join(target_package_dir, '%s.img' % each_img)
        each_tgt_map_path = os.path.join(target_package_dir, '%s.map' % each_img)

        # This will store tuples of (start, end, length) for continuous ranges
        non_continuous_blocks = []
        need_copy_blocks = []
        check_make_map_path(each_img)

        # Call the new function to process image maps
        continue_processing, src_generate_map, tgt_generate_map = process_image_maps(
            each_img, each_src_image_path, each_src_map_path, 
            each_tgt_image_path, each_tgt_map_path)
        if not continue_processing:
            continue

        # get the large of target image
        if not get_large_of_target_image(each_tgt_image_path, each_img):
            return False
        
        if not src_generate_map or not tgt_generate_map:
            if not handle_no_map_generation(each_img, each_src_image_path, each_tgt_image_path, \
                script_check_cmd_list, script_write_cmd_list, verse_script):
                return False
            continue
            
        inc_image = OPTIONS_MANAGER.init.invoke_event(INC_IMAGE_EVENT)
        if inc_image:
            src_image_class, tgt_image_class = inc_image(each_src_image_path, each_src_map_path,
                                                         each_tgt_image_path, each_tgt_map_path)
        else:
            src_image_class = IncUpdateImage(each_src_image_path, each_src_map_path)
            tgt_image_class = IncUpdateImage(each_tgt_image_path, each_tgt_map_path)

        transfers_manager = TransfersManager(each_img, tgt_image_class, src_image_class)
        transfers_manager.find_process_needs()
        actions_list = transfers_manager.get_action_list()
            
        graph_process = GigraphProcess(actions_list, src_image_class, tgt_image_class)
        # Streaming update does not need to handle stash and free commands
        if not OPTIONS_MANAGER.ab_partition_update:
            graph_process.stash_process()

        actions_list = graph_process.actions_list
        patch_process = patch_package_process.PatchProcess(each_img, tgt_image_class, src_image_class, actions_list)
                                                
        patch_process.patch_process(each_tgt_image_path)
        
        # Add copy command for ab partition
        copy_in_ab_process(patch_process, src_image_class, need_copy_blocks,
                       non_continuous_blocks, each_img)
            
        patch_process.write_script(each_img, script_check_cmd_list, script_write_cmd_list, verse_script)
        OPTIONS_MANAGER.incremental_block_file_obj_dict[each_img] = patch_process.package_patch_zip
        if not OPTIONS_MANAGER.stream_update:
            if not check_patch_file(patch_process):
                UPDATE_LOGGER.print_log('Verify the incremental result failed!', UPDATE_LOGGER.ERROR_LOG)
                raise RuntimeError

    add_incremental_command(verse_script, script_check_cmd_list, script_write_cmd_list)
    return True


def get_large_of_target_image(each_tgt_image_path, each_img):
    """
    Reads the target image content and stores it in OPTIONS_MANAGER.diff_image_new_data.

    :param each_tgt_image_path: The path to the target image.
    :param each_img: The name of the image (without extension).
    :return: True if successful, False otherwise.
    """
    try:
        with open(each_tgt_image_path, 'rb') as f:
            target_content = f.read()
        OPTIONS_MANAGER.diff_image_new_data[each_img] = target_content
        return True
    except Exception as e:
        print(f"Error reading target image {each_img}: {e}")
        return False
    

def process_image_maps(each_img, each_src_image_path, each_src_map_path, 
                       each_tgt_image_path, each_tgt_map_path):
    """
    Process source and target image maps for incremental updates.

    :param each_img: The image name without extension
    :param each_src_image_path: Path to the source image
    :param each_src_map_path: Path to the source map
    :param each_tgt_image_path: Path to the target image
    :param each_tgt_map_path: Path to the target map
    :return: A tuple (continue_processing, src_generate_map, tgt_generate_map)
             - continue_processing: Whether to continue processing the current image
             - src_generate_map: Whether the source map was successfully generated
             - tgt_generate_map: Whether the target map was successfully generated
    """
    # Check if source and target images are identical
    if filecmp.cmp(each_src_image_path, each_tgt_image_path):
        UPDATE_LOGGER.print_log(
            "Source Image is the same as Target Image! src image path: %s, tgt image path: %s"
            % (each_src_image_path, each_tgt_image_path), 
            UPDATE_LOGGER.INFO_LOG)
        OPTIONS_MANAGER.incremental_img_list.remove(each_img)
        return False, False, False  # Stop further processing for this image

    # Initialize map generation flags
    src_generate_map = True
    tgt_generate_map = True

    # Generate source map if it does not exist
    if not os.path.exists(each_src_map_path):
        src_generate_map = generate_image_map_file(each_src_image_path, each_src_map_path, each_img)

    # Generate target map if it does not exist
    if not os.path.exists(each_tgt_map_path):
        tgt_generate_map = generate_image_map_file(each_tgt_image_path, each_tgt_map_path, each_img)

    return True, src_generate_map, tgt_generate_map


def handle_no_map_generation(each_img, each_src_image_path, each_tgt_image_path, script_check_cmd_list, script_write_cmd_list, verse_script):
    if OPTIONS_MANAGER.stream_update:
        print(f'do no map process:{each_img}')
        OPTIONS_MANAGER.no_map_image_exist = True
        OPTIONS_MANAGER.no_map_file_list.append(each_img)
        # Directly cut the target image into new commands
        if not os.path.exists(each_tgt_image_path):
            UPDATE_LOGGER.print_log(
            "The file is missing "
            "from the target package, "
            "the component: %s cannot be full update processed. " %
            each_tgt_image_path)
            return False
        with open(each_tgt_image_path, 'rb') as f:
            tartget_no_map_content = f.read()
        chunk, block_sets = split_image_file(each_img, tartget_no_map_content)
        OPTIONS_MANAGER.image_chunk[each_img] = chunk
        OPTIONS_MANAGER.image_block_sets[each_img] = block_sets
        return True
    # If it is not a streaming update and cannot generate map file,directly diff the image
    elif increment_image_diff_processing(each_img, each_src_image_path, each_tgt_image_path,
        script_check_cmd_list, script_write_cmd_list, verse_script) is True:
        return True
    UPDATE_LOGGER.print_log("increment_image_diff_processing %s failed" % each_img)
    clear_resource(err_clear=True)
    return False
    
    
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


def unpack_package_processing():
    if OPTIONS_MANAGER.unpack_package_path:
        package = UnpackPackage()
        if not package.unpack_package():
            UPDATE_LOGGER.print_log("Unpack update package.bin failed!", UPDATE_LOGGER.ERROR_LOG)
            clear_resource(err_clear=True)
            sys.exit(1)
        UPDATE_LOGGER.print_log("Unpack update package.bin success!")
        clear_resource()
        sys.exit(0)


def group_numbers(arr):
    """
    Groups and sorts a list of consecutive numbers, returning a list of block ranges.
    :param arr: A list of integers representing block numbers.
    :return: A list of integers representing the start and end of each block range.
    """
    result = []
    current_group = [arr[0]]
    transfer_content_blocks = []
    
    for i in range(1, len(arr)):
        if arr[i] == arr[i - 1] + 1:
            current_group.append(arr[i])
        else:
            result.append({
                'min': min(current_group),
                'max': max(current_group),
                'length': len(current_group)
            })
            transfer_content_blocks.append(min(current_group))
            transfer_content_blocks.append(max(current_group) + 1)
            
            current_group = [arr[i]]
    
           
    result.append({
        'min': min(current_group),
        'max': max(current_group),
        'length': len(current_group)
    })
    transfer_content_blocks.append(min(current_group))
    transfer_content_blocks.append(max(current_group) + 1)
    
    return transfer_content_blocks


def parse_transfer_content(content):
    """
    Parses the transfer content to extract block information and modified lines.   
    :param content: The string content to be parsed, typically containing block data.
    :return: A tuple containing:
             - all_blocks: A list of all extracted block numbers.
             - modified_content: A modified version of the original content with adjustments made.
    """
    all_blocks = []
    modified_lines = []
    lines = content.splitlines()
    for line in lines[4:]:
        if 'pkgdiff' in line:
            modified_line, blocks = handle_pkgdiff(line)
            modified_lines.append(modified_line)           
            all_blocks.extend(blocks)
        elif 'zero' in line or 'erase' in line:
            blocks = handle_zero_erase(line)
            all_blocks.extend(blocks)
            modified_lines.append(line)
        elif 'move' in line or 'new' in line:
            blocks = handle_move_new(line)
            all_blocks.extend(blocks)
            modified_lines.append(line)        
        elif 'free' in line:
            print('no add free cmd')
            modified_lines.append(line)
        else:
            raise ValueError(f"no parse transfer_list info, got {lines}.")
    modified_content = '\n'.join(lines[:4] + modified_lines)    
    return all_blocks, modified_content


def handle_pkgdiff(line):
    """
    Handles the 'pkgdiff' line type.
    :param line: The line to process.
    :return: A tuple containing the modified line and the list of blocks.
    """
    parts = line.replace(',', ' ').split()
    # Change the start offset address of pkgdiff to all zeros
    modified_line = line.replace(line.split()[1], '0', 1)
    length = int(parts[5])
    if length % 2 != 0:
        raise ValueError(f"Length must be even, got {length}.")
    # Extract the range values of a pair of blocks
    pairs = list(map(int, parts[6:length + 6]))  
    blocks = []
    # List all blocks in a single pair of block range values
    for i in range(0, len(pairs), 2):
        start = pairs[i]
        print(f'start:{start}')
        end = pairs[i + 1]
        print(f'end:{end}')
        blocks.extend(range(start, end))
        print(f'len(blocks):{len(blocks)}')
    return modified_line, blocks


def handle_zero_erase(line):
    """
    Handles the 'zero' or 'erase' line type.
    :param line: The line to process.
    :return: The list of blocks extracted from the line.
    """
    parts = line.replace(',', ' ').split()
    length = int(parts[1])
    print(f'lenght:{length}')
    if length % 2 != 0:
        raise ValueError(f"Length must be even, got {length}.")
    pairs = list(map(int, parts[2:length + 2]))
    blocks = []
    for i in range(0, len(pairs), 2):
        start = pairs[i]
        print(f'start:{start}')
        end = pairs[i + 1]
        print(f'end:{end}')
        blocks.extend(range(start, end))
        print(f'len(blocks):{len(blocks)}')
    return blocks


def handle_move_new(line):
    """
    Handles the 'move' or 'new' line type.
    :param line: The line to process.
    :return: The list of blocks extracted from the line.
    """
    parts = line.replace(',', ' ').split()
    length = int(parts[2])
    print(f'lenght:{length}')
    if length % 2 != 0:
        raise ValueError(f"Length must be even, got {length}.")
    pairs = list(map(int, parts[3:length + 3]))
    blocks = []
    for i in range(0, len(pairs), 2):
        start = pairs[i]
        print(f'start:{start}')
        end = pairs[i + 1]
        print(f'end:{end}')
        blocks.extend(range(start, end))
        print(f'len(blocks):{len(blocks)}')
    return blocks


def split_image_file(each_img, full_image_data):
    """
    Splits the full image data into smaller chunks.    
    :param each_img: The image to be split (not used in the current implementation).
    :param full_image_data: The complete image data to be split.
    :return: A tuple containing two lists:
             - chunks: A list of data chunks.
             - block_sets: A list of corresponding block sets for each chunk.
    """
    # get the total block number of the image
    total_blocks = math.ceil(len(full_image_data) / 4096)
    print(f'total tgt blocks:{total_blocks}')
    # step 1：get the total size of the image data
    max_chunk_size = OPTIONS_MANAGER.chunk_limit * 4096
    total_size = len(full_image_data)
    print(f'total size:{total_size}')
    chunks = []
    block_sets = []
    # step 2：cut the image data into fixed block size
    num = math.ceil(total_size / max_chunk_size)
    print(f'num:{num}')
    for i in range(num):
        start_index = i * max_chunk_size
        end_index = min(start_index + max_chunk_size, total_size)  
        chunk = full_image_data[start_index:end_index]
    # step 3：record the corresponding block set
        block_set = list(range(math.ceil(start_index / 4096), 
                                math.ceil(end_index / 4096)))
        chunks.append(chunk)
        block_sets.append(block_set)
        print(f"block {i + 1}: size = {len(chunk)} bytes, block sets = {block_set}")
    print(f'total size:{total_size}')
    print(f'total tgt blocks:{total_blocks}')
    return chunks, block_sets
  
  
create_entrance_args()


def main():
    """
    Entry function.
    """
    parse_args()

    OPTIONS_MANAGER.product = PRODUCT

    source_package, target_package, update_package, no_zip, not_l2, \
        partition_file, signing_algorithm, hash_algorithm, private_key = get_args()
    if not_l2:
        no_zip = True

    # Unpack updater package
    unpack_package_processing()

    if OPTIONS_MANAGER.sd_card:
        if source_package is not None or OPTIONS_MANAGER.xml_path is not None or partition_file is not None:
            UPDATE_LOGGER.print_log("SDCard updater:-S/-xp/-pf parameter is not required!", UPDATE_LOGGER.ERROR_LOG)
            raise RuntimeError
    if check_args(private_key, source_package, target_package, update_package) is False:
        clear_resource(err_clear=True)
        return

    if not OPTIONS_MANAGER.sd_card:
        if check_userdata_image() is False:
            clear_resource(err_clear=True)
            return

    # Create a Script object.
    prelude_script, verse_script, refrain_script, ending_script = get_script_obj()

    # Create partition.
    if partition_file is not None:
        verse_script.add_command("\n# ---- do updater partitions ----\n")
        updater_partitions_cmd = verse_script.updater_partitions()
        verse_script.add_command(updater_partitions_cmd)

        partition_file_obj, partitions_list, partitions_file_path_list = parse_partition_file_xml(partition_file)
        if partition_file_obj is False:
            clear_resource(err_clear=True)
            return False
        OPTIONS_MANAGER.partition_file_obj = partition_file_obj
        OPTIONS_MANAGER.full_img_list = partitions_list
        OPTIONS_MANAGER.full_image_path_list = partitions_file_path_list
        
    # Incremental processing
    if incremental_processing(no_zip, partition_file, source_package, verse_script) is False:
        clear_resource(err_clear=True)
        return

    # Full processing
    if len(OPTIONS_MANAGER.full_img_list) != 0:
        verse_script.add_command("\n# ---- full image ----\n")
        full_update_image = FullUpdateImage(OPTIONS_MANAGER.target_package_dir,
                            OPTIONS_MANAGER.full_img_list, OPTIONS_MANAGER.full_img_name_list, verse_script,
                            OPTIONS_MANAGER.full_image_path_list, no_zip=OPTIONS_MANAGER.no_zip)
        full_image_content_len_list, full_image_file_obj_list = full_update_image.update_full_image()
        if full_image_content_len_list is False or full_image_file_obj_list is False:
            clear_resource(err_clear=True)
            return
        # Full streaming process
        if OPTIONS_MANAGER.stream_update:
            for each_img_name in OPTIONS_MANAGER.full_img_name_list:
                print(f'full streaming process! current image name is:{each_img_name}')
                each_img = each_img_name[:-4]
                chunks, block_sets = split_image_file(each_img, 
                                                      OPTIONS_MANAGER.full_image_new_data[each_img])
                OPTIONS_MANAGER.full_chunk[each_img] = chunks
                OPTIONS_MANAGER.full_block_sets[each_img] = block_sets
                             
        OPTIONS_MANAGER.full_image_content_len_list, OPTIONS_MANAGER.full_image_file_obj_list = \
            full_image_content_len_list, full_image_file_obj_list

    # Generate the update package.
    if build_update_package(
        no_zip, update_package, prelude_script, verse_script, refrain_script, ending_script) is False:
        clear_resource(err_clear=True)
        return
    # Clear resources.
    clear_resource()


if __name__ == '__main__':
    main()
