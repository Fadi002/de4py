from pathlib import Path
import subprocess
import os
import time
import string
import random
import shutil
import logging

logger = logging.getLogger(__name__)

DEFAULT_BIN_PATH = Path(__file__).parent.absolute()

def execute_command(command):
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        exit_code = process.wait()
        return exit_code
    except FileNotFoundError as e:
        logger.error(f"Command not found: {command}. Error: {e}")
        return -1
    except Exception as e:
        logger.error(f"Execution error: {e}")
        return -1

def inject_shell(pid, bp=None):
    try:
        pid = int(pid)
    except (ValueError, TypeError):
        return (None, False)
    
    bin_path = Path(bp) if bp else DEFAULT_BIN_PATH
    injector = bin_path / "NativeInjector.exe"
    pyshell_dll = bin_path / "pyshell.dll"
    
    if not injector.exists():
        logger.error(f"Injector not found at {injector}")
        return (None, False)

    exit_code = execute_command([str(injector), str(pyshell_dll.absolute()), str(pid)])
    
    if exit_code == 0:
        time.sleep(1)
        try:
            handle = os.open('\\\\.\\pipe\\de4py', os.O_RDWR)
            return (handle, True)
        except OSError as e:
            logger.error(f"Failed to open pipe: {e}")
            return (None, False)
    else:
        logger.error(f"Injector failed with code {exit_code}")
        return (None, False)

def stealth_inject_shell(pid, bp=None):
    try:
        pid = int(pid)
    except (ValueError, TypeError):
        return (None, False)
    
    bin_path = Path(bp) if bp else DEFAULT_BIN_PATH
    injector = bin_path / "NativeInjector.exe"
    pyshell_dll = bin_path / "pyshell.dll"
    
    if not injector.exists():
        return (None, False)

    file_name = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(random.randint(5,20)))
    temp_injector = bin_path / f"{file_name}.exe"
    
    try:
        shutil.copy2(str(injector), str(temp_injector))
        exit_code = execute_command([str(temp_injector), 'StealthInjection', str(pyshell_dll.absolute()), str(pid)])
    finally:
        if temp_injector.exists():
            os.remove(str(temp_injector))
            
    if exit_code == 0:
        time.sleep(1)
        try:
            handle = os.open('\\\\.\\pipe\\de4py', os.O_RDWR)
            return (handle, True)
        except OSError:
            return (None, False)
    else:
        return (None, False)

def show_console(pid, bp=None):
    try:
        pid = int(pid)
    except (ValueError, TypeError):
        return False
    
    bin_path = Path(bp) if bp else DEFAULT_BIN_PATH
    injector = bin_path / "NativeInjector.exe"
    
    if not injector.exists():
        return False

    exit_code = execute_command([str(injector), 'Showconsole', str(pid)])
    return exit_code == 0
