import subprocess
import os
import time
import string
import random
import shutil
# I HATE CTYPES THAT'S WHY I USED C++ TO MAKE THE INJECTOR XD
def execute_command(command):
    process = subprocess.Popen(command ,stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    exit_code = process.wait()
    return exit_code

def inject_shell(pid, bp=None):
    if bp == None:
        exit_code = execute_command(['dlls\\NativeInjector.exe', os.path.abspath("dlls\\pyshell.dll"), pid])
    else:
        exit_code = execute_command([f'{bp}\\NativeInjector.exe', os.path.abspath(f"{bp}\\pyshell.dll"), pid])
    if exit_code == 0:
        time.sleep(1)
        handle = os.open('\\\\.\\pipe\\de4py', os.O_RDWR)
        return (handle, True)
    else:
        return (None, False)

def stealth_inject_shell(pid, bp=None):
    file_name = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(random.randint(5,20)))
    if bp == None:
        shutil.copy2('dlls\\NativeInjector.exe', f'dlls\\{file_name}.exe')
        exit_code = execute_command([f'dlls\\{file_name}.exe', 'StealthInjection', os.path.abspath("dlls\\pyshell.dll"), pid])
        os.remove(f'dlls\\{file_name}.exe')
    else:
        shutil.copy2(f'{bp}\\NativeInjector.exe', f'{bp}\\{file_name}.exe')
        exit_code = execute_command([f'{bp}\\{file_name}.exe', 'StealthInjection', os.path.abspath(f"{bp}\\pyshell.dll"), pid])
        os.remove(f'{bp}\\{file_name}.exe')
    if exit_code == 0:
        time.sleep(1)
        handle = os.open('\\\\.\\pipe\\de4py', os.O_RDWR)
        return (handle, True)
    else:
        return (None, False)
    


def show_console(pid):
    exit_code = execute_command('dlls\\NativeInjector.exe Showconsole '+str(pid))
    if exit_code == 0:
        time.sleep(1)
        return True
    else:
        return False
