# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import os
import random
import string

def gen_path(d=None):
    random_filename = ''.join(random.choice(string.ascii_letters) for i in range(random.randint(10, 15)))+'.txt'
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    file_path = os.path.join(root, random_filename)
    return file_path, random_filename