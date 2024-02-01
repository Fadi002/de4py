import colorama, msvcrt, platform, signal
from tkinter import Tk, filedialog
from deobfuscators.detector import detect_obfuscator
from analyzer import (
    detect_packer,
    unpack_file,
    get_file_hashs,
    sus_strings_lookup,
    all_strings_lookup,
)
from config import config
from util import *
import socket

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
    tui.linux_prompt()
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
        print(f"\n{Fore.CYAN}=== coming soon ==={Style.RESET_ALL}\n")
    elif choice == "analyzer":
        analyzer_tab()
    elif choice == "about":
        print(
            f"\n{Fore.CYAN}This tool created by 0xmrpepe, advdebug\nwebsite: https://de4py.000.pe\ngithub: https://github.com/Fadi002/de4py{Style.RESET_ALL}\n"
        )
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
        tui.linux_prompt("deobfuscator")
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
        tui.linux_prompt("analyzer")
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
            f"{colorama.Fore.YELLOW}your pc arch is not x64 bit please note this tool was tested on windows x64 bit{colorama.Style.RESET_ALL}\n"
        )
    change_log = requests.get(config.__CHANGELOG_URL__).json()
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
    if update.check_update():
        tui.fade_type(
            f"{colorama.Fore.CYAN}You are using the latest version{colorama.Style.RESET_ALL}\n"
        )
    else:
        tui.fade_type(
            f"{colorama.Fore.YELLOW}There's a new version. Are you sure you want to use this version?{colorama.Style.RESET_ALL}\n"
        )
        tui.fade_type("Answer [y/n]\n")
        if not input(">>> ").lower() == "y":
            tui.fade_type(
                f"{colorama.Fore.YELLOW}Download it from here : https://github.com/Fadi002/de4py{colorama.Style.RESET_ALL}\n"
            )
            tui.fade_type(
                f"{colorama.Fore.YELLOW}Press any key to exit...{colorama.Style.RESET_ALL}\n"
            )
            while True:
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    tui.fade_type(
                        f"{colorama.Fore.YELLOW}Exiting...{colorama.Style.RESET_ALL}"
                    )
                    sys.exit(0)


def banner():
    tui.draw_line()
    print(
        tui.water(
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
    info = f"""                       {Fore.GREEN}de4py@{Fore.CYAN}{os.getenv('Username')}{Style.RESET_ALL}
    {Fore.CYAN}-----------------------------------------------{Style.RESET_ALL}
    {Fore.CYAN}OS: {platform.system()}{Style.RESET_ALL}
    {Fore.CYAN}Version: {platform.version()}{Style.RESET_ALL}
    {Fore.CYAN}Kernel: {platform.uname().release}{Style.RESET_ALL}
    {Fore.CYAN}Machine: {platform.machine()}{Style.RESET_ALL}
    {Fore.CYAN}Processor: {platform.processor()}{Style.RESET_ALL}
    {Fore.CYAN}Hostname: {socket.gethostname()}{Style.RESET_ALL}
    {Fore.CYAN}User: {os.getenv('Username')}{Style.RESET_ALL}
    {Fore.CYAN}Tool: de4py@{config.__VERSION__}{Style.RESET_ALL}"""
    print(tui.Add.Add(tui.windows_logo, info, 4))


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
    if config.__RPC__:
        rpc.start_RPC()
    while 1:
        home_tab()

if __name__ == "__main__":
    tui.clear_console()
    start()