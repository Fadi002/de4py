from PySide6.QtCore import QObject, Signal

class DevEventBus(QObject):
    inspect_widget = Signal(object)
    log = Signal(str, str)
    api_call = Signal(str, str)

bus = DevEventBus()
