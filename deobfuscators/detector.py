import re
from .jawbreaker import jawbreaker
from .wodx import wodx
from .devtool import devtool
from .blankOBF import BlankOBF
from .PlusOBF import PlusOBF
from .Hyperion import Hyperion
obfuscators = [
    ("PlusOBF",r"exec\(\"\"\.join\(\[chr\(len\(i\)\) for i in d\]\)\)",PlusOBF),
    ("wodx", r'(?:__NO_NO){23}', wodx),
    ("BlankOBF", r"import\s*base64,\s*lzma;\s*exec\(compile\(lzma\.decompress\(base64\.b64decode\(b'([A-Za-z0-9+/=]+)'\)\)\s*,\s*\"<string>\"\s*,\s*\"exec\"\)\)", BlankOBF),
    ("Hyperion", r'__obfuscator__\s*=\s*[\'\"]\s*Hyperion\s*[\'\"]', Hyperion),
    ('jawbreaker', r'([a-zA-Z_]\w{3})\s*=\s*([^;]+);', jawbreaker)
]
def detect_obfuscator(file_path) -> str:
    file_data = open(file_path,'r',encoding='utf8').read()
    for obfuscator in obfuscators:
        if re.search(obfuscator[1],file_data):
            return (obfuscator[2])(file_path)
    return "Cant detect the obfuscator\nsend the sample to add it https://de4py.000.pe/"
