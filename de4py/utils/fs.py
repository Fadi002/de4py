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
import hashlib
import json

def gen_path():
    random_filename = ''.join(random.choice(string.ascii_letters) for i in range(random.randint(10, 15)))+'.txt'
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    file_path = os.path.join(root, random_filename)
    return os.path.abspath(file_path), random_filename

def calculate_checksum(file_path):
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)
    return hasher.hexdigest()

def generate_checksums(excludes=None):
    if excludes is None:
        excludes = ['__pycache__', '.git', 'logs']
        
    checksums = {}
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in excludes]
        for file in files:
            if file.endswith('checksums.json'):
                continue
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, base_dir)
            checksums[rel_path] = calculate_checksum(file_path)
            
    return checksums

def save_checksums(checksums, output_file='checksums.json'):
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    out_path = os.path.join(base_dir, output_file)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(checksums, f, indent=4)
