from .erebus.deobfuscator.deobfuscator import Deobfuscator, Result
from .erebus.deobfuscator.unwrapper import unwrap

def Hyperion(file_path: str) -> str:
    code = open(file_path, 'r',encoding='utf-8').read()
    return Deobfuscator(unwrap(code)).deobfuscate().code