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

import os
import sys
import argparse
import subprocess


def input_path_check(arg):
    """
    Argument check, which is used to check whether the specified arg is a path.
    :param arg: the arg to check.
    :return: Check result, which is False if the arg is invalid.
    """
    if not os.path.isdir(arg) and not os.path.isfile(arg):
        return False
    return arg


def jar_name_check(arg):
    """
    Argument check, which is used to check whether the specified arg is none.
    :param arg: the arg to check.
    :return: Check result, which is False if the arg is invalid.
    """
    if arg is None:
        return False
    return arg


def build_jar(source_file, cls_out, manifest_file, jar_out, jar_name):
    jar_file = os.path.join(jar_out, '%s.jar' % jar_name)
    javac_cmd = ['javac', '-d', cls_out, source_file]
    subprocess.call(javac_cmd, shell=False)
    jar_cmd = ['jar', 'cvfm', jar_file, manifest_file, '-C', cls_out, '.']
    subprocess.call(jar_cmd, shell=False)
    return True


def main(argv):
    """
    Entry function.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument("-sf", "--source_file", type=input_path_check,
                        default=None, help="Source file path.")
    parser.add_argument("-co", "--cls_out", type=input_path_check,
                        default=None, help="Class out path.")
    parser.add_argument("-mf", "--manifest_file", type=input_path_check,
                        default=None, help="Manifest file path.")
    parser.add_argument("-jo", "--jar_out", type=input_path_check,
                        default=None, help="Jar out path.")
    parser.add_argument("-jn", "--jar_name", type=jar_name_check,
                        default=None, help="Jar name.")

    args = parser.parse_args(argv)

    # Generate the jar.
    build_re = build_jar(args.source_file, args.cls_out, args.manifest_file, args.jar_out, args.jar_name)

if __name__ == '__main__':
    main(sys.argv[1:])
