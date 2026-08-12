# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Per-OS ASCII logos rendered from fastfetch's standalone logo art.

The art lives as plain text in ``de4py/assets/ascii/<name>.txt`` (maintained
upstream at https://github.com/fastfetch-cli/fastfetch, path
``src/logo/ascii/<letter>/<name>.txt``). Each file embeds ``$1..$4`` color-slot
markers that fastfetch maps to a per-logo palette at render time; this module
replicates that behaviour so every supported OS shows its own mascot with the
same fidelity as fastfetch's neofetch/logo output.
"""
import os
import re
import sys

_LOGO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "ascii")

_SLOT_RE = re.compile(r"\$(\d)")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

# Per-OS palettes for color slots 1..4 (xterm 256-color indices).
_PALETTES = {
    "windows": ("39", "174", "117"),
    "macos": ("81", "195", "159"),
    "ubuntu": ("215", "209", "223"),
    "debian": ("78", "254", "209"),
    "arch": ("45", "117", "123"),
    "fedora": ("63", "33", "111"),
    "manjaro": ("41", "28", "70"),
    "freebsd": ("196", "9", "209"),
    "openbsd": ("214", "172", "58"),
    "netbsd": ("220", "160", "210"),
    "dragonfly": ("202", "214", "208"),
    "linux": ("111", "40", "34"),
}

_DEFAULT_SLOTS = ("45", "117", "123", "189")
_FALLBACK_SLOT = "\x1b[38;5;45m"

_LINUX_KEYS = {"arch", "debian", "ubuntu", "fedora", "manjaro"}


def _palette_for(key):
    return _PALETTES.get(key, _DEFAULT_SLOTS)


def _load(key):
    """Return the raw logo text for a key, or None if unavailable."""
    path = os.path.join(_LOGO_DIR, key + ".txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except (OSError, ValueError):
        return None


def render(key):
    """Render a logo key to an ANSI-coloured string (safe no-op fallbacks)."""
    text = _load(key) or _load("linux") or ""
    slots = _palette_for(key)

    def _color(match):
        index = int(match.group(1)) - 1
        if 0 <= index < len(slots):
            return f"\x1b[38;5;{slots[index]}m"
        return _FALLBACK_SLOT

    lines = []
    for raw in text.splitlines():
        line = _SLOT_RE.sub(_color, raw).rstrip()
        if line.strip():
            line += "\x1b[0m"
        lines.append(line)
    return "\n".join(lines) or ""


def _linux_distro_key():
    distro_id = None
    distro_like = ""
    try:
        with open("/etc/os-release", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                value = value.strip("\"'")
                if key == "ID":
                    distro_id = value.lower()
                elif key == "ID_LIKE":
                    distro_like = value.lower()
    except (OSError, ValueError):
        return "linux"
    candidates = [distro_id] + (distro_like.split() if distro_like else [])
    for candidate in candidates:
        if candidate in _LINUX_KEYS:
            return candidate
    return "linux"


def detect_logo_key():
    """Pick the ASCII logo key for the current OS/distro."""
    system = sys.platform
    if system == "win32":
        return "windows"
    if system == "darwin":
        return "macos"
    if system in ("freebsd", "openbsd", "netbsd", "dragonfly"):
        return system
    if system == "linux":
        return _linux_distro_key()
    return "linux"


def get_logo():
    """Return the current OS/distro logo as an ANSI-coloured string."""
    return render(detect_logo_key())


def strip_ansi(text):
    """Strip ANSI escape sequences for visible-width computation."""
    return _ANSI_RE.sub("", text)