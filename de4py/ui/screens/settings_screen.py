from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QCheckBox
)
from PySide6.QtCore import Qt

from de4py.config.config import settings


class SettingsScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 20)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        frame = QFrame()
        frame.setObjectName("StyledFrame")
        frame.setFixedSize(400, 280)
        
        frame_layout = QVBoxLayout(frame)
        frame_layout.setSpacing(15)
        
        title = QLabel("SETTINGS")
        title.setObjectName("TitleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(title)
        
        self.rpc_checkbox = QCheckBox("RPC")
        self.rpc_checkbox.stateChanged.connect(lambda s: self._update_config("rpc", s == Qt.CheckState.Checked.value))
        frame_layout.addWidget(self.rpc_checkbox)
        
        self.stealth_checkbox = QCheckBox("Stealth titles")
        self.stealth_checkbox.stateChanged.connect(lambda s: self._update_config("stealth_title", s == Qt.CheckState.Checked.value))
        frame_layout.addWidget(self.stealth_checkbox)
        
        self.plugins_checkbox = QCheckBox("Load plugins")
        self.plugins_checkbox.stateChanged.connect(lambda s: self._update_config("load_plugins", s == Qt.CheckState.Checked.value))
        frame_layout.addWidget(self.plugins_checkbox)
        
        frame_layout.addStretch()
        
        note = QLabel("Note: restart the tool to apply the new settings correctly")
        note.setWordWrap(True)
        frame_layout.addWidget(note)
        
        layout.addWidget(frame)

    def _load_config(self):
        try:
            self.rpc_checkbox.setChecked(settings.rpc)
            self.stealth_checkbox.setChecked(settings.stealth_title)
            self.plugins_checkbox.setChecked(settings.load_plugins)
        except Exception:
            pass

    def _update_config(self, key: str, value: bool):
        try:
            if hasattr(settings, key):
                setattr(settings, key, value)
                settings.save()
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._load_config()
