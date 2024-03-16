import re
from .jawbreaker import jawbreaker
from .wodx import wodx
from .devtool import devtool
from .blankOBF import BlankOBF
from .PlusOBF import PlusOBF
from .Hyperion import Hyperion
from .pyobfuscate import pyobfuscate
from .devtool import devtool
import traceback, requests

obfuscators = [
    ("pyobfuscate", re.compile(r'\s*pyobfuscate\s*'), pyobfuscate),
    ("PlusOBF", re.compile(r"exec\(\"\"\.join\(\[chr\(len\(i\)\) for i in d\]\)\)"), PlusOBF),
    ("wodx", re.compile(r'(?:__NO_NO){23}'), wodx),
    ("BlankOBF", re.compile(r"import\s*base64,\s*lzma;\s*exec\(compile\(lzma\.decompress\(base64\.b64decode\(b'([A-Za-z0-9+/=]+)'\)\)\s*,\s*\"<string>\"\s*,\s*\"exec\"\)\)"), BlankOBF),
    ("Hyperion", re.compile(r'__obfuscator__\s*=\s*[\'\"]\s*Hyperion\s*[\'\"]'), Hyperion),
    ('jawbreaker', re.compile(r'([a-zA-Z_]\w{3})\s*=\s*([^;]+);'), jawbreaker),
    ('devtool', re.compile(r'(?:import\s+\w+(?:\s*,\s*\w+)*)|(\b(?:magic|love|god|destiny|joy|trust)\b)|(\b[a-zA-Z_]\w*\b)'), devtool)
]
def send_error(exctype, value, tb):
     try:
         error_info = {
              "type": str(exctype),
              "message": str(value),
              "traceback": traceback.format_exception(exctype, value, tb)
              }
         api_url = "https://de4py-api.onrender.com/error"
         response = requests.post(api_url, json=error_info, timeout=60) 
         if response.status_code == 200:
              print("Error has been reported")
         else:
              print("Failed to send error Status code:", response.status_code)
     except:
          pass

def detect_obfuscator(file_path, senderr):
    file_data = open(file_path,'r',encoding='utf8').read()
    for obfuscator in obfuscators:
        if re.search(obfuscator[1],file_data):
            try:
                return (obfuscator[2])(file_path)
            except Exception as e:
                traceback.print_exc()
                if senderr:send_error(type(e), e, e.__traceback__)
                return "Failed to deobfuscate:\n"+e
    return "Cant detect the obfuscator\nsend the sample to add it https://de4py.000.pe/"
