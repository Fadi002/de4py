'''
*********************************************************************         
         | De4py project : https://github.com/Fadi002/de4py |
*********************************************************************
'''
import os, msvcrt, eel, logging, requests, sys, platform, threading, psutil, colorama, signal
from config import config
from util import tui, update, gen_path, rpc
if len(sys.argv) > 1 and sys.argv[1] == "--cli":
    from TUI import cli
    cli.start()
from deobfuscators.detector import detect_obfuscator
from tkinter import Tk, filedialog
from dlls import shell
from analyzer import detect_packer, unpack_file, get_file_hashs, sus_strings_lookup, all_strings_lookup
import time 
def signal_handler(sig, frame):
    print(f"{colorama.Fore.CYAN}Exiting....{colorama.Style.RESET_ALL}")
    rpc.KILL_THREAD = True
    sys.exit(0)
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
                    sys.exit(0)


@eel.expose
def protector_detector(file_path) -> str:
    try:
         result=detect_obfuscator(file_path)
         return result
    except Exception as e:
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
def changelog() -> str:
    response = requests.get(config.__CHANGELOG_URL__)
    return response.text


@eel.expose
def processchecker(pid) -> str:
    global HANDLE
    global HANDLE_analyzer
    while True:
        try:
            process = psutil.Process(pid)
        except psutil.NoSuchProcess:
            del HANDLE
            del HANDLE_analyzer
            HANDLE=None
            HANDLE_analyzer=None
            eel.dead_process()
            STOP_THREADS=True
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

def main() -> None:
    # eel.start('index.html',size=(1024, 589),port=3456)
    eel.start('index.html',size=(1024, 589),port=5456)
    rpc.KILL_THREAD = True


if __name__ == '__main__':
     try:
          cupdate()
     except Exception as e:
          print(e)
          logging.error("Failed to check the update")
     if config.__RPC__:
          rpc.start_RPC()
     main()
