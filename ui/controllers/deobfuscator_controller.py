def run_detect_obfuscator(file_path):
    from deobfuscators.detector import detect_obfuscator
    return detect_obfuscator(file_path)
