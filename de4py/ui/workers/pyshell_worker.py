"""
De4py PyShell Worker - Handles injection and pipe operations in background
One task only, emits result signal, no direct UI updates
"""
from PySide6.QtCore import QThread, Signal

from de4py.ui.controllers import pyshell_controller


class InjectionWorker(QThread):
    finished = Signal(object, bool)
    error = Signal(str)

    def __init__(self, pid: str, stealth: bool = False, parent=None):
        super().__init__(parent)
        self._pid = pid
        self._stealth = stealth

    def run(self):
        try:
            if self._stealth:
                result = pyshell_controller.stealth_inject_shell(self._pid)
            else:
                result = pyshell_controller.inject_shell(self._pid)
            
            if result and result[1]:
                pyshell_controller.set_handle(result[0])
                self.finished.emit(result[0], True)
            else:
                self.finished.emit(None, False)
        except Exception as e:
            self.error.emit(str(e))


class PipeCommandWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, command: str, parent=None):
        super().__init__(parent)
        self._command = command

    def run(self):
        try:
            result = pyshell_controller.write_to_pipe_detailed(self._command)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ShowConsoleWorker(QThread):
    finished = Signal(bool)
    error = Signal(str)

    def __init__(self, pid: str, parent=None):
        super().__init__(parent)
        self._pid = pid

    def run(self):
        try:
            result = pyshell_controller.show_console(self._pid)
            self.finished.emit(result or False)
        except Exception as e:
            self.error.emit(str(e))


class ProcessMonitorWorker(QThread):
    process_died = Signal()

    def __init__(self, pid: int, parent=None):
        super().__init__(parent)
        self._pid = pid
        self._running = True

    def run(self):
        import psutil
        while self._running:
            try:
                process = psutil.Process(self._pid)
                if not process.is_running():
                    self.process_died.emit()
                    break
                self.msleep(500)
            except psutil.NoSuchProcess:
                self.process_died.emit()
                break
            except Exception:
                break

    def stop(self):
        self._running = False
