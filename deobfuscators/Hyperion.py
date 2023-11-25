from .erebus.deobfuscator.deobfuscator import Deobfuscator, Result
from .erebus.deobfuscator.unwrapper import unwrap

def Hyperion(file_path: str) -> str:
    code = open(file_path, 'r',encoding='utf-8').read()
    deobfuscated = Deobfuscator(unwrap(code)).deobfuscate().code
    filename = file_path.split('/')[-1].split('.')[0]
    with open(filename+"-cleaned.py", 'w', encoding="utf8") as f:
        f.write(deobfuscated)
        f.close()
    return "saved as "+filename+"-cleaned.py\n\n\n"+deobfuscated