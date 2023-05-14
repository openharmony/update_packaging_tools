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
import secrets

MOUNT_POINT = "/module_update"
BLOCK_SIZE = 4096
HASH_SIZE = 32
IMG_MARGIN_SIZE = 16777216


def run_cmd(cmd):
    res = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
    sout, serr = res.communicate(timeout=120)

    return res.pid, res.returncode, sout, serr


def verify_ret(res):
    if res[1]:
        print(" ".join(["pid ", str(res[0]), " ret ", str(res[1]), "\n",
                        res[2].decode(), res[3].decode()]))
        print("MkImages failed errno: %s" % str(res[1]))
        sys.exit(2)


def sparse_img2simg(is_sparse, device):
    # we don't support sparse in mktools.
    if "sparse" in is_sparse:
        tmp_device = "%s.tmp" % device
        run_cmd(" ".join(["img2simg ", device, " ", tmp_device]))
        os.rename(tmp_device, device)


def getdirsize(target_dir):
    size = 0
    for root, dirs, files in os.walk(target_dir):
        size += sum([roundup(os.path.getsize(os.path.join(root, name)), BLOCK_SIZE) for name in files])
    return size


def roundup(size, unit):
    return (size + unit - 1) & (~(unit - 1))


def resize_img(device):
    run_cmd(" ".join(["resize2fs", "-M", device]))


def get_hash_tree_size(img_size):
    treesize = 0
    size = img_size
    while size > BLOCK_SIZE:
        blocknum = size // BLOCK_SIZE
        level_size = roundup(blocknum * HASH_SIZE, BLOCK_SIZE)
        treesize += level_size
        size = level_size
    return treesize


def sign_img(device, pubkey, privkey, output):
    hvb_tools = "hvbtool.py"
    source_image = device
    partition = "update"
    img_size = os.path.getsize(device)
    partition_size = img_size + get_hash_tree_size(img_size) + BLOCK_SIZE
    salt = secrets.token_hex(20)
    algorithm = "SHA256_RSA2048"
    rollback_index = "0"
    rollback_location = "0"
    run_cmd(" ".join([hvb_tools, "make_hashtree_footer", "--image", device,
        "--partition", partition,
        "--partition_size", str(partition_size),
        "--salt", salt,
        "--pubkey", pubkey,
        "--privkey", privkey,
        "--algorithm", algorithm,
        "--rollback_index", rollback_index,
        "--rollback_location", rollback_location,
        "--output", output]))


def build_image(args):
    image_type = "raw"
    if args.sparse_image:
        image_type = "sparse"
    if args.build_image_tools_path:
        env_path = ':'.join(args.build_image_tools_path)
        os.environ['PATH'] = '{}:{}'.format(env_path, os.environ.get('PATH'))
    src_dir = args.input_path
    device = args.output_image_path
    is_sparse = image_type
    if "ext4" == args.fs_type:
        fs_type = "ext4"
        mkfs_tools = "mkextimage.py"
    elif "f2fs" == args.fs_type:
        fs_type = "f2fs"
        mkfs_tools = "mkf2fsimage.py"
    elif "cpio" == args.fs_type:
        fs_type = "cpio"
        mkfs_tools = "mkcpioimage.py"
    else:
        print("not support filesystem type!!")
        sys.exit(1)
    
    fs_size = getdirsize(src_dir) + IMG_MARGIN_SIZE
    fs_type_config = "--fs_type=" + fs_type
    dac_config = args.dac_config
    file_context = args.file_context

    mk_configs = " ".join([src_dir, device, MOUNT_POINT, str(fs_size), fs_type_config,
        "--dac_config", dac_config, "--file_context", file_context])
    res = run_cmd(" ".join([mkfs_tools, mk_configs]))
    verify_ret(res)
    sparse_img2simg(is_sparse, device)
    resize_img(device)
    if args.pubkey:
        sign_img(device, args.pubkey, args.privkey, args.output_sign_image_path)
    else:
        print("not sign image")


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--image-name', required=True)
    parser.add_argument('--fs-type', required=True)
    parser.add_argument('--dac-config', required=True)
    parser.add_argument('--file-context', required=True)
    parser.add_argument('--input-path', required=True)
    parser.add_argument('--output-image-path', required=True)
    parser.add_argument('--sparse-image',
                        dest="sparse_image",
                        action='store_true')
    parser.set_defaults(sparse_image=False)
    parser.add_argument('--build-image-tools-path', nargs='*', required=False)
    parser.add_argument('--target-cpu', required=False)
    parser.add_argument('--pubkey', required=False)
    parser.add_argument('--privkey', required=False)
    parser.add_argument('--output-sign-image-path', required=False)
    args = parser.parse_args(argv)

    if os.path.exists(args.output_image_path):
        os.remove(args.output_image_path)
    if os.path.isdir(args.input_path):
        build_image(args)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
