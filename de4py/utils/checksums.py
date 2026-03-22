# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import os
import hashlib
import json

def calculate_checksum(file_path, hash_algorithm="sha256", buffer_size=8192):
    hasher = hashlib.new(hash_algorithm)
    with open(file_path, 'rb') as file:
        buffer = file.read(buffer_size)
        while len(buffer) > 0:
            hasher.update(buffer)
            buffer = file.read(buffer_size)
    return hasher.hexdigest()

def generate_checksums(directory, hash_algorithm="sha256"):
    excluded_dirs = {
        'env', 'venv', 'logs', 'brain', '__pycache__', 
        '__MACOSX', 'tests', 'INFO', 'Pictures', 
    }
    excluded_paths = {
        'ui/resources', 'config'
    }
    excluded_files = {
        'checksums.json', 'checksums.py', '.DS_Store', 'cleanup.bat', 'LICENSE',
        'crowdin.yml', 'pyproject.toml'
    }
    excluded_extensions = (
        '.pyc', '.pyo', '.pyd', '.log', '.tmp', '.bak', '.md', '.txt'
    )
    
    checksums = {}
    for root, dirs, files in os.walk(directory):
        rel_root = os.path.relpath(root, directory).replace('\\', '/')
        if rel_root == '.': rel_root = ''

        # Filter out excluded directories, hidden directories (starts with .), and explicit paths
        dirs[:] = [
            d for d in dirs 
            if d not in excluded_dirs 
            and not d.startswith('.')
            and os.path.join(rel_root, d).replace('\\', '/') not in excluded_paths
        ]

        for file_name in files:
            if file_name in excluded_files or file_name.endswith(excluded_extensions) or file_name.startswith('.'):
                continue
                
            rel_path = os.path.join(rel_root, file_name).replace('\\', '/')
            file_path = os.path.join(root, file_name)
            
            checksum = calculate_checksum(file_path, hash_algorithm)
            checksums[rel_path] = checksum # Use relative path for consistency
    return checksums

def save_checksums_to_json(checksums, output_json="checksums.json"):
    with open(output_json, 'w') as json_file:
        json.dump(checksums, json_file, indent=4) # Changed indent to 4 for consistency

def main():
    directory_to_scan = "."
    hash_algorithm_to_use = "sha256"

    print(f"Calculating checksums for files in {directory_to_scan}...")
    checksums = generate_checksums(directory_to_scan, hash_algorithm_to_use)

    output_json_file = "checksums.json"
    print(f"Saving checksums to {output_json_file}...")
    save_checksums_to_json(checksums, output_json_file)

    print(f"Successfully mapped {len(checksums)} files.")
    print("Checksums calculation and saving completed.")

if __name__ == "__main__":
    main()