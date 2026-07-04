# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QCheckBox, QComboBox, QPushButton, QHBoxLayout
)
from PySide6.QtCore import Qt

from de4py.config.config import settings
from de4py.lang import tr, translation_manager
from de4py.lang.keys import (
    SCREEN_TITLE_SETTINGS, SETTINGS_LANGUAGE, SETTINGS_RPC,
    SETTINGS_STEALTH, SETTINGS_PLUGINS, SETTINGS_RESTART_NOTE,
    SETTINGS_TRANSPARENT_UI, SETTINGS_TELEMETRY,
    SETTINGS_AUTO_UPDATE_CHECK, SETTINGS_AUTO_INSTALL, SETTINGS_CHECK_NOW,
    SETTINGS_UPDATE_CHECKING, SETTINGS_UPDATE_UPTODATE, SETTINGS_UPDATE_AVAILABLE,
    SETTINGS_UPDATE_DOWNLOAD_BTN, SETTINGS_UPDATE_OPENING_DIALOG
)

CHECKED = Qt.CheckState.Checked.value


class SettingsScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading_config = False
        self._updater_connected = False
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 20)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel(tr(SCREEN_TITLE_SETTINGS))
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        frame = QFrame()
        frame.setObjectName("StyledFrame")
        frame.setMaximumWidth(500)

        frame_layout = QVBoxLayout(frame)
        frame_layout.setSpacing(12)

        lang_row = QHBoxLayout()
        self.lang_label = QLabel(tr(SETTINGS_LANGUAGE))
        self.lang_label.setFixedWidth(120)
        lang_row.addWidget(self.lang_label)
        self.lang_combo = QComboBox()
        self.lang_combo.setObjectName("LanguageSelector")
        for code, name in translation_manager.get_available_languages().items():
            self.lang_combo.addItem(name, code)
        idx = self.lang_combo.findData(settings.language)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        self.lang_combo.currentIndexChanged.connect(self._change_language)
        lang_row.addWidget(self.lang_combo)
        frame_layout.addLayout(lang_row)

        self.rpc_checkbox = QCheckBox(tr(SETTINGS_RPC))
        self.rpc_checkbox.stateChanged.connect(lambda s: self._update_config("rpc", s == CHECKED))
        frame_layout.addWidget(self.rpc_checkbox)

        self.stealth_checkbox = QCheckBox(tr(SETTINGS_STEALTH))
        self.stealth_checkbox.stateChanged.connect(lambda s: self._update_config("stealth_title", s == CHECKED))
        frame_layout.addWidget(self.stealth_checkbox)

        self.plugins_checkbox = QCheckBox(tr(SETTINGS_PLUGINS))
        self.plugins_checkbox.stateChanged.connect(lambda s: self._update_config("load_plugins", s == CHECKED))
        frame_layout.addWidget(self.plugins_checkbox)

        self.transparent_checkbox = QCheckBox(tr(SETTINGS_TRANSPARENT_UI))
        self.transparent_checkbox.stateChanged.connect(self._on_transparent_ui_changed)
        frame_layout.addWidget(self.transparent_checkbox)

        self.telemetry_checkbox = QCheckBox(tr(SETTINGS_TELEMETRY))
        self.telemetry_checkbox.stateChanged.connect(lambda s: self._update_config("telemetry", s == CHECKED))
        frame_layout.addWidget(self.telemetry_checkbox)

        sep = QFrame()
        sep.setObjectName("SettingsSeparator")
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(2)
        frame_layout.addWidget(sep)

        self.auto_update_check_checkbox = QCheckBox(tr(SETTINGS_AUTO_UPDATE_CHECK))
        self.auto_update_check_checkbox.stateChanged.connect(lambda s: self._update_config("auto_update_check", s == CHECKED))
        frame_layout.addWidget(self.auto_update_check_checkbox)

        self.auto_install_checkbox = QCheckBox(tr(SETTINGS_AUTO_INSTALL))
        self.auto_install_checkbox.stateChanged.connect(lambda s: self._update_config("auto_update_install", s == CHECKED))
        frame_layout.addWidget(self.auto_install_checkbox)

        self.check_update_btn = QPushButton(tr(SETTINGS_CHECK_NOW))
        self.check_update_btn.clicked.connect(self._on_check_updates)
        frame_layout.addWidget(self.check_update_btn)

        self.update_status_label = QLabel("")
        self.update_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.update_status_label.setWordWrap(True)
        self.update_status_label.hide()
        frame_layout.addWidget(self.update_status_label)

        self.download_update_btn = QPushButton(tr(SETTINGS_UPDATE_DOWNLOAD_BTN))
        self.download_update_btn.clicked.connect(self._on_download_update)
        self.download_update_btn.hide()
        frame_layout.addWidget(self.download_update_btn)

        frame_layout.addStretch()

        self.note_label = QLabel(tr(SETTINGS_RESTART_NOTE))
        self.note_label.setWordWrap(True)
        frame_layout.addWidget(self.note_label)

        layout.addWidget(frame)

    def _change_language(self, _):
        if self._loading_config:
            return
        code = self.lang_combo.currentData()
        if code:
            self._update_config("language", code)
            translation_manager.set_language(code)

    def _update_config(self, key: str, value):
        if self._loading_config:
            return
        try:
            settings.set_and_emit(key, value)
        except Exception:
            pass

    def _on_transparent_ui_changed(self, state):
        if self._loading_config:
            return
        enabled = state == CHECKED
        settings.set_and_emit("transparent_ui", enabled)
        mw = self.window()
        if mw and hasattr(mw, "set_transparent_ui"):
            mw.set_transparent_ui(enabled)

    def _load_config(self):
        self._loading_config = True
        widgets = [
            self.rpc_checkbox, self.stealth_checkbox, self.plugins_checkbox,
            self.transparent_checkbox, self.telemetry_checkbox,
            self.auto_update_check_checkbox, self.auto_install_checkbox,
            self.lang_combo,
        ]
        for w in widgets:
            w.blockSignals(True)
        try:
            self.rpc_checkbox.setChecked(settings.rpc)
            self.stealth_checkbox.setChecked(settings.stealth_title)
            self.plugins_checkbox.setChecked(settings.load_plugins)
            self.transparent_checkbox.setChecked(settings.transparent_ui)
            self.telemetry_checkbox.setChecked(getattr(settings, "telemetry", True))
            self.auto_update_check_checkbox.setChecked(settings.auto_update_check)
            self.auto_install_checkbox.setChecked(settings.auto_update_install)
            idx = self.lang_combo.findData(settings.language)
            if idx >= 0:
                self.lang_combo.setCurrentIndex(idx)
        except Exception:
            pass
        finally:
            for w in widgets:
                w.blockSignals(False)
            self._loading_config = False

    def retranslate_ui(self):
        self.title_label.setText(tr(SCREEN_TITLE_SETTINGS))
        self.lang_label.setText(tr(SETTINGS_LANGUAGE))
        self.rpc_checkbox.setText(tr(SETTINGS_RPC))
        self.stealth_checkbox.setText(tr(SETTINGS_STEALTH))
        self.plugins_checkbox.setText(tr(SETTINGS_PLUGINS))
        self.transparent_checkbox.setText(tr(SETTINGS_TRANSPARENT_UI))
        self.telemetry_checkbox.setText(tr(SETTINGS_TELEMETRY))
        self.auto_update_check_checkbox.setText(tr(SETTINGS_AUTO_UPDATE_CHECK))
        self.auto_install_checkbox.setText(tr(SETTINGS_AUTO_INSTALL))
        self.check_update_btn.setText(tr(SETTINGS_CHECK_NOW))
        self.download_update_btn.setText(tr(SETTINGS_UPDATE_DOWNLOAD_BTN))
        self.note_label.setText(tr(SETTINGS_RESTART_NOTE))

    def _ensure_updater_signals(self):
        if self._updater_connected:
            return
        from de4py.updater.manager import UpdateManager
        mgr = UpdateManager.get()
        mgr.check_complete.connect(
            self._on_update_check_complete, Qt.ConnectionType.UniqueConnection)
        mgr.check_error.connect(
            self._on_update_check_error, Qt.ConnectionType.UniqueConnection)
        self._updater_connected = True

    def _on_check_updates(self):
        self._ensure_updater_signals()
        self.check_update_btn.setEnabled(False)
        self.check_update_btn.setText(tr(SETTINGS_UPDATE_CHECKING))
        self.update_status_label.hide()
        self.download_update_btn.hide()

        from de4py.updater.manager import UpdateManager
        UpdateManager.get().check_for_updates()

    def _on_update_check_complete(self, result):
        self.check_update_btn.setEnabled(True)
        self.check_update_btn.setText(tr(SETTINGS_CHECK_NOW))
        if result.update_available:
            self.update_status_label.setText(
                tr(SETTINGS_UPDATE_AVAILABLE, version=result.remote)
            )
            self.update_status_label.setStyleSheet("color: #58A6FF;")
            self.download_update_btn.show()
        else:
            self.update_status_label.setText(tr(SETTINGS_UPDATE_UPTODATE))
            self.update_status_label.setStyleSheet("color: #8b949e;")
            self.download_update_btn.hide()
        self.update_status_label.show()

    def _on_update_check_error(self, msg):
        self.check_update_btn.setEnabled(True)
        self.check_update_btn.setText(tr(SETTINGS_CHECK_NOW))
        self.update_status_label.setText(msg)
        self.update_status_label.setStyleSheet("color: #f85149;")
        self.update_status_label.show()
        self.download_update_btn.hide()

    def _on_download_update(self):
        from de4py.updater.manager import UpdateManager
        from de4py.ui.widgets.update_dialog import UpdateDialog
        mgr = UpdateManager.get()
        result = mgr._pending_result
        if not result:
            return
        dialog = UpdateDialog(result, parent=self.window())
        dialog.fade_in()

        UCT = Qt.ConnectionType.UniqueConnection
        mgr.download_progress.connect(dialog.set_download_progress, UCT)
        mgr.update_ready.connect(lambda _: dialog.show_ready(), UCT)
        mgr.update_failed.connect(dialog.show_error, UCT)
        dialog.update_confirmed.connect(
            lambda: mgr.start_download(result.remote), UCT)
        dialog.install_confirmed.connect(mgr.apply, UCT)
        dialog.dismissed.connect(dialog.fade_out, UCT)

        self.download_update_btn.setEnabled(False)
        self.download_update_btn.setText(tr(SETTINGS_UPDATE_OPENING_DIALOG))

    def showEvent(self, event):
        super().showEvent(event)
        self._load_config()
