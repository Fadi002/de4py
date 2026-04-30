# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Console display utilities for de4py CLI.

Handles: banner rendering, terminal formatting, animated text output,
and the neofetch-style side-by-side layout helper.
"""

import os
import sys
import time
import shutil
from colorama import Fore, Style, init

init()


# ── Banner ───────────────────────────────────────────────────────────────────

__RAW_BANNER__ = '''
██████╗ ███████╗██╗  ██╗██████╗ ██╗   ██╗
██╔══██╗██╔════╝██║  ██║██╔══██╗╚██╗ ██╔╝
██║  ██║█████╗  ███████║██████╔╝ ╚████╔╝ 
██║  ██║██╔══╝  ╚════██║██╔═══╝   ╚██╔╝  
██████╔╝███████╗     ██║██║        ██║   
╚═════╝ ╚══════╝     ╚═╝╚═╝        ╚═╝'''


def apply_gradient_coloring(text):
    """Apply a blue-to-green vertical gradient to multi-line text."""
    os.system("")
    faded = ""
    green = 10
    for line in text.splitlines():
        faded += f"\033[38;2;0;{green};255m{line}\033[0m\n"
        if green != 255:
            green += 15
            if green > 255:
                green = 255
    return faded

__BANNER__ = apply_gradient_coloring(__RAW_BANNER__)


# ── Console Helpers ──────────────────────────────────────────────────────────

def clear_console():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def fade_type(text):
    """Print text with a typewriter animation effect."""
    for c in text:
        print(c, end='', flush=True)
        time.sleep(0.009)


def draw_line():
    """Draw a full-width colored separator line."""
    terminal_width = shutil.get_terminal_size().columns
    line = Fore.CYAN + "-" * terminal_width + Style.RESET_ALL
    print(line)


def align(text: str) -> str:
    """
    Center-align multi-line text in the terminal, preserving ANSI color codes.
    credits: https://github.com/SirDank/dankware/blob/main/dankware/__init__.py
    """
    width = shutil.get_terminal_size().columns
    aligned = text
    for _ in tuple(vars(Fore).values()) + tuple(vars(Style).values()):
        aligned = aligned.replace(_, '')

    text = text.splitlines()
    aligned = aligned.splitlines()
    for _ in range(len(aligned)):
        aligned[_] = aligned[_].center(width).replace(aligned[_], text[_])
    return str('\n'.join(aligned) + Style.RESET_ALL)


def loading_animation(text, loops=2):
    """Show a spinning loading indicator in the terminal."""
    frames = ['\\', '|', '/', '-']
    for _ in range(loops):
        for frame in frames:
            line = f"{Fore.CYAN}{text} {Style.RESET_ALL}[{Fore.CYAN}{frame}{Style.RESET_ALL}]" + Style.RESET_ALL
            print(line, end='\r')
            time.sleep(0.2)


def clear_line():
    """Clear the current terminal line."""
    sys.stdout.write("\033[K")
    sys.stdout.flush()


def linux_prompt(tab="~"):
    """Display a styled prompt line."""
    sys.stdout.write(
        f"{Fore.GREEN}de4py@{Fore.CYAN}{os.getenv('Username')}{Style.RESET_ALL} "
        f"{Fore.GREEN}{tab}/ {Style.RESET_ALL}$ "
    )
    sys.stdout.flush()


# ── Neofetch-style Layout ────────────────────────────────────────────────────

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


class Add:
    """
    Side-by-side text layout helper for neofetch-style output.
    CREDITS: https://github.com/billythegoat356/pystyle/blob/main/pystyle/__init__.py
    """

    @staticmethod
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
            spaces = max(len(banner1.splitlines()), len(banner2.splitlines()))

        ban1 = banner1.splitlines()
        ban2 = banner2.splitlines()
        ban1count = len(ban1)
        ban2count = len(ban2)
        size = Add._longest_line_length(ban1)
        ban1 = Add._pad_lines(ban1, size)
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

    class MaximumSpaces(Exception):
        def __init__(self, spaces: str):
            super().__init__(f"Too much spaces [{spaces}].")

    @staticmethod
    def _longest_line_length(lines):
        longest = 0
        for line in lines:
            if len(line) > longest:
                longest = len(line)
        return longest

    @staticmethod
    def _pad_lines(lines, size):
        return [line + (size - len(line)) * " " for line in lines]


# ── Legacy Compatibility ─────────────────────────────────────────────────────
# Exception hook and logging are in their dedicated modules (errors.py / logging.py).
# Re-exported here so `from de4py.utils import tui; tui.custom_error` still works.
# NOTE: the exception hook is no longer installed as a side effect of importing this
# module — call errors.install() explicitly in main.py instead.
from de4py.utils.errors import custom_error, install as install_excepthook  # noqa: F401, E402
from de4py.utils.logging import setup_logging, ColorizingStreamHandler  # noqa: F401, E402