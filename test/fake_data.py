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
RSA_PRIVATE_KEY_DATA = b"""-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA49SUn9WClk/whGbVLVc8ol4FiSt/jw5EZ8T9PVFiYirAf4Cm
R0/bBZhlGiHtfFSOeHwednGhdbDVPb9dZl/a9SwhuCPhhQVICne8RvqzgJFsgpO5
CBxW1xspM/HDuz9c5gOLnu1+df3EASsv56xh6hH1LOe5QkGEA5QPZ9WoRlOJaP5T
ndZ+BEih4IPgQswRlCRFpx/Idiv8gi4bg9ZxmJ8CVMusSPHGm64dvlkn+LSZ9KMh
vhWFSZAFtcHK9hz55wQwMrhN+LCjVZA+MPUvaU1L+cT0ZDh+qxH0MQuL1wbgkd1b
HfYCUu+8D2q0PLfk4d6ncZRvjiChalX5g2mVLQIDAQABAoIBACIhhKp1N/0AuM19
Ak6qlQDWCQpFo/RwdLr+/dkjyhNeyDvRsBda1Tr/W5YQox1PJZDTN1UTLNcOyMNZ
WcqubYTxOZP2fCCLbAF1cpVHlYCbSKA/NScL586N2RxZCbORiH9E5LPIbHuMqsJq
D+ErJ/gC/LHffRd57ScEFVK+5VizfrCddBsPbbF2aCoQZyiDX4DBIQ+kMUgNChN7
I7J5yA8DrTjzEATArOlnKUvnlVx/jKT3ncCYQujxwQlzJWDbaSgon5ZhjBazSUiC
eHPbE+bCvcD90pWddUByeS885eMDIOhErJFS+lYYdI+bT3T5rILzK8wR2CupMhkX
a9RYuZkCgYEA9lGoxWyWIFK3ymeT6DOhqK6Cr7MJiYgAvgk+fA3dDVsGuEM6Xy/O
wwt915cZvKzcb018AmeSVwYvy7l3EuYDKXP/YzntV7OLuH9Fu3zuoZ4U3VOHtKLD
VOHeWO/dg/BB96mP2xxltwv64ZT3gPf9MIpDmgVnL4QREUG4K6T/XEsCgYEA7Mjl
8AK/Hu9cIPAwB0NNCU3ptnlznu42c+lj1SHfCtYV9me14nVEIynevyniZ3y8jMi6
5Ozo/Rt26W+WuxZj6vPH2FBtB3kMgxDPDGunphl6wKJ+3RqvBrErAu9AW6e/H5NP
gxU8V8PVO+Qo3CwIhjnjkobi7nBXe6gU1iqkeWcCgYAubqJD5P4/xZgDvZayFNmK
dKsJ99P6avrI1/FBbVOYKuqPXYzpWJe/SLFGLKObX3KGQLL5uRBq+y2TV7jMhTNf
YxBnYgoNmDjkZIl+mERbjvMb7Z0NPglYPOOvHDhDoMyupPYLNcUuxkFauLwXQagm
uEmaBR64ZErbV+ohwA6rFQKBgQC9P6RnvAo9E1ozCUWZyHSd5yPQsCl08TecVQFx
q2y1IH7VPfblVIxs/l4Fs9g8ljms3BJkPeXJxlW4JXP3e+HIO6eSgFVkD5+scZbK
epC39M1jgXycA2O4mYmjAs4Rc3USK471Wdes3dxjzevKbXcysLnutthRcoC5WJGu
ys5CKQKBgQDpYc/LxUR4K5k55kQyPofkyIlVK/De3VwsD7eCeRDb1jfcF52Xuuxg
Pm6RlIvVRy7RsrG7kKqWCiVAFauQQswW6DDBbjmrFd6CrruEAqwwgbCHZjE5Dy+0
ZKsKfkm/bymEiq7ATwzvWfuU3T3R0O9+S1RbTNYo+D3N2soTfPnXyw==
-----END RSA PRIVATE KEY-----"""

PARTITION_FILE_CONVERSION_FAILED = b"""<?xml version="1.0" encoding="GB2312" ?>
<Partition_Info>
<Part PartitionName="fastboot" FlashType="emmc" FileSystem="none" 
    Start="0N" Length="1M"/>
<Part PartitionName="kernel" FlashType="emmc" FileSystem="none" 
    Start="1M" Length="15M"/>
</Partition_Info>"""

UPDATER_SPECIFIED_CONFIG_REPEATS = """<?xml version="1.0"?>
<package>
    <head name="Component header information">
        <info fileVersion="01" prdID="123456" 
        softVersion="Hi3516DV300-eng 10 QP1A.190711.020" date="2021-01-23" 
        time="12:30">head info</info>
    </head>
    <group name = "Component information">
        <component compAddr="vendor" compId="12" resType="05" compType="0" 
        compVer="0o00">./vendor.img</component>
        <component compAddr="vendor" compId="12" resType="05" compType="1" 
        compVer="0o00">./vendor.img</component>
    </group>
</package>"""
