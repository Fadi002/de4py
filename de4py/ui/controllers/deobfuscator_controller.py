def run_detect_obfuscator(file_path):
    from de4py.engines.legacy.detector import detect_obfuscator
    return detect_obfuscator(file_path)
