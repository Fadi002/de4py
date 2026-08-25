import logging

from PySide6.QtCore import QObject, Signal

class AppLogBridge(QObject):
    record = Signal(str, str)

class AppLogHandler(logging.Handler):
    def __init__(self, bridge: AppLogBridge):
        super().__init__()
        self._bridge = bridge
        self._attached = False
        self.setLevel(logging.DEBUG)

    def emit(self, record: logging.LogRecord):
        try:
            self._bridge.record.emit(record.levelname, self.format(record))
        except Exception:
            pass

    def attach(self):
        if self._attached:
            return
        logging.getLogger().addHandler(self)
        self._attached = True

    def detach(self):
        if not self._attached:
            return
        logging.getLogger().removeHandler(self)
        self._attached = False

bridge = AppLogBridge()
app_log_handler = AppLogHandler(bridge)
app_log_handler.setFormatter(logging.Formatter("%(message)s"))
