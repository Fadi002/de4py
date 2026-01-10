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
    excludes = [
        'checksums.json', 'checksums.py', '.git', '__pycache__', 
        '.env', '.venv', 'logs', 'brain', 'ui/resources', 'config',
        'README.md', 'FAQ.md', 'LICENSE', '.github', 'cleanup.bat', 'requirements.txt',
        'logs/'
    ]
    
    checksums = {}
    for root, dirs, files in os.walk(directory):
        rel_root = os.path.relpath(root, directory).replace('\\', '/')
        if rel_root == '.': rel_root = ''

        # Filter directories to skip excluded ones
        dirs[:] = [d for d in dirs if d not in excludes and os.path.join(rel_root, d).replace('\\', '/') not in excludes]
        
        # Check if current directory itself is excluded (as a path)
        if rel_root in excludes:
            dirs[:] = []
            continue

        for file_name in files:
            rel_path = os.path.join(rel_root, file_name).replace('\\', '/')
            if file_name in excludes or rel_path in excludes:
                continue
                
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
