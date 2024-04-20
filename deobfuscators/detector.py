import re
from .jawbreaker import jawbreaker
from .wodx import wodx
from .devtool import devtool
from .blankOBF import BlankOBF
from .PlusOBF import PlusOBF
from .Hyperion import Hyperion
from .pyobfuscate import pyobfuscate
from .devtool import devtool
from .freecodingtools import freecodingtools
import traceback, requests

obfuscators = [
    ("pyobfuscate", re.compile(r'\s*pyobfuscate\s*'), pyobfuscate),
    ("PlusOBF", re.compile(r"exec\(\"\"\.join\(\[chr\(len\(i\)\) for i in d\]\)\)"), PlusOBF),
    ("wodx", re.compile(r'(?:__NO_NO){23}'), wodx),
    ("BlankOBF", re.compile(r"import\s*base64,\s*lzma;\s*exec\(compile\(lzma\.decompress\(base64\.b64decode\(b'([A-Za-z0-9+/=]+)'\)\)\s*,\s*\"<string>\"\s*,\s*\"exec\"\)\)"), BlankOBF),
    ("Hyperion", re.compile(r'__obfuscator__\s*=\s*[\'\"]\s*Hyperion\s*[\'\"]'), Hyperion),
    ('jawbreaker', re.compile(r'([a-zA-Z_]\w{3})\s*=\s*([^;]+);'), jawbreaker),
    ('freecodingtools', re.compile(r"^_\s*=\s*lambda\s+__\s*:\s*__import__\('zlib'\)\.decompress\(__import__\('base64'\)\.b64decode\(__\[::-1]\)\);exec\(\(\_\)"), freecodingtools),
    ('devtool', re.compile(r'\b(magic|love|god|destiny|joy|trust)\b'), devtool)
]


def detect_obfuscator(file_path):
    file_data = open(file_path,'r',encoding='utf8').read()
    for obfuscator in obfuscators:
        if re.search(obfuscator[1],file_data):
            try:
                return (obfuscator[2])(file_path)
            except Exception as e:
                return "Failed to deobfuscate:\n"+e
    return "Cant detect the obfuscator\nsend the sample to add it https://de4py.000.pe/"
