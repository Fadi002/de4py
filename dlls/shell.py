import subprocess
import os
import time
# I HATE CTYPES THAT'S WHY I USED C++ TO MAKE THE INJECTOR XD
def execute_command(command):
    process = subprocess.Popen(command ,stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    exit_code = process.wait()
    return exit_code

def inject_shell(pid):
    exit_code = execute_command(['dlls\\NativeInjector.exe', os.path.abspath("dlls\\pyshell.dll"), pid])
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