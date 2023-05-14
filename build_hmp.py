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

"""
The tool for making hmp.

positional arguments:
  -pn PACKAGE_NAME, --package_name PACKAGE_NAME
                        Module package name.
  -op OUT_PACKAGE, --out_package OUT_PACKAGE
                        Out package file path.
  -pi PACK_INFO, --pack_info PACK_INFO
                        Pack info file path.
  -mf MODULE_FILES, --module_files MODULE_FILES
                        Module files path.
"""
import os
import sys
import argparse
import zipfile
import io
import logging


# 1000000: max number of function recursion depth
MAXIMUM_RECURSION_DEPTH = 1000000
sys.setrecursionlimit(MAXIMUM_RECURSION_DEPTH)


def package_name_check(arg):
    """
    Argument check, which is used to check whether the specified arg is none.
    :param arg: the arg to check
    :return:  Check result, which is False if the arg is invalid.
    """
    if arg is None:
        UPDATE_LOGGER.print_log(
            "Package name error: %s" % arg, UPDATE_LOGGER.ERROR_LOG)
        return False
    return arg


def check_out_package(arg):
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
                "Out package must be a dir path, not a file path. "
                "path: %s" % arg, UPDATE_LOGGER.ERROR_LOG)
            return False
    else:
        try:
            UPDATE_LOGGER.print_log(
                "Out package path does not exist. The dir will be created!"
                "path: %s" % arg, UPDATE_LOGGER.WARNING_LOG)
            os.makedirs(arg)
            make_dir_path = arg
        except OSError:
            UPDATE_LOGGER.print_log(
                "Make out package path dir failed! "
                "path: %s" % arg, UPDATE_LOGGER.ERROR_LOG)
            return False
    return arg


def pack_info_check(arg):
    """
    Argument check, which is used to check whether
    the specified arg is a pack info.
    :param arg: the arg to check
    :return: Check result, which is False if the arg is invalid.
    """
    if not os.path.isfile(arg):
        UPDATE_LOGGER.print_log(
            "FileNotFoundError, path: %s" % arg, UPDATE_LOGGER.ERROR_LOG)
        return False
    return arg


class UpdateToolLogger:
    """
    Global log class
    """
    INFO_LOG = 'INFO_LOG'
    WARNING_LOG = 'WARNING_LOG'
    ERROR_LOG = 'ERROR_LOG'
    LOG_TYPE = (INFO_LOG, WARNING_LOG, ERROR_LOG)

    def __init__(self, output_type='console'):
        self.__logger_obj = self.__get_logger_obj(output_type=output_type)

    @staticmethod
    def __get_logger_obj(output_type='console'):
        ota_logger = logging.getLogger(__name__)
        ota_logger.setLevel(level=logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s : %(message)s',
            "%Y-%m-%d %H:%M:%S")
        if output_type == 'console':
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)
            ota_logger.addHandler(console_handler)
        elif output_type == 'file':
            file_handler = logging.FileHandler("UpdateToolLog.txt")
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            ota_logger.addHandler(file_handler)
        return ota_logger

    def print_log(self, msg, log_type=INFO_LOG):
        """
        Print log information.
        :param msg: log information
        :param log_type: log type
        :return:
        """
        if log_type == self.LOG_TYPE[0]:
            self.__logger_obj.info(msg)
        elif log_type == self.LOG_TYPE[1]:
            self.__logger_obj.warning(msg)
        elif log_type == self.LOG_TYPE[2]:
            self.__logger_obj.error(msg)
        else:
            self.__logger_obj.error("Unknown log type! %s", log_type)
            return False
        return True

    def print_uncaught_exception_msg(self, msg, exc_info):
        """
        Print log when an uncaught exception occurs.
        :param msg: Uncaught exception
        :param exc_info: information about the uncaught exception
        """
        self.__logger_obj.error(msg, exc_info=exc_info)


UPDATE_LOGGER = UpdateToolLogger()


def build_hmp(package_name, out_package, pack_info, module_files):
    out_package_path = os.path.join(
        out_package, '%s.zip' % package_name)
    zip_file = zipfile.ZipFile(out_package_path, 'w', zipfile.ZIP_DEFLATED, allowZip64=True)
    for module_file in module_files:
        zip_file.write(module_file, os.path.basename(module_file))
    zip_file.write(pack_info, os.path.basename(pack_info))
    zip_file.close()
    return True


def main(argv):
    """
    Entry function.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument("-pn", "--package_name", type=package_name_check,
                        default=None, help="Module package name.")
    parser.add_argument("-op", "--out_package", type=check_out_package,
                        default=None, help="Out package file path.")
    parser.add_argument("-pi", "--pack_info", type=pack_info_check,
                        default=None, help="Pack info file path.")
    parser.add_argument("-mf", "--module_files", nargs='+',
                        default=None, help="Module files path.")

    args = parser.parse_args(argv)

    # Generate the hmp.
    build_re = build_hmp(args.package_name, args.out_package, args.pack_info, args.module_files)

if __name__ == '__main__':
    main(sys.argv[1:])
