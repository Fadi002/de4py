# thanks https://github.com/otakumods/pyobfuscate.com-deobfuscator/
import re
import ast
import base64
import hashlib
from Crypto.Cipher import AES

def derive_key_and_iv(password, salt):
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    key = dk[:16]
    iv = dk[16:]
    return key, iv

def aes_decrypt(encrypted_data, key) -> str:
    encrypted_data = base64.b85decode(encrypted_data)
    salt = encrypted_data[:8]
    key, iv = derive_key_and_iv(key, salt)
    cipher = AES.new(key, AES.MODE_CFB, iv)
    data = cipher.decrypt(encrypted_data[8:])
    return data.decode()

def pyobfuscate(file_path: str) -> str:
    filename = file_path.split('/')[-1].split('.')[0]
    with open(file_path, "r") as f:
        lines = f.readlines()
        for i, line in enumerate(lines, start=1):
            match = re.search(r'obfuscate = (.+)', line)
            if match:
                obfuscate_str = match.group(1)
                line_number = i
                break
        if(".replace('\\n','')]))") in obfuscate_str:
            pass
        else:
            while(".replace('\\n','')]))" not in obfuscate_str):
                obfuscate_str+=lines[line_number]
                line_number+=1
        obfuscate = str(eval(obfuscate_str))
        dictionary = ast.literal_eval(obfuscate)
        encrypted_data = list(dictionary.values())[0]
        key = list(dictionary.keys())[0][1:-1]
        deobfuscated = aes_decrypt(encrypted_data,key)
        f.close()
    with open(filename+"-cleaned.py", "w", encoding="utf-8") as f:
        f.write(deobfuscated)
        f.close()
    return "saved as "+filename+"-cleaned.py\n\n\n"+deobfuscated