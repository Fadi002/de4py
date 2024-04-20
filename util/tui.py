import os, logging, time, shutil, sys, datetime, platform
from colorama import Fore, Style, AnsiToWin32, init
from traceback import extract_tb
from logging.handlers import TimedRotatingFileHandler
init()
__RAW_BANNER__ = '''
██████╗ ███████╗██╗  ██╗██████╗ ██╗   ██╗
██╔══██╗██╔════╝██║  ██║██╔══██╗╚██╗ ██╔╝
██║  ██║█████╗  ███████║██████╔╝ ╚████╔╝ 
██║  ██║██╔══╝  ╚════██║██╔═══╝   ╚██╔╝  
██████╔╝███████╗     ██║██║        ██║   
╚═════╝ ╚══════╝     ╚═╝╚═╝        ╚═╝'''

windows_logo = f"""{Fore.CYAN}                                ..,
{Fore.CYAN}                    ....,,:;+ccllll
{Fore.CYAN}      ...,,+:;  cllllllllllllllllll
{Fore.CYAN},cclllllllllll  lllllllllllllllllll
{Fore.CYAN}llllllllllllll  lllllllllllllllllll
{Fore.CYAN}llllllllllllll  lllllllllllllllllll
{Fore.CYAN}llllllllllllll  lllllllllllllllllll
{Fore.CYAN}llllllllllllll  lllllllllllllllllll
{Fore.CYAN}llllllllllllll  lllllllllllllllllll
{Fore.CYAN}                                   
{Fore.CYAN}llllllllllllll  lllllllllllllllllll
{Fore.CYAN}llllllllllllll  lllllllllllllllllll
{Fore.CYAN}llllllllllllll  lllllllllllllllllll
{Fore.CYAN}llllllllllllll  lllllllllllllllllll
{Fore.CYAN}llllllllllllll  lllllllllllllllllll
{Fore.CYAN}llllllllllllll  lllllllllllllllllll
{Fore.CYAN}`'ccllllllllll  lllllllllllllllllll
{Fore.CYAN}       `' \\*::  :ccllllllllllllllll
{Fore.CYAN}                       ````''*::cll
{Fore.CYAN}                                 ``{Style.RESET_ALL}"""

def water(text):
    os.system(""); faded = ""
    green = 10
    for line in text.splitlines():
        faded += (f"\033[38;2;0;{green};255m{line}\033[0m\n")
        if not green == 255:
            green += 15
            if green > 255:
                green = 255
    return faded

__BANNER__ = water(__RAW_BANNER__)

def clear_console():os.system('cls' if os.name == 'nt' else 'clear')

def setup_logging():
    logs_dir = 'logs'
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    log_level = logging.INFO
    logging_format = "%(levelname)s - %(message)s"
    file_handler = TimedRotatingFileHandler(filename=os.path.join(logs_dir, f'de4py-logs-{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.log'))
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(file_formatter)
    file_logger = logging.getLogger('file_logger')
    file_logger.setLevel(logging.INFO)
    file_logger.addHandler(file_handler)
    file_logger.info(f"System Architecture: {platform.architecture()[0]}, OS: {platform.platform()}, Python Version: {platform.python_version()}")
    logging.basicConfig(
        level=log_level,
        format=logging_format,
        handlers=[ColorizingStreamHandler(), file_handler])

class ColorizingStreamHandler(logging.StreamHandler):
    def emit(self, record):
        message = self.format(record)
        if record.levelno == logging.INFO:
            colored_message = f"{Fore.LIGHTBLUE_EX}{message}{Style.RESET_ALL}"
        elif record.levelno == logging.WARNING:
            colored_message = f"{Fore.YELLOW}{message}{Style.RESET_ALL}"
        elif record.levelno == logging.ERROR or record.levelno == logging.CRITICAL:
            colored_message = f"{Fore.RED}{message}{Style.RESET_ALL}"
        else:
            colored_message = message
        print(colored_message)

def fade_type(text):
     for c in text:
        print(c,end='',flush=True)
        time.sleep(0.009)

def align(text: str) -> str: 
    """
    credits : https://github.com/SirDank/dankware/blob/main/dankware/__init__.py
    """
    width = shutil.get_terminal_size().columns
    aligned = text
    for _ in tuple(vars(Fore).values()) + tuple(vars(Style).values()):
        aligned = aligned.replace(_,'')
    
    text = text.splitlines()
    aligned = aligned.splitlines()
    for _ in range(len(aligned)):
        aligned[_] = aligned[_].center(width).replace(aligned[_],text[_])
    return str('\n'.join(aligned) + Style.RESET_ALL)

def draw_line():
    terminal_width = shutil.get_terminal_size().columns
    line = Fore.CYAN + "-" * terminal_width + Style.RESET_ALL
    print(line)


def loading_animation(text, loops=2):
    frames = ['\\', '|', '/', '-']
    for _ in range(loops):
        for frame in frames:
            line = f"{Fore.CYAN}{text} {Style.RESET_ALL}[{Fore.CYAN}{frame}{Style.RESET_ALL}]" + Style.RESET_ALL
            print(line, end='\r')
            time.sleep(0.2)

def clear_line():
    sys.stdout.write("\033[K")
    sys.stdout.flush()

def linux_prompt(tab="~"):
    sys.stdout.write(f"{Fore.GREEN}de4py@{Fore.CYAN}{os.getenv('Username')}{Style.RESET_ALL} {Fore.GREEN}{tab}/ {Style.RESET_ALL}$ ")
    sys.stdout.flush()



def custom_error(exc_type, exc_value, exc_traceback):
    print(f"{Fore.RED}=== Start Traceback ==={Style.RESET_ALL}")
    print(f"{Fore.RED}Error Type:{Style.RESET_ALL} {exc_type.__name__}")
    print(f"{Fore.RED}Error Message:{Style.RESET_ALL} {exc_value}")
    print(f"{Fore.RED}Traceback:{Style.RESET_ALL}")
    traceback_lines = []
    for filename, line_num, func_name, line_code in extract_tb(exc_traceback):
        traceback_lines.append(f"  File '{filename}', line {line_num}, in {func_name}\n    {line_code}")
    print("\n".join(traceback_lines))
    print(f"{Fore.RED}=== End of Traceback ==={Style.RESET_ALL}")



class Add:
    """
    CREDITS: https://github.com/billythegoat356/pystyle/blob/main/pystyle/__init__.py
    1 function:
        Add()           |           allow you to add a text to another, and even center it
    """
    def Add(banner1, banner2, spaces=0, center=False):
        if center:
            split1 = len(banner1.splitlines())
            split2 = len(banner2.splitlines())
            if split1 > split2:
                spaces = (split1 - split2) // 2
            elif split2 > split1:
                spaces = (split2 - split1) // 2
            else:
                spaces = 0
        if spaces > max(len(banner1.splitlines()), len(banner2.splitlines())):
            # raise Banner.MaximumSpaces(spaces)
            spaces = max(len(banner1.splitlines()), len(banner2.splitlines()))
        ban1 = banner1.splitlines()
        ban2 = banner2.splitlines()
        ban1count = len(ban1)
        ban2count = len(ban2)
        size = Add._length(ban1)
        ban1 = Add._edit(ban1, size)
        ban1line = 0
        ban2line = 0
        text = ''
        for _ in range(spaces):
            if ban1count >= ban2count:
                ban1data = ban1[ban1line]
                ban2data = ''
                ban1line += 1
            else:
                ban1data = " " * size
                ban2data = ban2[ban2line]
                ban2line += 1
            text = text + ban1data + ban2data + '\n'
        while ban1line < ban1count or ban2line < ban2count:
            ban1data = ban1[ban1line] if ban1line < ban1count else " " * size
            ban2data = ban2[ban2line] if ban2line < ban2count else ""
            text = text + ban1data + ban2data + '\n'
            ban1line += 1
            ban2line += 1
        return text
    """ ! developper area ! """
    class MaximumSpaces(Exception):
        def __init__(self, spaces: str):
            super().__init__(f"Too much spaces [{spaces}].")
    def _length(ban1):
        bigestline = 0

        for line in ban1:
            if len(line) > bigestline:
                bigestline = len(line)
        return bigestline

    def _edit(ban1, size):
        return [line + (size - len(line)) * " " for line in ban1]

sys.excepthook = custom_error