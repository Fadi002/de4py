# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from .erebus import Deobfuscator, Result, unwrap


def Hyperion(path):
    with open(path, encoding='utf8', errors='ignore') as f:
        code = f.read()
    code = unwrap(code)
    result = Deobfuscator(code).deobfuscate()
    return result.code
