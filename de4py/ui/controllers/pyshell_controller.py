# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import os

from de4py.utils.platform_utils import IS_WINDOWS

HANDLE = None
HANDLE_analyzer = None


def set_handle(handle):
    global HANDLE
    HANDLE = handle


def _win_handle(fd):
    if not IS_WINDOWS or fd is None:
        return None
    try:
        import msvcrt
        return msvcrt.get_osfhandle(fd)
    except (OSError, ValueError):
        return None


def pipe_bytes_available(fd):
    """Bytes waiting in the pipe, or None when the handle is unusable."""
    handle = _win_handle(fd)
    if handle is None:
        return None
    try:
        import ctypes
        avail = ctypes.c_ulong(0)
        ok = ctypes.windll.kernel32.PeekNamedPipe(
            handle, None, 0, None, ctypes.byref(avail), None)
        if not ok:
            return None
        return avail.value
    except Exception:
        return None


def write_to_pipe(message):
    if HANDLE is None:
        return False
    os.write(HANDLE, message.encode())
    return read_from_pipe() == 'OK.'


def write_to_pipe_detailed(message):
    if HANDLE is None:
        raise OSError("PyShell is not attached to a process")
    os.write(HANDLE, message.encode())
    return read_from_pipe()


def read_from_pipe():
    if HANDLE is None:
        return ""
    return os.read(HANDLE, 1024).decode(errors="replace")


def read_from_analyzer_pipe():
    if HANDLE_analyzer is None:
        return ""
    return os.read(HANDLE_analyzer, 4096).decode(errors="replace")


def read_analyzer_chunk():
    """Non-blocking analyzer read: '' when idle, None when the pipe is gone."""
    fd = HANDLE_analyzer
    if fd is None:
        return None
    avail = pipe_bytes_available(fd)
    if avail is None:
        return None
    if avail == 0:
        return ""
    try:
        return os.read(fd, min(avail, 4096)).decode(errors="replace")
    except OSError:
        return None


def open_analyzer_handle():
    global HANDLE_analyzer
    HANDLE_analyzer = os.open('\\\\.\\pipe\\de4py_analyzer', os.O_RDWR)
    return HANDLE_analyzer


def close_analyzer_handle():
    global HANDLE_analyzer
    if HANDLE_analyzer is not None:
        try:
            os.close(HANDLE_analyzer)
        except OSError:
            pass
    HANDLE_analyzer = None


def clear_handles():
    global HANDLE, HANDLE_analyzer
    HANDLE = None
    close_analyzer_handle()
