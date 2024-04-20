'''
*********************************************************************         
         | De4py project : https://github.com/Fadi002/de4py |
*********************************************************************
'''

import sys
sys.dont_write_bytecode = True
if len(sys.argv) > 1 and sys.argv[1] == "--test":
     from util.test import main
     main()
import os, msvcrt, eel, logging, requests, platform, threading, psutil, colorama, signal, zlib
from config import config
from plugins import plugins
from util import tui, update, gen_path, rpc
if len(sys.argv) > 1 and sys.argv[1] == "--cli":
    from TUI import cli
    cli.start()
from deobfuscators.detector import detect_obfuscator, obfuscators
from tkinter import Tk, filedialog
from dlls import shell
from analyzer import detect_packer, unpack_file, get_file_hashs, sus_strings_lookup, all_strings_lookup
import ctypes
import traceback
def signal_handler(sig, frame):
    print(f"{colorama.Fore.CYAN}Exiting....{colorama.Style.RESET_ALL}")
    rpc.KILL_THREAD = True
    ctypes.windll.kernel32.ExitProcess(0)
signal.signal(signal.SIGINT, signal_handler)
HANDLE = None
HANDLE_analyzer = None
STOP_THREADS = False
tui.clear_console()
tui.setup_logging()
print(tui.__BANNER__)
logging.info("Starting de4py")
eel.init('gui')


def cupdate() -> None:
    if update.check_update():
            logging.info("You are using the latest version")
    else:
        logging.warning("There's a new version. Are you sure you want to use this version?")
        tui.fade_type('Answer [y/n]\n')
        if not input(">>> ").lower() == 'y':
             logging.warning("Download it from here : https://github.com/Fadi002/de4py")
             logging.warning("Press any key to exit...")
             while True:
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    logging.warning("Exiting...")
                    rpc.KILL_THREAD = True
                    ctypes.windll.kernel32.ExitProcess(0)


@eel.expose
def protector_detector(file_path) -> str:
    try:
         logging.info("Trying to deobfuscate a file")
         result=detect_obfuscator(file_path)
         return result
    except Exception as e:
        logging.error(f"Error: {traceback.format_exc()}")
        return "Error : "+str(e)
    

@eel.expose
def file_explorer() -> str:
    root = Tk()
    root.withdraw()
    root.wm_attributes('-topmost', 1)
    file_path = filedialog.askopenfilename(filetypes=[("Python Files", "*.py"),("Python compiled Files", "*.pyc"),("exe Files", "*.exe"),("All Files", "*.*")])
    return file_path


@eel.expose
def inject_shell(pid) -> str:
     global HANDLE
     l = shell.inject_shell(pid)
     if l[1]:
          HANDLE = l[0]
          threading.Thread(target=processchecker,args=(int(pid),)).start()
          return "pyshell injected"
     else:
          return "Failed to inject"


@eel.expose
def stealth_inject_shell(pid) -> str:
     global HANDLE
     l = shell.stealth_inject_shell(pid)
     if l[1]:
          HANDLE = l[0]
          threading.Thread(target=processchecker,args=(int(pid),)).start()
          return "pyshell injected"
     else:
          return "Failed to inject"

@eel.expose
def changelog() -> str:
    response = requests.get(config.__CHANGELOG_URL__)
    return response.text


@eel.expose
def processchecker(pid) -> str:
    global HANDLE
    global HANDLE_analyzer
    global STOP_THREADS
    while True:
        try:
            process = psutil.Process(pid)
        except psutil.NoSuchProcess:
            STOP_THREADS=True
            del HANDLE
            del HANDLE_analyzer
            HANDLE=None
            HANDLE_analyzer=None
            eel.dead_process()
            break


@eel.expose
def dumpstring() -> str:
     path, filename = gen_path(__file__)
     write_to_pipe("DumpStrings||"+path)
     return "saved as "+ filename

@eel.expose
def openanalyzerhandle() -> str:
     global HANDLE_analyzer
     write_to_pipe("GetAnalyzerHandle")
     HANDLE_analyzer = os.open('\\\\.\\pipe\\de4py_analyzer', os.O_RDWR)
     threading.Thread(target=update_hooks_output, args=()).start()
     return "Executed | click the button again to open the menu"

@eel.expose
def getfunctions() -> str:
     path, filename = gen_path(__file__)
     write_to_pipe("GetFunctions||"+path)
     return "saved as "+ filename


@eel.expose
def execpython(path) -> str:
     write_to_pipe("ExecPY||"+path)
     return "Executed"


@eel.expose
def showconsole(pid) -> str:
     if shell.show_console(pid):
          return "DONE"
     else:
          return "FAILED"


@eel.expose
def get_info() -> str:
    pv = platform.python_version()
    arch = platform.architecture()[0]
    if not arch.startswith('64'):
        logging.warning("your pc arch is not x64 bit please note this tool was tested on windows x64 bit")
    system_info = platform.uname()
    oss = system_info.system+" "+system_info.release
    return {"pv":pv,"arch":arch,"os":oss}

@eel.expose
def write_to_pipe(message) -> str:
        global HANDLE
        os.write(HANDLE, message.encode())
        response = read_from_pipe()
        if response == 'OK.':
             return True
        else:
             return False
        
def write_to_pipe_detailed(message) -> str:
        global HANDLE
        os.write(HANDLE, message.encode())
        response = read_from_pipe()
        return response

def read_from_pipe() -> str:
    global HANDLE
    message = os.read(HANDLE, 1024).decode()
    return message

@eel.expose
def monitorfileshook(var) -> str:
     if var:
          write_to_pipe("MonitorFiles")
          return "Monitor files hook has been installed"
     else:
          write_to_pipe("UnMonitorFiles")
          return "Monitor files hook has been uninstalled"

@eel.expose
def monitorprocesseshook(var) -> str:
     if var:
          write_to_pipe("MonitorProcesses")
          return "Monitor processes hook has been installed"
     else:
          write_to_pipe("UnMonitorProcesses")
          return "Monitor processes hook has been uninstalled"

@eel.expose
def monitorconnectionshook(var) -> str:
     if var:
          write_to_pipe("MonitorConnections")
          return "Monitor connections hook has been installed"
     else:
          write_to_pipe("UnMonitorConnections")
          return "Monitor connections hook has been uninstalled"
     
def dealwithfilesocket() -> str:
     if not os.path.exists(os.getcwd() + "\\SocketDump.txt"):
          open(os.getcwd() + "\\SocketDump.txt", 'w').close()

def dealwithfilessl():
     if not os.path.exists(os.getcwd() + "\\OpenSSLDump.txt"):
          open(os.getcwd() + "\\OpenSSLDump.txt", 'w').close()

@eel.expose
def dumpsocketcontent(var) -> str:
     if var:
          dealwithfilesocket()
          response = write_to_pipe("DumpConnections||" + os.getcwd() + "\\SocketDump.txt")
          return "starting to dump sockets content to the current script directory."
     else:
          response = write_to_pipe("StopDumpingConnections")
          return "stopped dumping socket content."



@eel.expose
def pycdumper(var) -> str:
     if var:
          dir_name = f"dumps-{''.join(random.choices(string.digits, k=7))}"
          os.makedirs(dir_name, exist_ok=True)
          directory_path = os.path.abspath(dir_name).rstrip(os.path.sep)
          with open(directory_path+'\\fixer.py','w') as f:
               # just write the fixer its open source you can decompress it
               f.write(zlib.decompress(b'x\xdamR=k\xc30\x10\xdd\r\xf9\x0f\x87\x17\xd9`\xd4d\xe9\x10\x9a\xa1\xd0\xd0\xce\xa5\x9d\xd2`\\\xfbd\x0blKH\xca\x17!\xff\xbd\x17GN\xd4\xb4Zt\xd2=\xbdwzw\xb2\xd3\xca8P6\x03}\xc8K\xd5i\xd9b\x06\xb6\xd98\xd9\xd2~\xb0\x93H\nh\xb1O(\xe6\x85\xa9\xb7)<-`6\x9fD@K\xf6z\xe3\x92\xf8\xd3\x165\xceA\xc8=\x1a\xae\x0f\x14\xb4\x98;\x95\xd3\x05\x1d\xcb\xaf>N/\xf83\t\xee\xa5K\xa6tQ\xa1\x80\xd7\xe5G\xfe\xb6|~Y\xbe\'\xa9\xe7\xdcI\xd7\x80\xd2$\xc9\xba\xa2\x96%1\xb0\x0c:U\xe1\x82\xedX\n\x85\x05\xe1\xa1\x00\x82\xef\x8ct\x980\xce9\xf3"\xb7\x9fp\xbf\x07LWLY\x94\r\xc2\x02X\x9e\xfbC\x9e\xb3K\xd2\xbf\xaa(\xab,o\xa5u\x954\x89G\xa5\xab\xe9\xfa\xbeP\x11\x92<\x1c\xc7\xf7\xa7k\xdd\xe6\xfb\xbe\xf0\x06\x8b\n\r)\x08n(Lf\x8f\xa3E\x83\xf7\xdct\xce ^E/9\xaa\xc6`\xa7\xb6\xff|\xc8\xa0\xdb\x98\xde\xd3N\xa2!M\xec\xa1\xbf\x93H\x1b\xd9\xbbD\xc4\xfa\xe0\x1a\xd5S\xf7\x84\x9a\xc3\xf1\xdc\x94-\x1a+U\x7f\x8a\x03\x94\xa3v\xa3\x1b\x9a\tN\x9d\xbb\x0b\x8e,\xf3\x95\x1f\xc7\x81X\xcd\xd6\xbf\x9em\xac\xec\xeb\x00I\nC5\x03(\x98\x8c\xb3\xbb:\x18,\xe2\xc9\x06\xa3.\x86\x10\xf8fp\x88\x01\xb6\xf3n\x929\xa3\x9f\x14\xfaI\x18\xb4\xd2?\xd7\x810%\x7f\x00\x1a\xfd\xec\xea').decode())
          response = write_to_pipe("DumpPyc||" + directory_path)
          return f"starting to dump pyc files to dumps folder ({directory_path})."
     else:
          response = write_to_pipe("StopDumpingPyc")
          return "stopped dumping pyc files"

@eel.expose
def dumpopensslcontent(var) -> str:
     if var:
          dealwithfilessl()
          return write_to_pipe_detailed("DumpOpenSSL||" + os.getcwd() + "\\OpenSSLDump.txt")
     else:
          return write_to_pipe_detailed("StopDumpingSSL")

def update_hooks_output():
    global HANDLE_analyzer
    global STOP_THREADS
    try:
         while True:
            if STOP_THREADS:
                 STOP_THREADS=False
                 break
            message = os.read(HANDLE_analyzer, 4096).decode()
            eel.add_text_winapihook(message)
    except Exception as e:
         logging.error(f"Error occurred while reading from HANDLE_analyzer: {str(e)}")

@eel.expose
def get_plugins():
    code = plugins.html_result
    plugins.html_result = ''
    return code

@eel.expose
def load_plugins():
     if config.__LOAD_PLUGINS__:
         loaded_plugins = plugins.load_plugins()
         for plugin in loaded_plugins:
             if plugin["type"] == "deobfuscator":
                  plugin = plugin["instance"]
                  obfuscators.append((plugin.plugin_name, plugin.regex, plugin.deobfuscator_function))
                  plugins.build_html({"name":plugin.plugin_name, "creator":plugin.creator, "link":plugin.link})
                  logging.info(f"Loaded deobfuscator plugin {plugin.plugin_name}")
             elif plugin["type"] == "theme":
                  plugin = plugin["instance"]
                  plugins.build_html({"name":plugin.plugin_name, "creator":plugin.creator, "link":plugin.link})
                  eel.applyCSS(plugin.css)
                  logging.info(f"Loaded theme plugin {plugin.plugin_name}")
     else:
          plugins.html_result = """
<div class="center">
<h1>Plugins are disabled</h1>
</div>
"""

@eel.expose
def STEALTH_TITLE():return config.__STEALTH_TITLE__


def main() -> None:
    if config.__STEALTH_TITLE__:
         logging.info("Stealth mode is on")
         ctypes.windll.kernel32.SetConsoleTitleW([''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(10,40))) for _ in range(random.randint(10,40))][0])
    else:
         logging.info("Stealth mode is off")
    logging.info("Starting the ui")
    eel.start('index.html', size=(1024, 589), port=5456)
    rpc.KILL_THREAD = True

@eel.expose
def update_config(key, value):
     config.update_json(key, value)

@eel.expose
def get_config():
    return config.get_config()


import psutil
import random
import string


if __name__ == '__main__':
     try:
          cupdate()
     except Exception as e:
          logging.error("Failed to check the update")
     if config.__RPC__:
          rpc.start_RPC()
     main()