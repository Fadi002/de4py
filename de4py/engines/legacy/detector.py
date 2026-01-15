import re
import traceback

# Lazy wrappers to avoid importing all engines at startup

def run_pyobfuscate(path):
    from de4py.engines.legacy.pyobfuscate import pyobfuscate
    return pyobfuscate(path)

def run_PlusOBF(path):
    from de4py.engines.legacy.PlusOBF import PlusOBF
    return PlusOBF(path)

def run_wodx(path):
    from de4py.engines.legacy.wodx import wodx
    return wodx(path)

def run_BlankOBF(path):
    from de4py.engines.legacy.blankOBF import BlankOBF
    return BlankOBF(path)

def run_Hyperion(path):
    from de4py.engines.legacy.Hyperion import Hyperion
    return Hyperion(path)

def run_jawbreaker(path):
    from de4py.engines.legacy.jawbreaker import jawbreaker
    return jawbreaker(path)

def run_freecodingtools(path):
    from de4py.engines.legacy.freecodingtools import freecodingtools
    return freecodingtools(path)

def run_devtool(path):
    from de4py.engines.legacy.devtool import devtool
    return devtool(path)

obfuscators = [
    ("pyobfuscate", re.compile(r'\s*pyobfuscate\s*'), run_pyobfuscate),
    ("PlusOBF", re.compile(r"exec\(\"\"\.join\(\[chr\(len\(i\)\) for i in d\]\)\)"), run_PlusOBF),
    ("wodx", re.compile(r'(?:__NO_NO){23}'), run_wodx),
    ("BlankOBF", re.compile(r"import\s*base64,\s*lzma;\s*exec\(compile\(lzma\.decompress\(base64\.b64decode\(b'([A-Za-z0-9+/=]+)'\)\)\s*,\s*\"<string>\"\s*,\s*\"exec\"\)\)"), run_BlankOBF),
    ("Hyperion", re.compile(r'__obfuscator__\s*=\s*[\'\"]\s*Hyperion\s*[\'\"]'), run_Hyperion),
    ('jawbreaker', re.compile(r'([a-zA-Z_]\w{3})\s*=\s*([^;]+);'), run_jawbreaker),
    ('freecodingtools', re.compile(r"^_\s*=\s*lambda\s+__\s*:\s*__import__\('zlib'\)\.decompress\(__import__\('base64'\)\.b64decode\(__\[::-1]\)\);exec\(\(\_\)"), run_freecodingtools),
    ('devtool', re.compile(r'\b(magic|love|god|destiny|joy|trust)\b'), run_devtool)
]


def detect_obfuscator(file_path):
    try:
        with open(file_path, 'r', encoding='utf8') as f:
            file_data = f.read()
    except Exception as e:
        return f"Failed to read file: {e}"

    for name, regex, func in obfuscators:
        if regex.search(file_data):
            try:
                return func(file_path)
            except Exception as e:
                return f"Failed to deobfuscate:\n{e}"
    
    return "Cant detect the obfuscator\nsend the sample to add it https://de4py.000.pe/"
