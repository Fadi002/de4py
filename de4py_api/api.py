"""The docs
1- Analyzer docs from line 7 to 59
2- Deobfuscator docs from line 61 to 104
3- Pyshell docs from line 106 to 157
"""

"""
The `Analyzer` class provides various methods for analyzing a file.

Usage:
    analyzer = Analyzer(file_path)

    # Detect the packer used in the file
    packer = analyzer.detect_packer()

    # Get the file hashes (MD5, SHA1, SHA256)
    hashes = analyzer.get_file_hashes()

    # Unpack the file if it is packed with a supported packer
    unpack_result = analyzer.unpack_file()

    # Look up suspicious strings in the file
    sus_strings = analyzer.sus_strings_lookup()

    # Look up all strings in the file
    all_strings = analyzer.all_strings_lookup()

Methods:

    - detect_packer() -> str:
        Detects the packer used in the file.

        Returns:
            str: The packer name.

    - get_file_hashes() -> str:
        Gets the file hashes (MD5, SHA1, SHA256).

        Returns:
            str: The hashes as a string.

    - unpack_file() -> str:
        Unpacks the file if it is packed with a supported packer.

        Returns:
            str: A success message or an error message.

    - sus_strings_lookup() -> Dict[str, list]:
        Looks up suspicious strings in the file.

        Returns:
            dict: The matches as a dictionary.

    - all_strings_lookup() -> str:
        Looks up all strings in the file.

        Returns:
            str: The strings as a string.
"""

"""
The `Deobfuscator` class is responsible for detecting and deobfuscating obfuscated code in Python files.

Methods:
    - auto_deobfuscator(file_path: str) -> Optional[str]:
        Automatically detects the obfuscator used in a Python file and returns the name of the obfuscator.

        Parameters:
            - file_path (str): The path to the Python file.

        Returns:
            Optional[str]: The deobfuscated code of the detected obfuscator, or None if no obfuscator is detected.

    - get_deobfuscator(obfuscator_name: str) -> Optional[Tuple[str, str, Callable]]:
        Retrieves a specific deobfuscator based on its name and returns information about the deobfuscator.

        Parameters:
            - obfuscator_name (str): The name of the obfuscator.

        Returns:
            Optional[Tuple[str, str, Callable]]: Information about the deobfuscator as a tuple (name, regex signature, a function you can call to deobfuscate a file),
            or None if the obfuscator is not found.

Example usage:

# Create an instance of the Deobfuscator class
deobfuscator = Deobfuscator()

# Shows a list of supported obfuscators
print(deobfuscator.supported_obfuscators_list)

# Automatically detect the obfuscator used in a Python file and deobfuscate it
file_path = "path/to/python/file.py"
deobfuscated_code = deobfuscator.auto_deobfuscator(file_path)
print(deobfuscated_code)

# Retrieve a specific deobfuscator based on its name
obfuscator_name = "pyobfuscate"
deobfuscator_info = deobfuscator.get_deobfuscator(obfuscator_name)
if deobfuscator_info is not None:
    name, regex_signature, deobfuscate_func = deobfuscator_info
    print(f"Deobfuscator Name: {name}")
    print(f"Regex Signature: {regex_signature}")
    print(f"Deobfuscate Function: {deobfuscate_func}")
else:
    print(f"No deobfuscator found with the name {obfuscator_name}")
"""

"""
De4py Pyshell wrapper API

This class provides a wrapper API for interacting with the De4py Pyshell tool. It allows you to perform various operations on a target process, such as injecting the pyshell dll, executing Python files, and more.

Usage:
    To use this class, create an instance of the Pyshell class with the process PID parameter. Then, you can call the different methods to perform specific operations on the target process.

Example:
    # Create an instance of the Pyshell class
    pyshell = Pyshell(process_pid=1234)

    # Inject the pyshell dll into the target process
    pyshell.inject()

    # Execute a Python file in the target process
    pyshell.execute_python_file('/path/to/python/file.py')

    # Detach the shell from the target process
    pyshell.deattach()

Methods:
    - show_hidden_console(self) -> bool:
        Shows the hidden console of the target process.

    - inject(self) -> bool:
        Injects the pyshell dll into the target process.

    - stealth_inject(self) -> bool:
        Performs a stealth injection of the pyshell dll into the target process.

    - dump_strings(self) -> str:
        Dumps strings from the target process and returns the filename of the dumped file.

    - get_all_functions(self) -> str:
        Retrieves all functions from the target process and returns the filename of the retrieved file.

    - execute_python_file(self, file_path: str) -> bool:
        Executes a Python file in the target process.

    - remove_exit_function(self) -> bool:
        Removes the exit function from the target process.

    - deattach(self) -> bool:
        Detaches the shell from the target process.

    - pyshell_gui(self) -> bool:
        Launches the Pyshell GUI in the target process.

    - force_crash_process(self) -> bool:
        Forces a crash in the target process.
"""

from typing import Optional, List, Tuple, Callable, Dict
import sys, os
sys.dont_write_bytecode = True
_DE4PY_FILES_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(_DE4PY_FILES_PATH)
from deobfuscators.detector import detect_obfuscator, obfuscators
from analyzer import detect_packer, get_file_hashs, unpack_file, sus_strings_lookup, all_strings_lookup
import json, psutil, dlls.shell, random, string

def _gen_path(d):
    random_filename = ''.join(random.choice(string.ascii_letters) for i in range(random.randint(10, 15)))+'.txt'
    file_path = os.path.join(os.path.dirname(d), random_filename)
    return os.path.abspath(file_path), random_filename


class Analyzer:
    """
    The `Analyzer` class provides various methods for analyzing a file.
    """
    def __init__(self, file_path: str) -> None:
        """
        Initializes the `Analyzer` class with a file path.

        Args:
            file_path (str): The path to the file.

        Raises:
            FileNotFoundError: If the file path is invalid or doesn't exist.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError("The path doesn't exist or is invalid")
        elif not os.path.isfile(file_path):
            raise FileNotFoundError("The path is not a file or is invalid")

        self.file_path = file_path

    def detect_packer(self) -> str:
        """
        Detects the packer used in the file.

        Returns:
            str: The packer name.
        """
        return detect_packer(self.file_path)[1]

    def get_file_hashes(self) -> str:
        """
        Gets the file hashes (MD5, SHA1, SHA256).

        Returns:
            str: The hashes as a string.
        """
        return get_file_hashs(self.file_path)

    def unpack_file(self) -> str:
        """
        Unpacks the file if it is packed with a supported packer.

        Returns:
            str: A success message or an error message.
        """
        return unpack_file(self.file_path)

    def sus_strings_lookup(self) -> Dict[str, list]:
        """
        Looks up suspicious strings in the file.

        Returns:
            dict: The matches as a dictionary.
        """
        return json.loads(sus_strings_lookup(self.file_path))

    def all_strings_lookup(self) -> str:
        """
        Looks up all strings in the file.

        Returns:
            str: The strings as a string.
        """
        return all_strings_lookup(self.file_path)

class Deobfuscator:
    """
    The `Deobfuscator` class is responsible for detecting and deobfuscating obfuscated code in Python files.
    It provides methods to automatically detect the obfuscator used in a file and to retrieve a specific deobfuscator based on its name.
    """
    supported_obfuscators_list: List[Tuple[str, str, Callable]] = obfuscators

    def auto_deobfuscator(self, file_path: str) -> Optional[str]:
        """
        Automatically detects the obfuscator used in a Python file and returns the name of the obfuscator.

        Args:
            file_path (str): The path to the Python file.

        Returns:
            Optional[str]: The deobfuscated cpde of the detected obfuscator, or None if no obfuscator is detected.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError("The path doesn't exist or is invalid")
        elif not os.path.isfile(file_path):
            raise FileNotFoundError("The path is not a file or is invalid")

        return detect_obfuscator(file_path=file_path)

    def get_deobfuscator(self, obfuscator_name: str) -> Optional[Tuple[str, str, Callable]]:
        """
        Retrieves a specific deobfuscator based on its name and returns information about the deobfuscator.

        Args:
            obfuscator_name (str): The name of the obfuscator.

        Returns:
            Optional[Tuple[str, str, Callable]]: Information about the deobfuscator as a tuple (name, regex signature, a function you can call to deobfuscate a file),
            or None if the obfuscator is not found.
        """
        obfuscator_name_lower = obfuscator_name.lower()
        return next(
            (
                (name, regex_signature, func)
                for name, regex_signature, func in self.supported_obfuscators_list
                if name.lower() == obfuscator_name_lower
            ),
            None,
        )

class Pyshell:
    """
    De4py Pyshell wrapper API
    """
    def __init__(self, process_pid: int) -> None:
        """
        Initializes a new instance of the Pyshell class with the specified process PID and binaries path.
        """
        self.process_pid = process_pid
        self.binaries_path = os.path.join(_DE4PY_FILES_PATH, 'dlls')
        self.PYSHELL_HANDLE: Optional[int] = None
        self._is_pid_alive(self.process_pid)

    def _is_pid_alive(self, pid: int) -> None:
        """
        Checks if the specified process PID is alive.
        """
        if not psutil.pid_exists(pid):
            self.PYSHELL_HANDLE = None
            raise Exception("Invalid pid")

    def _write_to_pipe(self, message: str) -> bool:
        """
        Writes a message to the target process via a named pipe.
        """
        if self.PYSHELL_HANDLE is None:
            return False
        self._is_pid_alive(self.process_pid)
        os.write(self.PYSHELL_HANDLE, message.encode())
        response = self._read_from_pipe()
        return response == 'OK.'

    def _read_from_pipe(self) -> str:
        """
        Reads a message from the target process via a named pipe.
        """
        if self.PYSHELL_HANDLE is None:
            return False
        self._is_pid_alive(self.process_pid)
        message = os.read(self.PYSHELL_HANDLE, 1024).decode()
        return message

    def show_hidden_console(self) -> bool:
        """
        Shows the hidden console of the target process.
        """
        self._is_pid_alive(self.process_pid)
        return dlls.shell.show_console(pid=self.process_pid)

    def inject(self) -> bool:
        """
        Injects the pyshell dll into the target process.
        """
        self._is_pid_alive(self.process_pid)
        if self.PYSHELL_HANDLE is None:
            injector_status = dlls.shell.inject_shell(str(self.process_pid), self.binaries_path)
            if injector_status[1]:
                self.PYSHELL_HANDLE = injector_status[0]
                return True
        return False

    def stealth_inject(self) -> bool:
        """
        Performs a stealth injection of the pyshell dll into the target process.
        """
        self._is_pid_alive(self.process_pid)
        if self.PYSHELL_HANDLE is None:
            injector_status = dlls.shell.stealth_inject_shell(str(self.process_pid), self.binaries_path)
            if injector_status[1]:
                self.PYSHELL_HANDLE = injector_status[0]
                return True
        return False

    def dump_strings(self) -> str:
        """
        Dumps strings from the target process and returns the filename of the dumped file.
        """
        if self.PYSHELL_HANDLE is None:
            return "Please inject pyshell first using inject() or stealth_inject()"
        self._is_pid_alive(self.process_pid)
        path, filename = _gen_path(_DE4PY_FILES_PATH)
        self._write_to_pipe("DumpStrings||" + path)
        return filename

    def get_all_functions(self) -> str:
        """
        Retrieves all functions from the target process and returns the filename of the retrieved file.
        """
        if self.PYSHELL_HANDLE is None:
            return "Please inject pyshell first using inject() or stealth_inject()"
        self._is_pid_alive(self.process_pid)
        path, filename = _gen_path(_DE4PY_FILES_PATH)
        self._write_to_pipe("GetFunctions||" + path)
        return filename

    def execute_python_file(self, file_path: str) -> bool:
        """
        Executes a Python file in the target process.
        """
        if self.PYSHELL_HANDLE is None:
            return False
        self._is_pid_alive(self.process_pid)
        self._write_to_pipe("ExecPY||" + file_path)
        return True

    def remove_exit_function(self) -> bool:
        """
        Removes the exit function from the target process.
        """
        if self.PYSHELL_HANDLE is None:
            return False
        self._is_pid_alive(self.process_pid)
        self._write_to_pipe("delExit")
        return True

    def deattach(self) -> bool:
        """
        Detaches the shell from the target process.
        """
        if self.PYSHELL_HANDLE is None:
            return False
        self._is_pid_alive(self.process_pid)
        self.PYSHELL_HANDLE = None
        self._write_to_pipe("DeattachDLL")
        return True

    def pyshell_gui(self) -> bool:
        """
        Launches the Pyshell GUI in the target process.
        """
        if self.PYSHELL_HANDLE is None:
            return False
        self._is_pid_alive(self.process_pid)
        self._write_to_pipe("PyshellGUI")
        return True

    def force_crash_process(self) -> bool:
        """
        Forces a crash in the target process.
        """
        if self.PYSHELL_HANDLE is None:
            return False
        self._is_pid_alive(self.process_pid)
        self._write_to_pipe("ForceCrash")
        return True