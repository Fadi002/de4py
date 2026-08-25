# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import colorama, platform, signal, os
from de4py.engines.legacy.detector import detect_obfuscator
from de4py.engines.analyzers import (
    detect_packer,
    unpack_file,
    get_file_hashs,
    sus_strings_lookup,
    all_strings_lookup,
)
from de4py.config.config import settings
from de4py.tui.commands import Command, CommandRegistry, run_repl
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
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
sys.excepthook = custom_error
change_log = None
platform_info = None
file_path = None


def _confirm_pyarmor_dynamic():
    print(f"\n{Fore.YELLOW}PyArmor file detected.{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[S]tatic{Style.RESET_ALL} - only reads and decrypts the file, never runs it.")
    print(f"{Fore.CYAN}[D]ynamic{Style.RESET_ALL} - actually imports and runs the file to capture "
          f"everything static recovery misses. Any payload it carries executes on this machine.")
    choice = input(f"{Fore.CYAN}Recovery mode [S/d]: {Style.RESET_ALL}").strip().lower()
    return "hooking" if choice == "d" else "static"


def _add_path_argument(parser):
    parser.add_argument("path", nargs="?", default=None, help="File path. Omit to open the file picker.")


def _make_set_file_handler(state):
    def handler(args):
        state["file_path"] = args.path or file_explorer()
        if state["file_path"]:
            print(f"{Fore.CYAN}Selected file path: {state['file_path']}{Style.RESET_ALL}\n")
        else:
            print(f"{Fore.YELLOW}No file selected.{Style.RESET_ALL}\n")
    return handler


def _help_command(registry):
    def handler(args):
        print(f"\n{Fore.CYAN}=== Available Commands ==={Style.RESET_ALL}")
        for name, help_text in registry.help_lines():
            print(f"{Fore.YELLOW}{name}{Style.RESET_ALL} - {help_text}")
        print(f"{Fore.CYAN}=========================={Style.RESET_ALL}\n")
    return Command("help", "Show available commands.", handler)


def _clear_command():
    def handler(args):
        tui.clear_console()
        banner()
    return Command("clear", "Clear the console.", handler)


def _exit_command():
    def handler(args):
        tui.clear_console()
        banner()
        print(f"{colorama.Fore.CYAN}Exiting....{colorama.Style.RESET_ALL}")
        sys.exit(0)
    return Command("exit", "Exits the program.", handler)


def _back_command():
    def handler(args):
        tui.clear_console()
        banner()
        return False
    return Command("back", "Back to the home page.", handler)


def _build_home_registry():
    registry = CommandRegistry()

    def _deobfuscator(args):
        deobfuscator_tab()

    def _pyshell(args):
        if supports("pyshell"):
            pyshell_tab()
        else:
            print(f"{Fore.RED}PyShell is only available on Windows.{Style.RESET_ALL}")

    def _analyzer(args):
        analyzer_tab()

    def _about(args):
        from de4py._meta import print_about
        print_about()

    def _neofetch_cmd(args):
        neofetch()

    def _changelog(args):
        changelog_display()

    registry.register(Command("deobfuscator", "Executes the deobfuscator tool.", _deobfuscator))
    registry.register(Command("pyshell", "Opens the Python shell.", _pyshell))
    registry.register(Command("analyzer", "Runs the code analyzer tool.", _analyzer))
    registry.register(Command("about", "Displays information about the program.", _about))
    registry.register(Command("changelog", "Displays the change log with details of each version and the corresponding updates.", _changelog))
    registry.register(Command("neofetch", "Displays your PC info + the tool info", _neofetch_cmd))
    registry.register(_help_command(registry))
    registry.register(_clear_command())
    registry.register(_exit_command())
    return registry


def home_tab():
    registry = _build_home_registry()
    run_repl(registry, lambda: tui.shell_prompt())


def _build_deobfuscator_registry(state):
    registry = CommandRegistry()

    def _start(args):
        if not state["file_path"]:
            print(f"{Fore.YELLOW}No file selected.{Style.RESET_ALL}\n")
            return
        engine_options = None
        if (state["mode"] != "normal" or state["explain"] or state["stats"]
                or state["max_iterations"] != 12):
            engine_options = {
                "enabled": True, "mode": state["mode"],
                "explain": state["explain"], "stats": state["stats"],
                "max_iterations": state["max_iterations"],
            }
        print(f"{Fore.CYAN}Starting the Deobfuscation process...{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Deobfuscation result:{Style.RESET_ALL}\n")
        print(detect_obfuscator(state["file_path"],
                                confirm_dynamic=_confirm_pyarmor_dynamic,
                                engine_options=engine_options))
        print("\n")

    def _mode(args):
        choice = (args[0] if args else "").lower()
        if choice in ("safe", "normal", "aggressive"):
            state["mode"] = choice
            print(f"{Fore.CYAN}Onyx mode set to {choice}.{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}Usage: mode safe|normal|aggressive{Style.RESET_ALL}")

    def _explain(args):
        state["explain"] = ((args[0].lower() if args else "on") != "off")
        print(f"{Fore.CYAN}Explain output: {state['explain']}{Style.RESET_ALL}")

    def _engine_stats(args):
        state["stats"] = ((args[0].lower() if args else "on") != "off")
        print(f"{Fore.CYAN}Stats output: {state['stats']}{Style.RESET_ALL}")

    def _max_iterations(args):
        try:
            state["max_iterations"] = max(1, min(64, int(args[0])))
            print(f"{Fore.CYAN}Max iterations: {state['max_iterations']}{Style.RESET_ALL}")
        except (IndexError, ValueError):
            print(f"{Fore.YELLOW}Usage: max_iterations <1-64>{Style.RESET_ALL}")

    registry.register(Command("set_file", "Select a file to deobfuscate. Provide a path to skip the picker.",
                               _make_set_file_handler(state), _add_path_argument))
    registry.register(Command("start", "Executes the deobfuscator.", _start))
    registry.register(Command("mode", "Onyx rule mode: safe|normal|aggressive.", _mode))
    registry.register(Command("explain", "Show per-transformation events after runs: on|off.", _explain))
    registry.register(Command("stats", "Show transformation counters after runs: on|off.", _engine_stats))
    registry.register(Command("max_iterations", "Governor iteration cap for Onyx: 1-64.", _max_iterations))
    registry.register(_help_command(registry))
    registry.register(_clear_command())
    registry.register(_back_command())
    registry.register(_exit_command())
    return registry


def deobfuscator_tab():
    state = {"file_path": None, "mode": "normal", "explain": False,
             "stats": False, "max_iterations": 12}
    tui.clear_console()
    banner()
    registry = _build_deobfuscator_registry(state)
    run_repl(registry, lambda: tui.shell_prompt("deobfuscator"))


def _build_analyzer_registry(state):
    registry = CommandRegistry()

    def _needs_file(fn):
        def handler(args):
            if not state["file_path"]:
                print(f"{Fore.YELLOW}No file selected.{Style.RESET_ALL}\n")
                return
            fn(state["file_path"])
        return handler

    def _packer(path):
        print(f"{Fore.CYAN}Starting the detecting process...{Style.RESET_ALL}")
        print(f"{Fore.CYAN}packer detector result:{Style.RESET_ALL}\n")
        print(detect_packer(path))
        print("\n")

    def _unpacker(path):
        print(f"{Fore.CYAN}Starting the unpacking process...{Style.RESET_ALL}")
        print(f"{Fore.CYAN}unpacker result:{Style.RESET_ALL}\n")
        print(unpack_file(path))
        print("\n")

    def _sus_strings(path):
        print(f"{Fore.CYAN}Starting the sus strings lookup process...{Style.RESET_ALL}")
        print(f"{Fore.CYAN}search result:{Style.RESET_ALL}\n")
        print(sus_strings_lookup(path))
        print("\n")

    def _all_strings(path):
        print(f"{Fore.CYAN}Starting the all strings lookup process...{Style.RESET_ALL}")
        print(f"{Fore.CYAN}search result:{Style.RESET_ALL}\n")
        print(all_strings_lookup(path))
        print("\n")

    def _hashes(path):
        print(f"{Fore.CYAN}Starting to get the file hashs process...{Style.RESET_ALL}")
        print(f"{Fore.CYAN}hashs result:{Style.RESET_ALL}\n")
        print(get_file_hashs(path))

    registry.register(Command("set_file", "Select a file to analyze. Provide a path to skip the picker.",
                               _make_set_file_handler(state), _add_path_argument))
    registry.register(Command("exe_packer_detector", "Detect the exe packer (ex. py2exe).", _needs_file(_packer)))
    registry.register(Command("exe_unpacker", "Unpack the exe if its supported", _needs_file(_unpacker)))
    registry.register(Command("sus_strings_lookup", "Search for the sus strings like ips links.", _needs_file(_sus_strings)))
    registry.register(Command("all_strings", "Search for all readable strings in the file.", _needs_file(_all_strings)))
    registry.register(Command("get_file_hashs", "Gives you the MD5, SHA1 and SHA256 of the file.", _needs_file(_hashes)))
    registry.register(_help_command(registry))
    registry.register(_clear_command())
    registry.register(_back_command())
    registry.register(_exit_command())
    return registry


def analyzer_tab():
    state = {"file_path": None}
    tui.clear_console()
    banner()
    registry = _build_analyzer_registry(state)
    run_repl(registry, lambda: tui.shell_prompt("analyzer"))


def file_explorer() -> str:
    from tkinter import Tk, filedialog

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
    home_tab()

def _build_pyshell_registry(shell, pid):
    registry = CommandRegistry()

    def _inject(args):
        if shell.inject():
            print(f"{Fore.GREEN}Injection Successful{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}Injection Failed{Style.RESET_ALL}")

    def _exec_file(args):
        path = args.path or file_explorer()
        if not path:
            return
        if shell.execute_python_file(path):
            print(f"{Fore.GREEN}Executed{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}Failed{Style.RESET_ALL}")

    def _dump_strings(args):
        print(f"Result: {shell.dump_strings()}")

    def _get_funcs(args):
        print(f"Result: {shell.get_all_functions()}")

    def _remove_exit(args):
        if shell.remove_exit_function():
            print(f"{Fore.GREEN}Removed exit function.{Style.RESET_ALL}")

    def _crash(args):
        shell.force_crash_process()
        print(f"{Fore.RED}Crashed.{Style.RESET_ALL}")

    registry.register(Command("inject", "Inject Pyshell DLL", _inject))
    registry.register(Command("exec_file", "Execute Python File. Provide a path to skip the picker.",
                               _exec_file, _add_path_argument))
    registry.register(Command("dump_strings", "Dump Strings", _dump_strings))
    registry.register(Command("get_funcs", "Get All Functions", _get_funcs))
    registry.register(Command("remove_exit", "Remove Exit Function", _remove_exit))
    registry.register(Command("crash", "Force Crash Process", _crash))
    registry.register(_help_command(registry))
    registry.register(_back_command())
    return registry


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

    registry = _build_pyshell_registry(shell, pid)
    run_repl(registry, lambda: tui.shell_prompt(f"pyshell({pid})"))


if __name__ == "__main__":
    tui.clear_console()
    start()
