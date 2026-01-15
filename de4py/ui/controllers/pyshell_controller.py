import os
from de4py.utils.dlls import shell


HANDLE = None
HANDLE_analyzer = None
STOP_THREADS = False


def inject_shell(pid):
    return shell.inject_shell(pid)


def stealth_inject_shell(pid):
    return shell.stealth_inject_shell(pid)


def show_console(pid):
    return shell.show_console(pid)


def set_handle(handle):
    global HANDLE
    HANDLE = handle


def get_handle():
    global HANDLE
    return HANDLE


def set_analyzer_handle(handle):
    global HANDLE_analyzer
    HANDLE_analyzer = handle


def get_analyzer_handle():
    global HANDLE_analyzer
    return HANDLE_analyzer


def write_to_pipe(message):
    global HANDLE
    os.write(HANDLE, message.encode())
    response = read_from_pipe()
    return response == 'OK.'


def write_to_pipe_detailed(message):
    global HANDLE
    os.write(HANDLE, message.encode())
    return read_from_pipe()


def read_from_pipe():
    global HANDLE
    return os.read(HANDLE, 1024).decode()


def read_from_analyzer_pipe():
    global HANDLE_analyzer
    return os.read(HANDLE_analyzer, 4096).decode()


def open_analyzer_handle():
    global HANDLE_analyzer
    HANDLE_analyzer = os.open('\\\\.\\pipe\\de4py_analyzer', os.O_RDWR)
    return HANDLE_analyzer


def clear_handles():
    global HANDLE, HANDLE_analyzer, STOP_THREADS
    HANDLE = None
    HANDLE_analyzer = None
    STOP_THREADS = True


def set_stop_threads(val):
    global STOP_THREADS
    STOP_THREADS = val


def get_stop_threads():
    global STOP_THREADS
    return STOP_THREADS
