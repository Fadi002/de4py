# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.





from typing import Optional, List, Tuple, Callable, Dict
import sys, os
sys.dont_write_bytecode = True
_DE4PY_FILES_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
from de4py.utils import shell as _shell_utils
from de4py.engines.legacy.detector import detect_obfuscator, obfuscators
from de4py.engines.analyzers import detect_packer, get_file_hashs, unpack_file, sus_strings_lookup, all_strings_lookup
import json, psutil

from de4py.utils.fs import gen_path as _gen_path


class Analyzer:
    def __init__(self, file_path: str) -> None:
        if not os.path.exists(file_path):
            raise FileNotFoundError("The path doesn't exist or is invalid")
        elif not os.path.isfile(file_path):
            raise FileNotFoundError("The path is not a file or is invalid")

        self.file_path = file_path

    def detect_packer(self) -> str:
        return detect_packer(self.file_path)[1]

    def get_file_hashes(self) -> str:
        return get_file_hashs(self.file_path)

    def unpack_file(self) -> str:
        return unpack_file(self.file_path)

    def sus_strings_lookup(self) -> Dict[str, list]:
        return json.loads(sus_strings_lookup(self.file_path))

    def all_strings_lookup(self) -> str:
        return all_strings_lookup(self.file_path)

class Deobfuscator:
    supported_obfuscators_list: List[Tuple[str, str, Callable]] = obfuscators

    def auto_deobfuscator(self, file_path: str) -> Optional[str]:
        if not os.path.exists(file_path):
            raise FileNotFoundError("The path doesn't exist or is invalid")
        elif not os.path.isfile(file_path):
            raise FileNotFoundError("The path is not a file or is invalid")

        return detect_obfuscator(file_path=file_path)

    def get_deobfuscator(self, obfuscator_name: str) -> Optional[Tuple[str, str, Callable]]:
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
    def __init__(self, process_pid: int) -> None:
        self.process_pid = process_pid
        self.binaries_path = os.path.join(_DE4PY_FILES_PATH, 'utils', 'dlls')  # native binaries dir
        self.PYSHELL_HANDLE: Optional[int] = None
        self._is_pid_alive(self.process_pid)

    def _is_pid_alive(self, pid: int) -> None:
        if not psutil.pid_exists(pid):
            self.PYSHELL_HANDLE = None
            raise Exception("Invalid pid")

    def _write_to_pipe(self, message: str) -> bool:
        if self.PYSHELL_HANDLE is None:
            return False
        self._is_pid_alive(self.process_pid)
        os.write(self.PYSHELL_HANDLE, message.encode())
        response = self._read_from_pipe()
        return response == 'OK.'

    def _read_from_pipe(self) -> str:
        if self.PYSHELL_HANDLE is None:
            return ""
        self._is_pid_alive(self.process_pid)
        message = os.read(self.PYSHELL_HANDLE, 1024).decode()
        return message

    def show_hidden_console(self) -> bool:
        self._is_pid_alive(self.process_pid)
        return _shell_utils.show_console(pid=self.process_pid, bp=self.binaries_path)

    def inject(self) -> bool:
        self._is_pid_alive(self.process_pid)
        if self.PYSHELL_HANDLE is None:
            injector_status = _shell_utils.inject_shell(str(self.process_pid), self.binaries_path)
            if injector_status[1]:
                self.PYSHELL_HANDLE = injector_status[0]
                return True
        return False

    def stealth_inject(self) -> bool:
        self._is_pid_alive(self.process_pid)
        if self.PYSHELL_HANDLE is None:
            injector_status = _shell_utils.stealth_inject_shell(str(self.process_pid), self.binaries_path)
            if injector_status[1]:
                self.PYSHELL_HANDLE = injector_status[0]
                return True
        return False

    def dump_strings(self) -> str:
        if self.PYSHELL_HANDLE is None:
            return "Please inject pyshell first using inject() or stealth_inject()"
        self._is_pid_alive(self.process_pid)
        path, filename = _gen_path(_DE4PY_FILES_PATH)
        self._write_to_pipe("DumpStrings||" + path)
        return filename

    def get_all_functions(self) -> str:
        if self.PYSHELL_HANDLE is None:
            return "Please inject pyshell first using inject() or stealth_inject()"
        self._is_pid_alive(self.process_pid)
        path, filename = _gen_path(_DE4PY_FILES_PATH)
        self._write_to_pipe("GetFunctions||" + path)
        return filename

    def execute_python_file(self, file_path: str) -> bool:
        if self.PYSHELL_HANDLE is None:
            return False
        self._is_pid_alive(self.process_pid)
        self._write_to_pipe("ExecPY||" + file_path)
        return True

    def remove_exit_function(self) -> bool:
        if self.PYSHELL_HANDLE is None:
            return False
        self._is_pid_alive(self.process_pid)
        self._write_to_pipe("delExit")
        return True

    def detach(self) -> bool:
        if self.PYSHELL_HANDLE is None:
            return False
        self._is_pid_alive(self.process_pid)
        self._write_to_pipe("DeattachDLL")
        self.PYSHELL_HANDLE = None
        return True

    def pyshell_gui(self) -> bool:
        if self.PYSHELL_HANDLE is None:
            return False
        self._is_pid_alive(self.process_pid)
        self._write_to_pipe("PyshellGUI")
        return True

    def force_crash_process(self) -> bool:
        if self.PYSHELL_HANDLE is None:
            return False
        self._is_pid_alive(self.process_pid)
        self._write_to_pipe("ForceCrash")
        return True