import pefile
from hashlib import md5, sha1, sha256
from .pyinstxtractor import PyInstArchive
from .unpy2exe import unpy2exe
import re
import eel
import json

@eel.expose
def detect_packer(file_path: str) -> tuple:
    pe = pefile.PE(file_path)
    for section in pe.sections:
        if ".rdata" in section.Name.decode():
            n_offset = section.PointerToRawData
            n_size = section.SizeOfRawData
            with open(file_path, 'rb') as file:
                file.seek(n_offset)
                rdata_content = file.read(n_size)
                if b"PyInstaller: FormatMessageW failed." in rdata_content:
                    return (True, "pyinstaller")
                elif b"__nuitka_version__" in rdata_content or b"NUITKA_ONEFILE_PARENT" in rdata_content:
                    return (True, "nuitka")
                elif b"PY2EXE_VERBOSE" in rdata_content or b"py2exe failed to activate the activation context before loading a DLL" in rdata_content or b"py2exe failed to de-activate the activation context" in rdata_content:
                    return (True, "py2exe")
    return (False, "unsupprted packer")

@eel.expose
def get_file_hashs(file_path: str) -> str:
    file = open(file_path, "rb").read()
    md5_hash = md5(file).hexdigest()
    sha1_hash = sha1(file).hexdigest()
    sha256_hash = sha256(file).hexdigest()
    return "MD5: "+md5_hash+"\n"+"SHA1: "+sha1_hash+"\n"+"SHA256: "+sha256_hash

@eel.expose
def unpack_file(file_path: str) -> str:
    packer = detect_packer(file_path)
    if not packer[0]:
        return "invaild file or packer"
    else:
        if packer[1] == "pyinstaller":
            arch = PyInstArchive(file_path)
            if arch.open():
                if arch.checkFile():
                    if arch.getCArchiveInfo():
                        arch.parseTOC()
                        arch.extractFiles(True)
                        arch.close()
                        return "Successfully extracted pyinstaller archive: {0}".format(file_path)+"\nYou can now use a python decompiler on the pyc files within the extracted directory"
            arch.close()
        elif packer[1] == "nuitka":
            return "nuitka is not supported at this moment"
        elif packer[1] == "py2exe":
            unpy2exe(file_path,output_dir=file_path.split('/')[-1].split('.')[0]+"_extracted")
            return "Successfully extracted py2exe archive: {0}".format(file_path)+"\nYou need to fix the pyc header then use python decompiler"

@eel.expose
def sus_strings_lookup(file_path):
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

@eel.expose
def all_strings_lookup(filename):
    with open(filename, 'rb') as file:
        content = file.read().decode(errors='ignore')
    strings_regex = re.compile(r'[\x20-\x7E]{4,}') 
    strings = strings_regex.findall(content)
    unlisted_strings = '\n'.join(strings)
    return unlisted_strings