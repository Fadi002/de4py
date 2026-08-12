# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import os


HANDLE = None
HANDLE_analyzer = None


def set_handle(handle):
    global HANDLE
    HANDLE = handle


def write_to_pipe(message):
    os.write(HANDLE, message.encode())
    response = read_from_pipe()
    return response == 'OK.'


def write_to_pipe_detailed(message):
    os.write(HANDLE, message.encode())
    return read_from_pipe()


def read_from_pipe():
    return os.read(HANDLE, 1024).decode()


def read_from_analyzer_pipe():
    return os.read(HANDLE_analyzer, 4096).decode()


def open_analyzer_handle():
    global HANDLE_analyzer
    HANDLE_analyzer = os.open('\\\\.\\pipe\\de4py_analyzer', os.O_RDWR)
    return HANDLE_analyzer


def clear_handles():
    global HANDLE, HANDLE_analyzer
    HANDLE = None
    HANDLE_analyzer = None
