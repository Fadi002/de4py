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
    random_filename = ''.join(random.choice(string.ascii_letters) for _ in range(random.randint(10, 15))) + '.txt'
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
    import subprocess

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    checksums = {}

    def is_ignored(path):
        if path in ('checksums.json', 'crowdin.yml', '.gitattributes', '.gitignore', 'LICENSE'):
            return True
        if path.endswith('.md'):
            return True
        if path.startswith(('Pictures/', 'INFO/', 'prompts/', 'samples/')):
            return True
        return False

    try:
        result = subprocess.run(
            ['git', 'ls-files', '--cached', '--others', '--exclude-standard'],
            cwd=base_dir, capture_output=True, text=True, check=True
        )
        for line in result.stdout.splitlines():
            rel_path = line.replace('\\', '/')
            if not line or is_ignored(rel_path):
                continue
            file_path = os.path.join(base_dir, line)
            if os.path.isfile(file_path):
                checksums[rel_path] = calculate_checksum(file_path)
        return checksums
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    if excludes is None:
        excludes = {'__pycache__', '.git', 'node_modules', 'logs', 'brain'}

    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in excludes and not d.startswith('.')]
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, base_dir).replace('\\', '/')
            if is_ignored(rel_path):
                continue
            checksums[rel_path] = calculate_checksum(file_path)

    return checksums

def save_checksums(checksums, output_file='checksums.json'):
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    out_path = os.path.join(base_dir, output_file)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(checksums, f, indent=4)
