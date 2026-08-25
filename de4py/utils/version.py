# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import re
from typing import Tuple


def parse_version(v: str) -> Tuple[int, int, int]:
    cleaned = v.strip().lstrip('Vv')
    parts = re.split(r'[.\-]', cleaned)
    nums = []
    for p in parts[:3]:
        try:
            nums.append(int(p))
        except ValueError:
            nums.append(0)
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums)


def is_newer(remote: str, local: str) -> bool:
    return parse_version(remote) > parse_version(local)


def versions_equal(remote: str, local: str) -> bool:
    return parse_version(remote) == parse_version(local)
