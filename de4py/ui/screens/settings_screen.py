from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QCheckBox, QComboBox, QHBoxLayout
)
from PySide6.QtCore import Qt

from de4py.config.config import settings
from de4py.lang import tr, translation_manager
from de4py.lang.keys import (
    SCREEN_TITLE_SETTINGS, SETTINGS_LANGUAGE, SETTINGS_RPC,
    SETTINGS_STEALTH, SETTINGS_PLUGINS, SETTINGS_RESTART_NOTE
)


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
        
        self.title_label = QLabel(tr(SCREEN_TITLE_SETTINGS))
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(self.title_label)
        
        # Language Selector
        lang_layout = QHBoxLayout()
        self.lang_label = QLabel(tr(SETTINGS_LANGUAGE))
        lang_layout.addWidget(self.lang_label)
        
        self.lang_combo = QComboBox()
        self.lang_combo.setObjectName("LanguageSelector")
        # Add available languages
        for code, name in translation_manager.get_available_languages().items():
            self.lang_combo.addItem(name, code)
        
        # Set current selection
        idx = self.lang_combo.findData(settings.language)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
            
        self.lang_combo.currentIndexChanged.connect(self._change_language)
        lang_layout.addWidget(self.lang_combo)
        frame_layout.addLayout(lang_layout)
        
        self.rpc_checkbox = QCheckBox(tr(SETTINGS_RPC))
        self.rpc_checkbox.stateChanged.connect(lambda s: self._update_config("rpc", s == Qt.CheckState.Checked.value))
        frame_layout.addWidget(self.rpc_checkbox)
        
        self.stealth_checkbox = QCheckBox(tr(SETTINGS_STEALTH))
        self.stealth_checkbox.stateChanged.connect(lambda s: self._update_config("stealth_title", s == Qt.CheckState.Checked.value))
        frame_layout.addWidget(self.stealth_checkbox)
        
        self.plugins_checkbox = QCheckBox(tr(SETTINGS_PLUGINS))
        self.plugins_checkbox.stateChanged.connect(lambda s: self._update_config("load_plugins", s == Qt.CheckState.Checked.value))
        frame_layout.addWidget(self.plugins_checkbox)
        
        frame_layout.addStretch()
        
        frame_layout.addStretch()
        
        self.note_label = QLabel(tr(SETTINGS_RESTART_NOTE))
        self.note_label.setWordWrap(True)
        frame_layout.addWidget(self.note_label)
        
        layout.addWidget(frame)

    def _change_language(self, index):
        lang_code = self.lang_combo.currentData()
        if lang_code:
            self._update_config("language", lang_code)
            translation_manager.set_language(lang_code)

    def retranslate_ui(self):
        """Update UI texts when language changes."""
        self.title_label.setText(tr(SCREEN_TITLE_SETTINGS))
        self.lang_label.setText(tr(SETTINGS_LANGUAGE))
        self.rpc_checkbox.setText(tr(SETTINGS_RPC))
        self.stealth_checkbox.setText(tr(SETTINGS_STEALTH))
        self.plugins_checkbox.setText(tr(SETTINGS_PLUGINS))
        self.note_label.setText(tr(SETTINGS_RESTART_NOTE))

    def _load_config(self):
        try:
            self.rpc_checkbox.setChecked(settings.rpc)
            self.stealth_checkbox.setChecked(settings.stealth_title)
            self.plugins_checkbox.setChecked(settings.load_plugins)
            
            # Update combo box if setting changed externally
            idx = self.lang_combo.findData(settings.language)
            if idx >= 0 and idx != self.lang_combo.currentIndex():
                self.lang_combo.blockSignals(True)
                self.lang_combo.setCurrentIndex(idx)
                self.lang_combo.blockSignals(False)
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
