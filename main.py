'''
*********************************************************************         
         | De4py project : https://github.com/Fadi002/de4py |
*********************************************************************
'''
import os, msvcrt, eel, logging, requests, sys, platform, threading, psutil
from deobfuscators.detector import detect_obfuscator
from tkinter import Tk, filedialog
from dlls import shell
from util import tui, update, gen_path
from config import config

HANDLE = None
tui.clear_console()
tui.setup_logging()
print(tui.__BANNER__)
logging.info("Starting de4py")
eel.init('gui')



def cupdate():
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
                    exit(0)


@eel.expose
def protector_detector(file_path):
    try:
         result=detect_obfuscator(file_path)
         return result
    except Exception as e:
        return "Error : "+str(e)
    

@eel.expose
def file_explorer():
    root = Tk()
    root.withdraw()
    root.wm_attributes('-topmost', 1)
    file_path = filedialog.askopenfilename(filetypes=[("Python Files", "*.py")])
    return file_path


@eel.expose
def inject_shell(pid):
     global HANDLE
     l = shell.inject_shell(pid)
     if l[1]:
          HANDLE = l[0]
          threading.Thread(target=processchecker,args=(int(pid),)).start()
          return "pyshell injected"
     else:
          return "Failed to inject"


@eel.expose
def changelog():
    response = requests.get(config.__CHANGELOG_URL__)
    return response.text


@eel.expose
def processchecker(pid):
    global HANDLE
    while True:
        try:
            process = psutil.Process(pid)
        except psutil.NoSuchProcess:
            del HANDLE
            HANDLE=None
            eel.dead_process()
            break


@eel.expose
def dumpstring():
     path, filename = gen_path(__file__)
     write_to_pipe("DumpStrings||"+path)
     return "saved as "+ filename


@eel.expose
def getfunctions():
     path, filename = gen_path(__file__)
     write_to_pipe("GetFunctions||"+path)
     return "saved as "+ filename


@eel.expose
def execpython(path):
     write_to_pipe("ExecPY||"+path)
     return "Executed"


@eel.expose
def showconsole(pid):
     if shell.show_console(pid):
          return "DONE"
     else:
          return "FAILED"


@eel.expose
def get_info():
    pv = platform.python_version()
    arch = platform.architecture()[0]
    if not arch.startswith('64'):
        logging.warning("your pc arch is not x64 bit please note this tool was tested on windows x64 bit")
    system_info = platform.uname()
    oss = system_info.system+" "+system_info.release
    return {"pv":pv,"arch":arch,"os":oss}




@eel.expose
def write_to_pipe(message):
        global HANDLE
        os.write(HANDLE, message.encode())
        if read_from_pipe() == 'OK.':
             return True
        else: 
             return False


def read_from_pipe():
    global HANDLE
    message = os.read(HANDLE, 1024).decode()
    return message


def main():
    eel.start('index.html',size=(1024, 589))


if __name__ == '__main__':
    cupdate()
    main()
