# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import colorama, platform, signal, os
from tkinter import Tk, filedialog
from de4py.engines.legacy.detector import detect_obfuscator
from de4py.engines.analyzers import (
    detect_packer,
    unpack_file,
    get_file_hashs,
    sus_strings_lookup,
    all_strings_lookup,
)
from de4py.config.config import settings
from de4py.utils import tui, rpc, fade_type
from de4py.utils.errors import custom_error
from de4py.utils.platform_utils import supports
from de4py._meta import PROJECT_SIGNATURE
from colorama import Fore, Style
import socket
import sys
import requests
import time
from de4py.de4py_api.api import Pyshell

_PROJECT_SIGNATURE = PROJECT_SIGNATURE

def signal_handler(sig, frame):
    tui.clear_console()
    banner()
    print(f"{colorama.Fore.CYAN}Exiting....{colorama.Style.RESET_ALL}")
    rpc.KILL_THREAD = True
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
sys.excepthook = custom_error
change_log = None
platform_info = None
file_path = None


def home_tab():
    tui.shell_prompt()
    choice = input()
    commands = {
        "help": "Displays a list of available commands.",
        "deobfuscator": "Executes the deobfuscator tool.",
        "pyshell": "Opens the Python shell.",
        "analyzer": "Runs the code analyzer tool.",
        "about": "Displays information about the program.",
        "changelog": "Displays the change log with details of each version and the corresponding updates.",
        "neofetch": "Displays your PC info + the tool info",
        "clear": "Clear the console.",
        "exit": "Exits the program.",
    }
    if choice == "help":
        print(f"\n{Fore.CYAN}=== Available Commands ==={Style.RESET_ALL}")
        for cmd, desc in commands.items():
            print(f"{Fore.YELLOW}{cmd}{Style.RESET_ALL} - {desc}")
        print(f"{Fore.CYAN}=========================={Style.RESET_ALL}\n")
    elif choice == "deobfuscator":
        deobfuscator_tab()
    elif choice == "pyshell":
        if supports("pyshell"):
            pyshell_tab()
        else:
            print(f"{Fore.RED}PyShell is only available on Windows.{Style.RESET_ALL}")
    elif choice == "analyzer":
        analyzer_tab()
    elif choice == "about":
        from de4py._meta import print_about
        print_about()
    elif choice == "neofetch":
        neofetch()
    elif choice == "changelog":
        changelog_display()
    elif choice == "clear":
        tui.clear_console()
        banner()
    elif choice == "exit":
        tui.clear_console()
        banner()
        print(f"{colorama.Fore.CYAN}Exiting....{colorama.Style.RESET_ALL}")
        sys.exit(0)
    else:
        print(f"{Fore.RED}Unknown command{Style.RESET_ALL}")


def deobfuscator_tab():
    global file_path
    file_path = None
    tui.clear_console()
    banner()
    commands = {
        "set_file": "Select a file to deobfuscate.",
        "start": "Executes the deobfuscator.",
        "back": "Back to the home page.",
        "clear": "Clear the console.",
        "exit": "Exits the program.",
    }
    while 1:
        tui.shell_prompt("deobfuscator")
        choice = input()
        if choice == "help":
            print(f"\n{Fore.CYAN}=== Available Commands ==={Style.RESET_ALL}")
            for cmd, desc in commands.items():
                print(f"{Fore.YELLOW}{cmd}{Style.RESET_ALL} - {desc}")
            print(f"{Fore.CYAN}=========================={Style.RESET_ALL}\n")
        elif choice == "set_file":
            file_path = file_explorer()
            if file_path:
                print(f"{Fore.CYAN}Selected file path: {file_path}{Style.RESET_ALL}\n")

            else:
                print(f"{Fore.YELLOW}No file selected.{Style.RESET_ALL}\n")
        elif choice == "start":
            if file_path:
                print(
                    f"{Fore.CYAN}Starting the Deobfuscation process...{Style.RESET_ALL}"
                )
                print(f"{Fore.CYAN}Deobfuscation result:{Style.RESET_ALL}\n")
                print(detect_obfuscator(file_path))
                print("\n")
            else:
                print(f"{Fore.YELLOW}No file selected.{Style.RESET_ALL}\n")
        elif choice == "back":
            tui.clear_console()
            banner()
            break
        elif choice == "clear":
            tui.clear_console()
            banner()
        elif choice == "exit":
            tui.clear_console()
            banner()
            print(f"{colorama.Fore.CYAN}Exiting....{colorama.Style.RESET_ALL}")
            sys.exit(0)
        else:
            print(f"{Fore.RED}Unknown command{Style.RESET_ALL}")


def analyzer_tab():
    global file_path
    file_path = None
    tui.clear_console()
    banner()
    commands = {
        "set_file": "Select a file to analyze.",
        "exe_packer_detector": "Detect the exe packer (ex. py2exe).",
        "exe_unpacker": "Unpack the exe if its supported",
        "sus_strings_lookup": "Search for the sus strings like ips links.",
        "all_strings": "Search for all readable strings in the file.",
        "get_file_hashs": "Gives you the MD5, SHA1 and SHA256 of the file.",
        "clear": "Clear the console.",
        "exit": "Exits the program.",
    }
    while 1:
        tui.shell_prompt("analyzer")
        choice = input()
        if choice == "help":
            print(f"\n{Fore.CYAN}=== Available Commands ==={Style.RESET_ALL}")
            for cmd, desc in commands.items():
                print(f"{Fore.YELLOW}{cmd}{Style.RESET_ALL} - {desc}")
            print(f"{Fore.CYAN}=========================={Style.RESET_ALL}\n")
        elif choice == "set_file":
            file_path = file_explorer()
            if file_path:
                print(f"{Fore.CYAN}Selected file path: {file_path}{Style.RESET_ALL}\n")

            else:
                print(f"{Fore.YELLOW}No file selected.{Style.RESET_ALL}\n")
        elif choice == "exe_packer_detector":
            if file_path:
                print(f"{Fore.CYAN}Starting the detecting process...{Style.RESET_ALL}")
                print(f"{Fore.CYAN}packer detector result:{Style.RESET_ALL}\n")
                print(detect_packer(file_path))
                print("\n")
            else:
                print(f"{Fore.YELLOW}No file selected.{Style.RESET_ALL}\n")
        elif choice == "exe_unpacker":
            if file_path:
                print(f"{Fore.CYAN}Starting the unpacking process...{Style.RESET_ALL}")
                print(f"{Fore.CYAN}unpacker result:{Style.RESET_ALL}\n")
                print(unpack_file(file_path))
                print("\n")
            else:
                print(f"{Fore.YELLOW}No file selected.{Style.RESET_ALL}\n")
        elif choice == "sus_strings_lookup":
            if file_path:
                print(
                    f"{Fore.CYAN}Starting the sus strings lookup process...{Style.RESET_ALL}"
                )
                print(f"{Fore.CYAN}search result:{Style.RESET_ALL}\n")
                print(sus_strings_lookup(file_path))
                print("\n")
            else:
                print(f"{Fore.YELLOW}No file selected.{Style.RESET_ALL}\n")
        elif choice == "all_strings":
            if file_path:
                print(
                    f"{Fore.CYAN}Starting the all strings lookup process...{Style.RESET_ALL}"
                )
                print(f"{Fore.CYAN}search result:{Style.RESET_ALL}\n")
                print(all_strings_lookup(file_path))
                print("\n")
            else:
                print(f"{Fore.YELLOW}No file selected.{Style.RESET_ALL}\n")
        elif choice == "get_file_hashs":
            if file_path:
                print(
                    f"{Fore.CYAN}Starting to get the file hashs process...{Style.RESET_ALL}"
                )
                print(f"{Fore.CYAN}hashs result:{Style.RESET_ALL}\n")
                print(get_file_hashs(file_path))
            else:
                print(f"{Fore.YELLOW}No file selected.{Style.RESET_ALL}\n")
        elif choice == "back":
            tui.clear_console()
            banner()
            break
        elif choice == "clear":
            tui.clear_console()
            banner()
        elif choice == "exit":
            tui.clear_console()
            banner()
            print(f"{colorama.Fore.CYAN}Exiting....{colorama.Style.RESET_ALL}")
            sys.exit(0)
        else:
            print(f"{Fore.RED}Unknown command{Style.RESET_ALL}")


def file_explorer() -> str:
    root = Tk()
    root.withdraw()
    root.wm_attributes("-topmost", 1)
    file_path = filedialog.askopenfilename(
        filetypes=[
            ("Python Files", "*.py"),
            ("Python compiled Files", "*.pyc"),
            ("exe Files", "*.exe"),
            ("All Files", "*.*"),
        ]
    )
    return file_path


def get_info() -> str:
    pv = platform.python_version()
    arch = platform.architecture()[0]
    system_info = platform.uname()
    oss = system_info.system + " " + system_info.release
    return {"pv": pv, "arch": arch, "os": oss}


def fetch_info():
    global change_log
    global platform_info
    if not platform.architecture()[0].startswith("64"):
        tui.fade_type(
            f"{colorama.Fore.YELLOW}your pc arch is not x64 bit. native components are tested on x64 systems.{colorama.Style.RESET_ALL}\n"
        )
    change_log = requests.get(settings.changelog_url).json()
    platform_info = get_info()


def changelog_display():
    print("\n")
    for version_data in change_log:
        version_element = (
            f"{Fore.CYAN}Version {version_data['version']}{Style.RESET_ALL}\n"
        )
        changes_list = ""
        for change in version_data["changes"]:
            changes_list += f"  • {change}\n"
        version_element += changes_list
        print(version_element)
    print("\n")


def cupdate() -> None:
    from de4py.utils.version import is_newer
    from de4py.updater.verify import fetch_remote_checksums, verify_zip
    from de4py.updater.apply import backup_current, apply_update, restart_app
    from de4py.updater.download import DOWNLOAD_DIR

    try:
        r = requests.get(settings.version_url, timeout=8)
        r.raise_for_status()
        remote_version = r.text.strip()
    except Exception:
        tui.fade_type(
            f"{colorama.Fore.YELLOW}Could not check for updates.{colorama.Style.RESET_ALL}\n"
        )
        return

    if not is_newer(remote_version, settings.version):
        tui.fade_type(
            f"{colorama.Fore.CYAN}You are using the latest version ({settings.version}).{colorama.Style.RESET_ALL}\n"
        )
        return

    tui.fade_type(
        f"{colorama.Fore.YELLOW}New version available: {remote_version} (current: {settings.version}){colorama.Style.RESET_ALL}\n"
    )
    tui.fade_type("Download and install? [y/n]\n>>> ")
    if input().strip().lower() != "y":
        return

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    filename = f"de4py-{remote_version}.zip"
    dest = os.path.join(DOWNLOAD_DIR, filename)
    url = f"{settings.releases_base_url}/{remote_version}/{filename}"

    tui.fade_type(f"{colorama.Fore.CYAN}Downloading {remote_version}...{colorama.Style.RESET_ALL}\n")
    try:
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        total = int(r.headers.get('content-length', 0))
        downloaded = 0
        with open(dest, 'wb') as f:
            for chunk in r.iter_content(chunk_size=262144):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = int(downloaded / total * 100)
                        print(f"\r  Progress: {pct}%", end='', flush=True)
        print()
    except Exception as e:
        tui.fade_type(f"{colorama.Fore.RED}Download failed: {e}{colorama.Style.RESET_ALL}\n")
        return

    tui.fade_type(f"{colorama.Fore.CYAN}Verifying integrity...{colorama.Style.RESET_ALL}\n")
    try:
        checksums = fetch_remote_checksums(remote_version)
        mismatches = verify_zip(dest, checksums)
        if mismatches:
            tui.fade_type(f"{colorama.Fore.RED}Integrity check failed: {mismatches[:3]}{colorama.Style.RESET_ALL}\n")
            return
    except Exception as e:
        tui.fade_type(f"{colorama.Fore.YELLOW}Checksum verification skipped: {e}{colorama.Style.RESET_ALL}\n")

    tui.fade_type(f"{colorama.Fore.CYAN}Backing up current version...{colorama.Style.RESET_ALL}\n")
    backup_current()
    tui.fade_type(f"{colorama.Fore.CYAN}Applying update...{colorama.Style.RESET_ALL}\n")
    if apply_update(dest):
        tui.fade_type(f"{colorama.Fore.GREEN}Update applied successfully. Restarting...{colorama.Style.RESET_ALL}\n")
        restart_app()
    else:
        tui.fade_type(f"{colorama.Fore.RED}Failed to apply update.{colorama.Style.RESET_ALL}\n")


def banner():
    tui.draw_line()
    print(
        tui.apply_gradient_coloring(
            tui.align('''
     888              d8888                    
     888             d8P888                    
     888            d8P 888                    
 .d88888  .d88b.   d8P  888  88888b.  888  888 
d88" 888 d8P  Y8b d88   888  888 "88b 888  888 
888  888 88888888 8888888888 888  888 888  888 
Y88b 888 Y8b.           888  888 d88P Y88b 888 
 "Y88888  "Y8888        888  88888P"   "Y88888 
                             888           888 
                             888      Y8b d88P 
                          888       "Y88P"'''
            )
        )
    )
    tui.draw_line()


def neofetch():
    print("\n")
    info = f"""                       {Fore.GREEN}de4py@{Fore.CYAN}{tui.get_username()}{Style.RESET_ALL}
    {Fore.CYAN}-----------------------------------------------{Style.RESET_ALL}
    {Fore.CYAN}OS: {platform.system()}{Style.RESET_ALL}
    {Fore.CYAN}Version: {platform.version()}{Style.RESET_ALL}
    {Fore.CYAN}Kernel: {platform.uname().release}{Style.RESET_ALL}
    {Fore.CYAN}Machine: {platform.machine()}{Style.RESET_ALL}
    {Fore.CYAN}Processor: {platform.processor()}{Style.RESET_ALL}
    {Fore.CYAN}Hostname: {socket.gethostname()}{Style.RESET_ALL}
    {Fore.CYAN}User: {tui.get_username()}{Style.RESET_ALL}
    {Fore.CYAN}Tool: de4py@{settings.version}{Style.RESET_ALL}"""
    print(tui.Add.Add(tui.get_logo(), info, 4))


def start():
    banner()
    tui.loading_animation("Checking for updates")
    tui.clear_line()
    cupdate()
    tui.loading_animation("Fetching info")
    fetch_info()
    tui.clear_line()
    fade_type(f"{colorama.Fore.CYAN}Starting de4py{colorama.Style.RESET_ALL}\n")
    time.sleep(1)
    tui.clear_console()
    banner()
    fade_type(
        f"{colorama.Fore.CYAN}Welcome to de4py type {colorama.Style.RESET_ALL}help {colorama.Fore.CYAN}to get the commands that you can use\n"
    )
    if settings.rpc:
        rpc.start_rpc()
    while 1:
        home_tab()

def pyshell_tab():
    tui.clear_console()
    banner()
    print(f"{Fore.CYAN}Enter the Target Process PID:{Style.RESET_ALL}")
    try:
        pid = int(input("PID >>> "))
    except ValueError:
        print(f"{Fore.RED}Invalid PID{Style.RESET_ALL}")
        time.sleep(1)
        return

    try:
        shell = Pyshell(pid)
    except Exception as e:
        print(f"{Fore.RED}Error connecting to process: {e}{Style.RESET_ALL}")
        time.sleep(2)
        return

    commands = {
        "inject": "Inject Pyshell DLL",
        "exec_file": "Execute Python File",
        "dump_strings": "Dump Strings",
        "get_funcs": "Get All Functions",
        "remove_exit": "Remove Exit Function",
        "crash": "Force Crash Process",
        "back": "Back to Home",
        "help": "Show commands"
    }

    while True:
        tui.shell_prompt(f"pyshell({pid})")
        choice = input()
        
        if choice == "inject":
            if shell.inject():
                print(f"{Fore.GREEN}Injection Successful{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}Injection Failed{Style.RESET_ALL}")
        elif choice == "exec_file":
            path = file_explorer()
            if path:
                if shell.execute_python_file(path):
                     print(f"{Fore.GREEN}Executed{Style.RESET_ALL}")
                else:
                     print(f"{Fore.RED}Failed{Style.RESET_ALL}")
        elif choice == "dump_strings":
            res = shell.dump_strings()
            print(f"Result: {res}")
        elif choice == "get_funcs":
            res = shell.get_all_functions()
            print(f"Result: {res}")
        elif choice == "remove_exit":
             if shell.remove_exit_function():
                 print(f"{Fore.GREEN}Removed exit function.{Style.RESET_ALL}")
        elif choice == "crash":
             shell.force_crash_process()
             print(f"{Fore.RED}Crashed.{Style.RESET_ALL}")
        elif choice == "back":
            break
        elif choice == "help":
            print(f"\n{Fore.CYAN}=== Available Commands ==={Style.RESET_ALL}")
            for k,v in commands.items():
                 print(f"{Fore.YELLOW}{k}{Style.RESET_ALL} - {v}")
        else:
             print(f"{Fore.RED}Unknown command{Style.RESET_ALL}")

if __name__ == "__main__":
    tui.clear_console()
    start()
