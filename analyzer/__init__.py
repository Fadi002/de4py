import pefile
import re
import json
from hashlib import md5, sha1, sha256
from .pyinstxtractor import PyInstArchive
from .unpy2exe import unpy2exe

def detect_packer(file_path: str) -> tuple:
    """
    Analyzes a PE file to detect common Python packers like PyInstaller, Nuitka, or py2exe.
    
    Args:
        file_path (str): Path to the executable file.
        
    Returns:
        tuple: (bool success, str packer_type)
    """
    with pefile.PE(file_path) as pe:
        for section in pe.sections:
            if ".rdata" in section.Name.decode():
                n_offset = section.PointerToRawData
                n_size = section.SizeOfRawData
                with open(file_path, 'rb') as file:
                    file.seek(n_offset)
                    rdata_content = file.read(n_size)
                    
                    # Look for known packer-specific strings in the .rdata section
                    if b"PyInstaller: FormatMessageW failed." in rdata_content:
                        return (True, "pyinstaller")
                    elif b"__nuitka_version__" in rdata_content or b"NUITKA_ONEFILE_PARENT" in rdata_content:
                        return (True, "nuitka")
                    elif b"PY2EXE_VERBOSE" in rdata_content or \
                         b"py2exe failed to activate the activation context before loading a DLL" in rdata_content or \
                         b"py2exe failed to de-activate the activation context" in rdata_content:
                        return (True, "py2exe")
    return (False, "unsupported packer")

def get_file_hashs(file_path: str) -> str:
    """
    Calculates MD5, SHA1, and SHA256 hashes of a file.
    
    Args:
        file_path (str): Path to the file.
        
    Returns:
        str: Formatted string containing all three hashes.
    """
    file_bytes = open(file_path, "rb").read()
    md5_hash = md5(file_bytes).hexdigest()
    sha1_hash = sha1(file_bytes).hexdigest()
    sha256_hash = sha256(file_bytes).hexdigest()
    return f"MD5: {md5_hash}\nSHA1: {sha1_hash}\nSHA256: {sha256_hash}"

def unpack_file(file_path: str) -> str:
    """
    Attempts to unpack an executable based on its detected packer type.
    
    Args:
        file_path (str): Path to the executable to be unpacked.
        
    Returns:
        str: Status message indicating success or specific failure reason.
    """
    packer = detect_packer(file_path)
    if not packer[0]:
        return "invalid file or packer"
    
    if packer[1] == "pyinstaller":
        arch = PyInstArchive(file_path)
        if arch.open():
            if arch.checkFile():
                if arch.getCArchiveInfo():
                    arch.parseTOC()
                    arch.extractFiles(True)
                    arch.close()
                    return f"Successfully extracted pyinstaller archive: {file_path}\n" \
                           "You can now use a python decompiler on the pyc files in the extracted directory."
        arch.close()
        
    elif packer[1] == "nuitka":
        return "Nuitka is not supported at this moment."
        
    elif packer[1] == "py2exe":
        output_dir = file_path.split('/')[-1].split('.')[0] + "_extracted"
        unpy2exe(file_path, output_dir=output_dir)
        return f"Successfully extracted py2exe archive: {file_path}\n" \
               "Manual pyc header fixing may be required before decompilation."
               
    return "Failed to unpack"

def sus_strings_lookup(file_path: str) -> str:
    """
    Searches for suspicious strings (keywords, URLs, IPs) in a file.
    
    Args:
        file_path (str): Original file path.
        
    Returns:
        str: JSON formatted string containing lists of matched suspicious items.
    """
    regex = {
        'sus words': re.compile(r'(\btoken\b|grabber|stealer|steal|webhook|passwords|chrome|\bopera\b|opera gx|\bedge\b|brave|firefox|ipify|leveldb|appdata|localappdata|local storage|index.js|desktop-core|discord|discordcanary|discordptb|logger)'),
        'urls': re.compile(r'(http|https|ftp)\://([a-zA-Z0-9\-\.]+\.+[a-zA-Z]{2,3})(:[a-zA-Z0-9]*)?/?([a-zA-Z0-9\-\._\?\,\'/\\\+&amp;%\$#\=~@]*)'),
        'ips': re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
    }
    with open(file_path, 'rb') as file:
        content = file.read().decode(errors='ignore')
        matches = {key: [] for key in regex.keys()}
        for key, pattern in regex.items():
            for match in pattern.finditer(content):
                matches[key].append(match.group(0))
        return json.dumps(matches)

def all_strings_lookup(filename: str) -> str:
    """
    Extracts all printable ASCII strings (minimum length 4) from a binary file.
    
    Args:
        filename (str): Target binary file.
        
    Returns:
        str: Newline-separated list of extracted strings.
    """
    with open(filename, 'rb') as file:
        content = file.read().decode(errors='ignore')
    strings_regex = re.compile(r'[\x20-\x7E]{4,}')
    strings = strings_regex.findall(content)
    return '\n'.join(strings)
