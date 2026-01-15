from pathlib import Path
import re
import ast
import base64
import hashlib
import logging
from Crypto.Cipher import AES

logger = logging.getLogger(__name__)

def derive_key_and_iv(password, salt):
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    key = dk[:16]
    iv = dk[16:]
    return key, iv

def aes_decrypt(encrypted_data, key) -> str:
    try:
        encrypted_data = base64.b85decode(encrypted_data)
        salt = encrypted_data[:8]
        key, iv = derive_key_and_iv(key, salt)
        cipher = AES.new(key, AES.MODE_CFB, iv)
        data = cipher.decrypt(encrypted_data[8:])
        return data.decode(errors='replace')
    except Exception as e:
        logger.error(f"AES decryption failed: {e}")
        return ""

def pyobfuscate(file_path: str) -> str:
    path = Path(file_path)
    output_filename = path.stem + "-cleaned.py"
    
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        
        obfuscate_str = ""
        found = False
        for i, line in enumerate(lines):
            match = re.search(r'obfuscate = (.+)', line)
            if match:
                obfuscate_str = match.group(1)
                # Continue collecting if it's multi-line
                temp_i = i
                while temp_i + 1 < len(lines) and ".replace('\\n','')]))" not in obfuscate_str:
                    temp_i += 1
                    obfuscate_str += lines[temp_i]
                found = True
                break
        
        if not found:
            return "Could not find obfuscated content in the file."

        # Safety first: attempt to use ast.literal_eval for the structure
        try:
            # Often the content is eval'd because it might be a double-encoded string
            # We'll try to parse it safely.
            if obfuscate_str.startswith("str("):
                # Peel str() and try to parse what's inside
                inner_str = obfuscate_str[4:-1]
                obfuscate_val = ast.literal_eval(inner_str)
            else:
                obfuscate_val = ast.literal_eval(obfuscate_str)
                
            dictionary = ast.literal_eval(obfuscate_val)
        except Exception as e:
            logger.warning(f"Static analysis failed for pyobfuscate, falling back to discovery: {e}")
            return f"Static analysis failed: {e}. The obfuscation pattern might be too complex for safe parsing."

        encrypted_data = list(dictionary.values())[0]
        key = list(dictionary.keys())[0][1:-1]
        deobfuscated = aes_decrypt(encrypted_data, key)
        
        if not deobfuscated:
            return "Deobfuscation failed (decryption returned empty)."

        output_path = path.parent / output_filename
        output_path.write_text(f"# Cleaned with de4py | https://github.com/Fadi002/de4py\n{deobfuscated}", encoding="utf-8")
        
        return f"Saved as {output_filename}\n\n\n# Cleaned with de4py\n{deobfuscated}"
        
    except Exception as e:
        logger.error(f"pyobfuscate engine failed: {e}")
        return f"Engine failed: {e}"