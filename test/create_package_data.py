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
import ast
import os
import shutil
import zipfile

from test.fake_data import RSA_PRIVATE_KEY_DATA

UPDATER_BINARY_DATA = b"updater binary data"
BOARD_LIST_DATA = b"""HI3516
HI3518
HI3559"""
VERSION_MBN_DATA = b"""Hi3516DV300-eng 10 QP1A.190711.020
Hi3516DV300-eng 10 QP1A.190711.021"""

UPDATER_SPECIFIED_CONFIG_XML_DATA = """<?xml version="1.0"?>
<package>
    <head name="Component header information">
        <info fileVersion="01" prdID="123456" 
        softVersion="Hi3516DV300-eng 10 QP1A.190711.0VERSION_MARK" 
        date="2021-01-23" time="12:30">head info</info>
    </head>
    <group name = "Component information">
        SYSTEM_MARK
        COMPONENT_MARK
    </group>
</package>"""
UPDATER_PARTITIONS_XML_DATA = b"""<?xml version="1.0" encoding="GB2312" ?>
<Partition_Info>
<Part PartitionName="boot" FlashType="emmc" FileSystem="none" 
    Start="0" Length="1M"/>
<Part PartitionName="kernel" FlashType="emmc" FileSystem="none" 
    Start="1M" Length="15M"/>
<Part PartitionName="updater" FlashType="emmc" FileSystem="ext3/4" 
    Start="16M" Length="20M"/>
<Part PartitionName="misc" FlashType="emmc" FileSystem="none" 
    Start="36M" Length="1M"/>
<Part PartitionName="system" FlashType="emmc" FileSystem="ext3/4" 
    Start="37M" Length="3300M"/>
<Part PartitionName="vendor" FlashType="emmc" FileSystem="ext3/4" 
    Start="3337M" Length="263M"/>
<Part PartitionName="userdata" FlashType="emmc" FileSystem="ext3/4" 
    Start="3600M" Length="1464M"/>
</Partition_Info>"""

SYSTEM_COMPONENT_STR = """<component compAddr="system" compId="12" 
        resType="05" compType="0" compVer="0o00">./system.img</component>"""
COMPONENT_STR_INC = """<component compAddr="vendor" compId="13" 
        resType="05" compType="1" compVer="0o00">./vendor.img</component>"""
COMPONENT_STR_FULL = """<component compAddr="vendor" compId="13" 
        resType="05" compType="0" compVer="0o00">./vendor.img</component>"""
COMPONENT_STR_USERDATA = """<component compAddr="userdata" compId="14" 
        resType="05" compType="0" compVer="0o00">./userdata.img</component>"""
SOURCE_VERSION_STR = "20"
TARGET_VERSION_STR = "21"


def create_input_package(
        package_name, package_type="target", is_su=False,
        is_updater_partitions=False, has_userdata=False,
        is_inc_full_none=False, is_miss_image=False,
        is_miss_version_list=False, is_miss_updater_binary=False):
    """
    Create input package.
    :param package_name: package name
    :param package_type: package type, source or target
    :param is_su: Is it an updater upgrade package
    :param is_updater_partitions: Is it an updater partitions upgrade package
    :param has_userdata: Configuring UserData in XML
    :param is_inc_full_none: Both full and incremental list lengths are zero
    :param is_miss_image: Is image missing
    :param is_miss_version_list: Is VERSION.list missing
    :param is_miss_updater_binary: Is updater_binary missing
    :return:
    """
    # Create a folder for the input package.
    package_name_path = "./%s" % package_name
    if not os.path.exists(package_name_path):
        os.mkdir(package_name_path)

    if not is_miss_image:
        create_file(os.path.join(package_name_path, "system.img"),
                    get_target_vendor_data())

    # Judge the type of input package and generate the corresponding vendor.img
    if package_type == "target":
        vendor_content = get_target_vendor_data()
    elif package_type == "source":
        vendor_content = get_source_vendor_data()
    else:
        print("Unknown package type!")
        raise RuntimeError
    if not is_miss_image:
        create_file(os.path.join(package_name_path, "vendor.img"),
                    vendor_content)
    if not is_miss_updater_binary:
        create_file(os.path.join(package_name_path, "updater_binary"),
                    UPDATER_BINARY_DATA)
    # updater upgrade package
    if is_su:
        create_file(os.path.join(package_name_path, "uImage"),
                    get_target_vendor_data())
        create_file(os.path.join(package_name_path, "updater.img"),
                    get_target_vendor_data())
        create_file(os.path.join(package_name_path, "updater_b.img"),
                    get_target_vendor_data())
        create_file(os.path.join(package_name_path, "updater_uImage"),
                    get_target_vendor_data())
    # Create updater_config dir.
    updater_config_path = "./%s/updater_config" % package_name
    if not os.path.exists(updater_config_path):
        os.mkdir(updater_config_path)
    create_file(os.path.join(updater_config_path, "BOARD.list"),
                BOARD_LIST_DATA)
    if not is_miss_version_list:
        create_file(os.path.join(updater_config_path, "VERSION.mbn"),
                    VERSION_MBN_DATA)
    # Judge the type of input package and
    xml_content = \
        create_updater_specified_config_file(
            has_userdata, is_updater_partitions, package_type)

    if is_inc_full_none:
        xml_content = xml_content.replace("SYSTEM_MARK", "")
        xml_content = xml_content.replace(
            "COMPONENT_MARK", "").encode()
    else:
        xml_content = xml_content.replace(
            "SYSTEM_MARK", SYSTEM_COMPONENT_STR)
        xml_content = xml_content.replace(
            "COMPONENT_MARK", COMPONENT_STR_FULL).encode()

    create_file(
        os.path.join(updater_config_path, "updater_specified_config.xml"),
        xml_content)
    # Create partition_file.xml.
    if is_updater_partitions:
        create_file("./partition_file.xml", UPDATER_PARTITIONS_XML_DATA)
    # Create rsa_private_key2048.pem.
    create_file("./rsa_private_key2048.pem", RSA_PRIVATE_KEY_DATA)
    # Create zip package.
    with zipfile.ZipFile('./%s.zip' % package_name,
                         'w', zipfile.ZIP_DEFLATED) as package_zip:
        package_zip.write(package_name_path)
        for home, dirs, files in os.walk(package_name_path):
            for each_file_name in files:
                package_zip.write(os.path.join(home, each_file_name))
            for each_dir_name in dirs:
                package_zip.write(os.path.join(home, each_dir_name))


def create_updater_specified_config_file(
        has_userdata, is_updater_partitions, package_type):
    """
    generate the corresponding updater_specified_config.xml
    :param has_userdata: has userdata
    :param is_updater_partitions: is updater partitions
    :param package_type: package type
    :return:
    """
    if package_type == "target":
        xml_content = UPDATER_SPECIFIED_CONFIG_XML_DATA.replace(
            "VERSION_MARK", TARGET_VERSION_STR)
        xml_content = xml_content.replace(
            "COMPONENT_MARK", COMPONENT_STR_INC)
    elif package_type == "source":
        xml_content = UPDATER_SPECIFIED_CONFIG_XML_DATA.replace(
            "VERSION_MARK", SOURCE_VERSION_STR)
        if is_updater_partitions:
            xml_content = xml_content.replace(
                "COMPONENT_MARK", COMPONENT_STR_FULL)
        elif has_userdata:
            xml_content = xml_content.replace(
                "COMPONENT_MARK", COMPONENT_STR_USERDATA)
    else:
        print("Unknown package type!")
        raise RuntimeError
    return xml_content


def create_file(file_path, file_data):
    """
    Create file
    :param file_path: file path
    :param file_data: file data
    :return:
    """
    with open(file_path, "wb") as w_f:
        w_f.write(file_data)


def clear_package(package_name):
    """
    Clean up the constructed input package and files
    :param package_name: constructed input package name
    :return:
    """
    if os.path.exists("./%s" % package_name):
        shutil.rmtree("./%s" % package_name)
    if os.path.exists("./%s.zip" % package_name):
        os.remove("./%s.zip" % package_name)
    if os.path.exists("./partition_file.xml"):
        os.remove("./partition_file.xml")
    if os.path.exists("./rsa_private_key2048.pem"):
        os.remove("./rsa_private_key2048.pem")


def get_source_vendor_data():
    """
    Get source vendor image file data
    :return:
    """
    with open(r"./source_vendor_data", "r") as r_f:
        content = r_f.read()
        return ast.literal_eval(content)


def get_target_vendor_data():
    """
    Get target vendor image file data
    :return:
    """
    with open(r"./target_vendor_data", "r") as r_f:
        content = r_f.read()
        return ast.literal_eval(content)
