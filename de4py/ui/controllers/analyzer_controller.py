# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from de4py.engines.analyzers import (
    detect_packer, unpack_file, get_file_hashs,
    sus_strings_lookup, all_strings_lookup
)


def run_detect_packer(file_path):
    return detect_packer(file_path)


def run_unpack_file(file_path):
    return unpack_file(file_path)


def run_get_file_hashs(file_path):
    return get_file_hashs(file_path)


def run_sus_strings_lookup(file_path):
    return sus_strings_lookup(file_path)


def run_all_strings_lookup(file_path):
    return all_strings_lookup(file_path)

