import sys, platform, socket, os, json, hashlib
sys.dont_write_bytecode = True
RED = "\033[91m"
GREEN = "\033[92m"
RESET = "\033[0m"

def colored_print(color, message):
    print(f"{color}{message}{RESET}")

def calculate_checksum(file_path, hash_algorithm="sha256", buffer_size=8192):
    hasher = hashlib.new(hash_algorithm)
    with open(file_path, 'rb') as file:
        buffer = file.read(buffer_size)
        while len(buffer) > 0:
            hasher.update(buffer)
            buffer = file.read(buffer_size)
    return hasher.hexdigest()

def load_checksums_from_json(json_file="checksums.json"):
    try:
        with open(json_file, 'r') as file:
            checksums = json.load(file)
        return checksums
    except FileNotFoundError:
        print(f"Error: The checksums file '{json_file}' not found.")
        return {}
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON in '{json_file}'. Make sure the file is valid JSON.")
        return {}
    
def verify_checksums(directory, checksums):
    invalid_files = [(os.path.join(root, file_name), checksums[os.path.join(root, file_name)])
                     for root, _, files in os.walk(directory)
                     for file_name in files
                     if file_name != 'checksums.json'
                     if os.path.join(root, file_name) in checksums
                     if checksums[os.path.join(root, file_name)] != calculate_checksum(os.path.join(root, file_name))]

    for file_path, expected_checksum in invalid_files:
        print(f"Error: Checksum mismatch for file '{file_path}'.")
    message = f"All files have valid checksums." if not invalid_files else f"{len(invalid_files)} file(s) have invalid checksums."
    colored_print(GREEN if not invalid_files else RED, message)



def check_import(module_name):
    try:
        __import__(module_name)
        colored_print(GREEN, f"Import '{module_name}' successful.")
        return True
    except ImportError:
        colored_print(RED, f"Import '{module_name}' failed.")
        input(f"{RESET}Press enter to continue\n")
        return False

def check_internet_connection():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        colored_print(GREEN, "Connected to the internet.")
        return True
    except OSError:
        colored_print(RED, "No internet connection.")
        return False


def check_python_version():
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 12):
        colored_print(GREEN, f"Python version {major}.{minor} is supported.")
        return False
    else:
        colored_print(RED, f"Python version {major}.{minor} is not supported. Required: 3.11-3.8")
        input(f"{RESET}Press enter to continue\n")
        return True

def check_system_architecture():
    system_architecture = platform.architecture()[0]
    if system_architecture == '64bit':
        colored_print(GREEN, f"System Architecture: {system_architecture}")
        return True
    else:
        colored_print(RED, f"Unsupported System Architecture: {system_architecture}")
        print("You need to compile the de4py tools for your device.")
        return False

def main():
    colored_print(RED, "BEFORE THE CHECKING PROCESS START IGNORE checksums.json or __pycache__ FILES !")
    input(f"{RED}Press enter to start{RESET}\n")
    print("Checking the environment...")
    if check_python_version() or not check_internet_connection() or not check_system_architecture():
        sys.exit(1)

    imports_to_check = [
        'os', 'msvcrt', 'eel', 'logging', 'requests', 'platform', 'threading', 'psutil', 'colorama', 'signal',
        'config', 'plugins', 'TUI.cli', 'deobfuscators.detector', 'dlls.shell', 'analyzer', 'time', 'inspect', 'importlib.util'
    ]
    for module in imports_to_check:
        if not check_import(module):
            sys.exit(1)

    print("Environment checks passed. Verifying checksums...")
    directory_to_check = "."
    checksums_json_file = "checksums.json" 
    loaded_checksums = load_checksums_from_json(checksums_json_file)
    verify_checksums(directory_to_check, loaded_checksums)
    sys.exit(1)
