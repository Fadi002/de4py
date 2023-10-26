import os, logging, time
from colorama import Fore, Style
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
__BANNER__ = water('''
██████╗ ███████╗██╗  ██╗██████╗ ██╗   ██╗
██╔══██╗██╔════╝██║  ██║██╔══██╗╚██╗ ██╔╝
██║  ██║█████╗  ███████║██████╔╝ ╚████╔╝ 
██║  ██║██╔══╝  ╚════██║██╔═══╝   ╚██╔╝  
██████╔╝███████╗     ██║██║        ██║   
╚═════╝ ╚══════╝     ╚═╝╚═╝        ╚═╝''')
def clear_console():os.system('cls' if os.name == 'nt' else 'clear')
def setup_logging():
    log_level = logging.INFO
    logging_format = "%(levelname)s - %(message)s"
    logging.basicConfig(
        level=log_level,
        format=logging_format,
        handlers=[ColorizingStreamHandler()])

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