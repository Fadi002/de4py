import sys
import platform
import socket
import os
import json
import hashlib
import logging
import argparse
from importlib import import_module

# Avoid pycache
sys.dont_write_bytecode = True

# Colors for terminal
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
WHITE = "\033[97m"
RESET = "\033[0m"
BOLD = "\033[1m"

def colored_print(color, message, bold=False):
    prefix = BOLD if bold else ""
    print(f"{prefix}{color}{message}{RESET}")

class De4pyTester:
    """
    Advanced environment and integrity tester for de4py.
    """
    def __init__(self, target_dir=".", checksum_file="checksums.json"):
        self.target_dir = os.path.abspath(target_dir)
        self.checksum_file = checksum_file
        self.results = []
        self.critical_fail = False

    def log_result(self, category, name, success, message=""):
        status = "PASSED" if success else "FAILED"
        color = GREEN if success else RED
        self.results.append({
            "category": category,
            "name": name,
            "status": status,
            "message": message
        })
        if not success:
            colored_print(RED, f"  [!] {category}: {name} - {message}")
        else:
            colored_print(GREEN, f"  [+] {category}: {name}")

    def run_environment_checks(self):
        colored_print(BLUE, "\n--- Environment Diagnostics ---", bold=True)
        
        # 1. Python Version
        major, minor = sys.version_info[:2]
        is_py_ver_ok = (3, 8) <= (major, minor) <= (3, 14)
        msg = f"Detecting Python {major}.{minor}"
        self.log_result("System", "Python Version", is_py_ver_ok, f"Found {major}.{minor}. Expected 3.8-3.14")

        # 2. Architecture
        arch = platform.architecture()[0]
        is_arch_ok = arch == '64bit'
        self.log_result("System", "Architecture", is_arch_ok, f"Found {arch}. 64-bit required for native components.")

        # 3. Internet
        has_internet = False
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            has_internet = True
        except OSError:
            pass
        self.log_result("Network", "Internet Access", has_internet, "Offline mode might limit deobfuscation features.")

    def run_dependency_checks(self):
        colored_print(BLUE, "\n--- Dependency Analysis ---", bold=True)
        dependencies = [
            'PySide6', 'requests', 'psutil', 'colorama', 'Crypto', 
            'logging', 'platform', 'threading', 'signal', 'json',
            'importlib.util', 'inspect'
        ]
        
        for dep in dependencies:
            try:
                mod = import_module(dep)
                version = getattr(mod, '__version__', 'detected')
                self.log_result("Dependency", dep, True, f"v{version}")
            except ImportError:
                self.log_result("Dependency", dep, False, f"Module '{dep}' not found. Try: pip install {dep}")
                self.critical_fail = True

    def run_integrity_checks(self):
        colored_print(BLUE, "\n--- Integrity Verification ---", bold=True)
        if not os.path.exists(self.checksum_file):
            self.log_result("Integrity", "Checksum File", False, f"'{self.checksum_file}' missing.")
            return

        try:
            with open(self.checksum_file, 'r') as f:
                checksums = json.load(f)
        except Exception as e:
            self.log_result("Integrity", "Checksum Load", False, str(e))
            return

        mismatched = []
        for rel_path, expected in checksums.items():
            full_path = os.path.join(self.target_dir, rel_path)
            if not os.path.exists(full_path):
                mismatched.append(f"Missing: {rel_path}")
                continue
            
            actual = self.calculate_checksum(full_path)
            if actual != expected:
                mismatched.append(f"Mismatch: {rel_path}")

        success = len(mismatched) == 0
        msg = f"All {len(checksums)} files verified." if success else f"{len(mismatched)} failures."
        self.log_result("Integrity", "File Checksums", success, "\n".join(mismatched))

    def calculate_checksum(self, file_path):
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def generate_checksums(self, excludes=None):
        if excludes is None:
            excludes = [
                'checksums.json', 'checksums.py', '.git', '__pycache__', '.pytest_cache', 
                '.env', '.venv', 'logs', 'brain', '.antigravityignore',
                'ui/resources', 'config', 'README.md', 'FAQ.md', 'LICENSE'
            ]
        
        colored_print(YELLOW, f"Generating checksums for {self.target_dir}...")
        checksums = {}
        for root, dirs, files in os.walk(self.target_dir):
            rel_root = os.path.relpath(root, self.target_dir).replace('\\', '/')
            if rel_root == '.': rel_root = ''

            # Skip excluded base directories
            if any(rel_root.startswith(ex.replace('\\', '/')) for ex in excludes if os.path.isdir(os.path.join(self.target_dir, ex))):
                dirs[:] = []
                continue

            # Filter directories
            dirs[:] = [d for d in dirs if d not in excludes and os.path.join(rel_root, d).replace('\\', '/') not in excludes]
            
            for file in files:
                rel_path = os.path.join(rel_root, file).replace('\\', '/')
                if file in excludes or rel_path in excludes:
                    continue
                
                full_path = os.path.join(root, file)
                checksums[rel_path] = self.calculate_checksum(full_path)
        
        with open(self.checksum_file, 'w') as f:
            json.dump(checksums, f, indent=4)
        
        colored_print(GREEN, f"Successfully mapped {len(checksums)} files to {self.checksum_file}")

    def print_summary(self):
        colored_print(BLUE, "\n" + "="*40, bold=True)
        colored_print(BLUE, "        DE4PY DIAGNOSTICS SUMMARY", bold=True)
        colored_print(BLUE, "="*40 + "\n", bold=True)
        
        passed = [r for r in self.results if r['status'] == "PASSED"]
        failed = [r for r in self.results if r['status'] == "FAILED"]
        
        for r in passed:
            print(f" {GREEN}[OK]{RESET} {r['category']:<12} | {r['name']}")
        
        for r in failed:
            print(f" {RED}[!!]{RESET} {r['category']:<12} | {r['name']:<15} -> {r['message']}")

        print(f"\nResults: {len(passed)} passed, {len(failed)} failed.")
        
        if failed:
            colored_print(RED, "\n[!] SOME CHECKS FAILED. Please review the environment.", bold=True)
            if self.critical_fail:
                colored_print(RED, "    CRITICAL: Missing core dependencies.", bold=True)
        else:
            colored_print(GREEN, "\n[+] ENVIRONMENT IS HEALTHY.", bold=True)

def main(argv=None):
    parser = argparse.ArgumentParser(description="de4py Diagnostic Tool")
    parser.add_argument("--generate-checksums", action="store_true", help="Regenerate the checksums.json file")
    parser.add_argument("--target", default=".", help="Target directory to check")
    parser.add_argument("--no-integrity", action="store_true", help="Skip checksum verification")
    args = parser.parse_args(argv)

    tester = De4pyTester(target_dir=args.target)

    if args.generate_checksums:
        tester.generate_checksums()
        return

    colored_print(CYAN, "=== de4py System Integrity Check ===", bold=True)
    
    tester.run_environment_checks()
    tester.run_dependency_checks()
    
    if not args.no_integrity:
        tester.run_integrity_checks()

    tester.print_summary()
    
    if any(r['status'] == "FAILED" for r in tester.results):
        sys.exit(1)

if __name__ == "__main__":
    main()
