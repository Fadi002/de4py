# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QCheckBox, QComboBox, QPushButton,
    QHBoxLayout, QLineEdit, QScrollArea, QDialog
)
from PySide6.QtCore import Qt, QTimer

from de4py.config.config import settings
from de4py.lang import tr, translation_manager
from de4py.utils.platform_utils import IS_WINDOWS
from de4py.lang.keys import (
    SCREEN_TITLE_SETTINGS, SETTINGS_LANGUAGE, SETTINGS_RPC,
    SETTINGS_STEALTH, SETTINGS_PLUGINS, SETTINGS_RESTART_NOTE,
    SETTINGS_TRANSPARENT_UI, SETTINGS_TELEMETRY,
    SETTINGS_AUTO_UPDATE_CHECK, SETTINGS_AUTO_INSTALL, SETTINGS_CHECK_NOW,
    SETTINGS_UPDATE_CHECKING, SETTINGS_UPDATE_UPTODATE, SETTINGS_UPDATE_AVAILABLE,
    SETTINGS_UPDATE_DOWNLOAD_BTN, SETTINGS_UPDATE_OPENING_DIALOG,
    SETTINGS_AI, SETTINGS_AI_ENABLE, SETTINGS_AI_PROVIDER, SETTINGS_AI_MODEL,
    SETTINGS_AI_BASE_URL, SETTINGS_AI_API_KEY, SETTINGS_AI_ANNOTATE,
    SETTINGS_AI_EXPLAIN, SETTINGS_AI_SIMPLIFY, SETTINGS_AI_NOTE,
    SETTINGS_AI_SHOW, SETTINGS_AI_HIDE, SETTINGS_AI_CLEAR,
    SETTINGS_AI_TEST_CONNECTION, SETTINGS_AI_TESTING,
    SETTINGS_AI_SOURCE_SECURE, SETTINGS_AI_SOURCE_VAULT,
    SETTINGS_AI_SOURCE_SESSION, SETTINGS_AI_SOURCE_ENV,
    SETTINGS_AI_SOURCE_NONE, SETTINGS_AI_SOURCE_UNAVAILABLE,
    SETTINGS_AI_STORAGE_HINT, SETTINGS_AI_VAULT_UNLOCK,
    SETTINGS_AI_VAULT_WRONG_PASSWORD, SETTINGS_AI_VAULT_LOCKED,
)

CHECKED = Qt.CheckState.Checked.value

_PROVIDER_ORDER = ("ollama", "openai", "openrouter", "opencode", "gemini", "custom")


class SettingsScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading_config = False
        self._updater_connected = False
        self._update_dialog = None
        self._ai_test_workers = {}
        self._ai_cards = {}
        self._ai_widgets = []
        self._setup_ui()
        self._load_config()

    # ------------------------------------------------------------------ UI

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
        frame.setMaximumWidth(580)

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
        if not IS_WINDOWS:
            self.transparent_checkbox.hide()
        frame_layout.addWidget(self.transparent_checkbox)

        self.telemetry_checkbox = QCheckBox(tr(SETTINGS_TELEMETRY))
        self.telemetry_checkbox.stateChanged.connect(lambda s: self._update_config("telemetry", s == CHECKED))
        frame_layout.addWidget(self.telemetry_checkbox)

        # ------------------------------------------------------- AI section
        ai_sep = QFrame()
        ai_sep.setObjectName("SettingsSeparator")
        ai_sep.setFrameShape(QFrame.Shape.HLine)
        ai_sep.setFixedHeight(2)
        frame_layout.addWidget(ai_sep)

        self.ai_title_label = QLabel(tr(SETTINGS_AI))
        self.ai_title_label.setObjectName("SettingsSectionTitle")
        frame_layout.addWidget(self.ai_title_label)

        self.ai_enable_checkbox = QCheckBox(tr(SETTINGS_AI_ENABLE))
        self.ai_enable_checkbox.stateChanged.connect(lambda s: self._update_config("ai_enabled", s == CHECKED))
        frame_layout.addWidget(self.ai_enable_checkbox)

        provider_row = QHBoxLayout()
        self.ai_provider_label = QLabel(tr(SETTINGS_AI_PROVIDER))
        self.ai_provider_label.setFixedWidth(120)
        provider_row.addWidget(self.ai_provider_label)
        self.ai_provider_combo = QComboBox()
        for provider_id in _PROVIDER_ORDER:
            self.ai_provider_combo.addItem(_provider_display(provider_id), provider_id)
        self.ai_provider_combo.currentIndexChanged.connect(self._on_ai_provider_changed)
        provider_row.addWidget(self.ai_provider_combo, 1)
        frame_layout.addLayout(provider_row)

        self.ai_annotate_checkbox = QCheckBox(tr(SETTINGS_AI_ANNOTATE))
        self.ai_annotate_checkbox.stateChanged.connect(lambda s: self._update_config("ai_annotate", s == CHECKED))
        frame_layout.addWidget(self.ai_annotate_checkbox)

        self.ai_explain_checkbox = QCheckBox(tr(SETTINGS_AI_EXPLAIN))
        self.ai_explain_checkbox.stateChanged.connect(lambda s: self._update_config("ai_explain", s == CHECKED))
        frame_layout.addWidget(self.ai_explain_checkbox)

        self.ai_simplify_checkbox = QCheckBox(tr(SETTINGS_AI_SIMPLIFY))
        self.ai_simplify_checkbox.stateChanged.connect(lambda s: self._update_config("ai_simplify", s == CHECKED))
        frame_layout.addWidget(self.ai_simplify_checkbox)

        self.ai_note_label = QLabel(tr(SETTINGS_AI_NOTE))
        self.ai_note_label.setWordWrap(True)
        self.ai_note_label.setStyleSheet("color: #8b949e;")
        frame_layout.addWidget(self.ai_note_label)

        self.ai_storage_label = QLabel("")
        self.ai_storage_label.setWordWrap(True)
        self.ai_storage_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        frame_layout.addWidget(self.ai_storage_label)

        self.ai_unlock_vault_btn = QPushButton(tr(SETTINGS_AI_VAULT_UNLOCK))
        self.ai_unlock_vault_btn.setFixedHeight(28)
        self.ai_unlock_vault_btn.clicked.connect(self._on_unlock_vault)
        self.ai_unlock_vault_btn.hide()
        frame_layout.addWidget(
            self.ai_unlock_vault_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        for provider_id in _PROVIDER_ORDER:
            card = self._build_provider_card(provider_id)
            frame_layout.addWidget(card["frame"])

        # ---------------------------------------------------- update section
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

        scroll = QScrollArea()
        scroll.setObjectName("SettingsScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(frame)
        scroll.setMaximumWidth(620)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(scroll, 1)
        self._scroll = scroll
        self._scroll_content = frame

    def _build_provider_card(self, provider_id: str) -> dict:
        try:
            from de4py.ai.client import PROVIDERS
            preset = PROVIDERS.get(provider_id, {})
        except Exception:
            preset = {}
        needs_key = bool(preset.get("needs_key", provider_id not in ("ollama", "custom")))
        show_url = provider_id in ("ollama", "custom")

        frame = QFrame()
        frame.setObjectName("PluginCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        title = QLabel(_provider_display(provider_id))
        title.setStyleSheet("font-weight: bold; color: #58A6FF; font-size: 12px;")
        layout.addWidget(title)

        model_row = QHBoxLayout()
        model_label = QLabel(tr(SETTINGS_AI_MODEL))
        model_label.setFixedWidth(70)
        model_row.addWidget(model_label)
        model_combo = QComboBox()
        model_combo.setEditable(True)
        model_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        model_combo.setMinimumWidth(140)
        model_combo.lineEdit().setPlaceholderText(preset.get("default_model", ""))
        for m in preset.get("models", []) or []:
            model_combo.addItem(m)
        model_combo.lineEdit().editingFinished.connect(
            lambda p=provider_id: self._on_model_edited(p))
        # ``editingFinished`` only fires for typed edits; picking a known model
        # from the popup emits ``activated`` instead, so both must save.
        model_combo.activated.connect(
            lambda idx, p=provider_id: self._on_model_edited(p))
        model_row.addWidget(model_combo, 1)
        layout.addLayout(model_row)

        url_edit = None
        if show_url:
            url_row = QHBoxLayout()
            url_label = QLabel(tr(SETTINGS_AI_BASE_URL))
            url_label.setFixedWidth(70)
            url_row.addWidget(url_label)
            url_edit = QLineEdit()
            url_edit.setPlaceholderText(preset.get("base_url", ""))
            url_edit.editingFinished.connect(
                lambda p=provider_id: self._on_url_edited(p))
            url_row.addWidget(url_edit, 1)
            layout.addLayout(url_row)

        key_edit = None
        show_btn = None
        clear_btn = None
        if needs_key:
            key_row = QHBoxLayout()
            key_label = QLabel(tr(SETTINGS_AI_API_KEY))
            key_label.setFixedWidth(70)
            key_row.addWidget(key_label)
            key_edit = QLineEdit()
            key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            key_edit.editingFinished.connect(
                lambda p=provider_id: self._on_key_edited(p))
            key_row.addWidget(key_edit, 1)
            show_btn = QPushButton(tr(SETTINGS_AI_SHOW))
            show_btn.setMinimumWidth(60)
            show_btn.clicked.connect(lambda: self._on_show_hide(provider_id))
            key_row.addWidget(show_btn)
            clear_btn = QPushButton(tr(SETTINGS_AI_CLEAR))
            clear_btn.setMinimumWidth(60)
            clear_btn.clicked.connect(lambda: self._on_clear_key(provider_id))
            key_row.addWidget(clear_btn)
            layout.addLayout(key_row)

        source_label = QLabel("")
        source_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(source_label)

        test_row = QHBoxLayout()
        test_btn = QPushButton(tr(SETTINGS_AI_TEST_CONNECTION))
        test_btn.setFixedWidth(120)
        test_btn.clicked.connect(lambda: self._on_test_connection(provider_id))
        test_row.addWidget(test_btn)
        status_label = QLabel("")
        status_label.setWordWrap(True)
        status_label.setStyleSheet("font-size: 11px;")
        test_row.addWidget(status_label, 1)
        layout.addLayout(test_row)

        card = {
            "provider": provider_id,
            "frame": frame,
            "title": title,
            "model_combo": model_combo,
            "model_label": model_label,
            "url_edit": url_edit,
            "key_edit": key_edit,
            "show_btn": show_btn,
            "clear_btn": clear_btn,
            "source_label": source_label,
            "status_label": status_label,
            "test_btn": test_btn,
        }
        self._ai_cards[provider_id] = card
        self._ai_widgets.extend(
            w for w in (model_combo, url_edit, key_edit) if w is not None)
        return card

    # ------------------------------------------------------------- actions

    def _change_language(self, _):
        if self._loading_config:
            return
        code = self.lang_combo.currentData()
        if code:
            self._update_config("language", code)
            translation_manager.set_language(code)

    def _on_ai_provider_changed(self):
        if self._loading_config:
            return
        self._update_config("ai_provider", self.ai_provider_combo.currentData())

    def _on_model_edited(self, provider: str):
        if self._loading_config:
            return
        model = self._ai_cards[provider]["model_combo"].lineEdit().text().strip()
        self._update_config(f"ai_{provider}_model", model)

    def _on_url_edited(self, provider: str):
        if self._loading_config:
            return
        url = self._ai_cards[provider]["url_edit"].text().strip()
        self._update_config(f"ai_{provider}_base_url", url)

    def _on_key_edited(self, provider: str):
        if self._loading_config:
            return
        key = self._ai_cards[provider]["key_edit"].text().strip()
        if not key:
            return
        try:
            from de4py.ai.credentials import set_secret
            saved = set_secret(provider, key, mode="auto")
        except Exception:
            saved = False
        if not saved:
            saved = self._prompt_credential_storage(provider, key) == "saved"
            if not saved:
                self._ai_cards[provider]["key_edit"].clear()
        self._refresh_credential_status(provider)

    def _on_show_hide(self, provider: str):
        card = self._ai_cards[provider]
        edit = card["key_edit"]
        if edit.echoMode() == QLineEdit.EchoMode.Password:
            edit.setEchoMode(QLineEdit.EchoMode.Normal)
            card["show_btn"].setText(tr(SETTINGS_AI_HIDE))
        else:
            edit.setEchoMode(QLineEdit.EchoMode.Password)
            card["show_btn"].setText(tr(SETTINGS_AI_SHOW))

    def _on_clear_key(self, provider: str):
        if self._loading_config:
            return
        try:
            from de4py.ai.credentials import delete_secret
            delete_secret(provider)
        except Exception:
            pass
        self._ai_cards[provider]["key_edit"].clear()
        self._refresh_credential_status(provider)

    def _prompt_credential_storage(self, provider: str, key: str) -> str:
        """Ask the user how to persist a credential when no secure backend is
        available. Never falls back to plaintext."""
        try:
            from de4py.ai.credentials import (
                create_vault, set_secret, set_session_secret,
                unlock_vault, vault_enabled,
            )
        except Exception:
            return "cancelled"
        from de4py.ui.widgets.ai_vault_dialog import AIVaultDialog

        dialog = AIVaultDialog("choose", self.window())
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.chosen == "cancel":
            return "cancelled"
        if dialog.chosen == "session":
            set_session_secret(provider, key)
            return "saved"

        if vault_enabled():
            prompt = AIVaultDialog("unlock", self.window())
            if prompt.exec() != QDialog.DialogCode.Accepted:
                return "cancelled"
            if not unlock_vault(prompt.password_value):
                self._ai_cards[provider]["status_label"].setText(
                    tr(SETTINGS_AI_VAULT_WRONG_PASSWORD))
                return "cancelled"
        else:
            prompt = AIVaultDialog("create", self.window())
            if prompt.exec() != QDialog.DialogCode.Accepted:
                return "cancelled"
            if not create_vault(prompt.password_value):
                return "cancelled"
        return "saved" if set_secret(provider, key, mode="vault") else "cancelled"

    def _refresh_credential_status(self, provider: str):
        card = self._ai_cards.get(provider)
        if card is None:
            return
        try:
            from de4py.ai.client import PROVIDERS
            from de4py.ai.credentials import credential_source
            env_key = PROVIDERS.get(provider, {}).get("env_key")
            source = credential_source(provider, env_key)
        except Exception:
            source = "none"
        label = card["source_label"]
        if source == "stored":
            label.setText(tr(SETTINGS_AI_SOURCE_SECURE))
            label.setStyleSheet("font-size: 11px; color: #3fb950;")
        elif source == "vault":
            label.setText(tr(SETTINGS_AI_SOURCE_VAULT))
            label.setStyleSheet("font-size: 11px; color: #3fb950;")
        elif source == "session":
            label.setText(tr(SETTINGS_AI_SOURCE_SESSION))
            label.setStyleSheet("font-size: 11px; color: #58A6FF;")
        elif source == "env":
            label.setText(tr(SETTINGS_AI_SOURCE_ENV))
            label.setStyleSheet("font-size: 11px; color: #58A6FF;")
        elif source == "vault_locked":
            label.setText(tr(SETTINGS_AI_VAULT_LOCKED))
            label.setStyleSheet("font-size: 11px; color: #d29922;")
        elif source == "none":
            try:
                from de4py.ai.credentials import persistent_backend_available
                storage_ok = persistent_backend_available()
            except Exception:
                storage_ok = True
            if not storage_ok:
                label.setText(tr(SETTINGS_AI_SOURCE_UNAVAILABLE))
                label.setStyleSheet("font-size: 11px; color: #d29922;")
            else:
                label.setText(tr(SETTINGS_AI_SOURCE_NONE))
                label.setStyleSheet("font-size: 11px; color: #8b949e;")

    def _on_unlock_vault(self):
        try:
            from de4py.ai.credentials import unlock_vault, vault_enabled
        except Exception:
            return
        if not vault_enabled():
            return
        from de4py.ui.widgets.ai_vault_dialog import AIVaultDialog
        prompt = AIVaultDialog("unlock", self.window())
        if prompt.exec() != QDialog.DialogCode.Accepted:
            return
        if unlock_vault(prompt.password_value):
            self._refresh_all_credential_status()
            self._update_unlock_button()
        else:
            self.ai_storage_label.setText(tr(SETTINGS_AI_VAULT_WRONG_PASSWORD))
            self.ai_storage_label.setStyleSheet("color: #f85149; font-size: 11px;")

    def _update_unlock_button(self):
        try:
            from de4py.ai.credentials import vault_enabled, vault_unlocked
            visible = vault_enabled() and not vault_unlocked()
        except Exception:
            visible = False
        self.ai_unlock_vault_btn.setVisible(visible)

    def _refresh_all_credential_status(self):
        for provider_id in self._ai_cards:
            self._refresh_credential_status(provider_id)

    def _on_test_connection(self, provider: str):
        worker = self._ai_test_workers.get(provider)
        if worker and worker.isRunning():
            return
        card = self._ai_cards[provider]
        card["test_btn"].setEnabled(False)
        card["test_btn"].setText(tr(SETTINGS_AI_TESTING))
        card["status_label"].setText("")
        worker = self._make_test_worker(provider)
        self._ai_test_workers[provider] = worker
        worker.start()

    def _make_test_worker(self, provider: str):
        from de4py.ui.workers.ai_test_worker import AITestWorker
        worker = AITestWorker(provider, self)
        worker.test_complete.connect(
            lambda p, ok, msg, lat: self._on_ai_test_done(p, ok, msg, lat))
        return worker

    def _on_ai_test_done(self, provider: str, ok: bool, message: str, latency: float):
        card = self._ai_cards.get(provider)
        if card is None:
            return
        card["test_btn"].setEnabled(True)
        card["test_btn"].setText(tr(SETTINGS_AI_TEST_CONNECTION))
        if ok:
            card["status_label"].setText(
                f"✓ {message} · {latency:.0f} ms")
            card["status_label"].setStyleSheet("font-size: 11px; color: #3fb950;")
        else:
            card["status_label"].setText(f"✕ {message}")
            card["status_label"].setStyleSheet("font-size: 11px; color: #f85149;")

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

    # ------------------------------------------------------------- loading

    def _load_config(self):
        self._loading_config = True
        widgets = [
            self.rpc_checkbox, self.stealth_checkbox, self.plugins_checkbox,
            self.transparent_checkbox, self.telemetry_checkbox,
            self.auto_update_check_checkbox, self.auto_install_checkbox,
            self.lang_combo, self.ai_enable_checkbox, self.ai_annotate_checkbox,
            self.ai_explain_checkbox, self.ai_simplify_checkbox,
            self.ai_provider_combo,
        ] + list(self._ai_widgets)
        for w in widgets:
            w.blockSignals(True)
        try:
            self.rpc_checkbox.setChecked(settings.rpc)
            self.stealth_checkbox.setChecked(settings.stealth_title)
            self.plugins_checkbox.setChecked(settings.load_plugins)
            self.transparent_checkbox.setChecked(settings.transparent_ui)
            self.telemetry_checkbox.setChecked(settings.telemetry)
            self.auto_update_check_checkbox.setChecked(settings.auto_update_check)
            self.auto_install_checkbox.setChecked(settings.auto_update_install)
            self.ai_enable_checkbox.setChecked(settings.ai_enabled)
            self.ai_annotate_checkbox.setChecked(settings.ai_annotate)
            self.ai_explain_checkbox.setChecked(settings.ai_explain)
            self.ai_simplify_checkbox.setChecked(settings.ai_simplify)
            idx = self.ai_provider_combo.findData(settings.ai_provider)
            if idx < 0:
                idx = 0
            self.ai_provider_combo.setCurrentIndex(idx)
            idx = self.lang_combo.findData(settings.language)
            if idx >= 0:
                self.lang_combo.setCurrentIndex(idx)

            try:
                from de4py.ai.credentials import get_secret, storage_summary
            except Exception:
                get_secret = lambda p: ""  # noqa: E731
                storage_summary = lambda: ""  # noqa: E731
            self.ai_storage_label.setText(
                tr(SETTINGS_AI_STORAGE_HINT, storage=storage_summary()))
            self.ai_storage_label.setStyleSheet("color: #8b949e; font-size: 11px;")
            self._update_unlock_button()

            for provider_id, card in self._ai_cards.items():
                model_key, url_key = f"ai_{provider_id}_model", f"ai_{provider_id}_base_url"
                model = getattr(settings, model_key, "") or ""
                if not model:
                    model = getattr(settings, "ai_model", "") or ""
                url = getattr(settings, url_key, "") or ""
                if not url:
                    url = getattr(settings, "ai_base_url", "") or ""
                combo = card["model_combo"]
                if model:
                    combo.setCurrentText(model)
                if card["url_edit"] is not None and url:
                    card["url_edit"].setText(url)
                if card["key_edit"] is not None:
                    card["key_edit"].setText(get_secret(provider_id))
                self._refresh_credential_status(provider_id)
        except Exception:
            pass
        finally:
            for w in widgets:
                w.blockSignals(False)
            self._loading_config = False

    # ------------------------------------------------------------ navigation

    def focus_ai_section(self):
        """Scroll the AI section into view (used by the deobfuscator screen's
        'Configure AI' button)."""
        if self._scroll and self.ai_title_label:
            self._scroll.ensureWidgetVisible(self.ai_title_label, 0, 40)

    # ----------------------------------------------------------- translation

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
        self.ai_title_label.setText(tr(SETTINGS_AI))
        self.ai_enable_checkbox.setText(tr(SETTINGS_AI_ENABLE))
        self.ai_provider_label.setText(tr(SETTINGS_AI_PROVIDER))
        self.ai_annotate_checkbox.setText(tr(SETTINGS_AI_ANNOTATE))
        self.ai_explain_checkbox.setText(tr(SETTINGS_AI_EXPLAIN))
        self.ai_simplify_checkbox.setText(tr(SETTINGS_AI_SIMPLIFY))
        self.ai_note_label.setText(tr(SETTINGS_AI_NOTE))
        self.check_update_btn.setText(tr(SETTINGS_CHECK_NOW))
        self.download_update_btn.setText(tr(SETTINGS_UPDATE_DOWNLOAD_BTN))
        self.note_label.setText(tr(SETTINGS_RESTART_NOTE))
        for provider_id, card in self._ai_cards.items():
            card["model_label"].setText(tr(SETTINGS_AI_MODEL))
            card["test_btn"].setText(tr(SETTINGS_AI_TEST_CONNECTION))
            if card["show_btn"] is not None:
                card["show_btn"].setText(tr(SETTINGS_AI_SHOW))
            if card["clear_btn"] is not None:
                card["clear_btn"].setText(tr(SETTINGS_AI_CLEAR))
            self._refresh_credential_status(provider_id)
        try:
            from de4py.ai.credentials import storage_summary
            self.ai_storage_label.setText(
                tr(SETTINGS_AI_STORAGE_HINT, storage=storage_summary()))
        except Exception:
            pass

    # ------------------------------------------------------------ updater

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

        dialog = self._update_dialog
        if dialog is None:
            dialog = UpdateDialog(result, parent=self.window())
            self._update_dialog = dialog
            mgr.download_progress.connect(dialog.set_download_progress)
            mgr.update_ready.connect(lambda _: dialog.show_ready())
            mgr.update_failed.connect(dialog.show_error)
            mgr.update_failed.connect(self._reenable_download_btn)
            dialog.update_confirmed.connect(
                lambda: mgr.start_download(
                    mgr._pending_result.remote if mgr._pending_result else ""))
            dialog.install_confirmed.connect(mgr.apply)
            dialog.dismissed.connect(self._on_update_dialog_dismissed)
        else:
            dialog.set_result(result)
        dialog.fade_in()

        self.download_update_btn.setEnabled(False)
        self.download_update_btn.setText(tr(SETTINGS_UPDATE_OPENING_DIALOG))

    def _reenable_download_btn(self):
        self.download_update_btn.setEnabled(True)
        self.download_update_btn.setText(tr(SETTINGS_UPDATE_DOWNLOAD_BTN))

    def _on_update_dialog_dismissed(self):
        self._reenable_download_btn()
        dialog, self._update_dialog = self._update_dialog, None
        if dialog is not None:
            QTimer.singleShot(400, dialog.deleteLater)

    def showEvent(self, event):
        super().showEvent(event)
        self._load_config()


def _provider_display(provider_id: str) -> str:
    try:
        from de4py.ai.providers import provider_label
        return provider_label(provider_id)
    except Exception:
        return provider_id
