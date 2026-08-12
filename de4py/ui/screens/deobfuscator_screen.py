# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QFileDialog,
    QSizePolicy, QCheckBox, QScrollArea
)
from PySide6.QtCore import Qt

from de4py.lang import tr
from de4py.lang.keys import (
    SCREEN_TITLE_DEOBFUSCATOR,    DEOBF_SELECT_FILE, DEOBF_DEOBFUSCATE, DEOBF_RESEARCH_NOTE,
    MSG_NO_FILE_SELECTED, MSG_OPERATION_COMPLETE, MSG_OPERATION_FAILED,
    DEOBF_AI_TITLE, DEOBF_AI_ENABLE, DEOBF_AI_ANNOTATE, DEOBF_AI_EXPLAIN,
    DEOBF_AI_SIMPLIFY, DEOBF_AI_TEST, DEOBF_AI_TESTING, DEOBF_AI_TEST_OK,
    DEOBF_AI_TEST_FAIL, DEOBF_AI_STATUS, DEOBF_AI_NOT_CONFIGURED,
    DEOBF_AI_CONFIGURE, DEOBF_AI_CONSENT_TITLE, DEOBF_AI_CONSENT_CLOUD,
    DEOBF_AI_CONSENT_LOCAL
)

from de4py.ui.widgets.output_textarea import OutputTextArea
from de4py.ui.widgets.ai_consent_overlay import AIConsentOverlay
from de4py.ui.workers.deobfuscator_worker import DeobfuscatorWorker
from de4py.ui.workers.ai_test_worker import AITestWorker
from de4py.utils import sentry
import os


class DeobfuscatorScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_path = None
        self._worker = None
        self._ai_test_worker = None
        self._consent_provider = None
        self._consent_overlay = None
        self._pending_deobfuscate = False
        self._local_notice_shown = False
        self._setup_ui()
        self._refresh_ai_options_from_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 20)
        layout.setSpacing(20)

        self.title_label = QLabel(tr(SCREEN_TITLE_DEOBFUSCATOR))
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        # The two-pane content lives in a scroll area so the card can never be
        # compressed below its content (short windows, larger fonts, translated
        # labels) — without it, tight windows crush the widgets into overlaps.
        content_widget = QWidget()
        content_widget.setObjectName("DeobfContent")
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(40)

        left_frame = self._create_left_frame()
        content_layout.addWidget(left_frame)

        right_frame = self._create_right_frame()
        content_layout.addWidget(right_frame, 1)

        self.content_scroll = QScrollArea()
        self.content_scroll.setObjectName("DeobfScrollArea")
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content_scroll.setWidget(content_widget)
        layout.addWidget(self.content_scroll, 1)

    def _create_left_frame(self):
        frame = QFrame()
        frame.setObjectName("StyledFrame")
        frame.setFixedWidth(350)
        frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Maximum)

        layout = QVBoxLayout(frame)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(18, 18, 18, 18)

        self.select_btn = QPushButton(tr(DEOBF_SELECT_FILE))
        self.select_btn.clicked.connect(self._on_select_file)
        self.select_btn.setFixedHeight(30)
        layout.addWidget(self.select_btn)

        self.file_label = QLabel("None")
        self.file_label.setObjectName("FilePathLabel")
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_label.setFixedHeight(26)
        self.file_label.setWordWrap(True)

        layout.addWidget(self.file_label)

        self.ai_title = QLabel(tr(DEOBF_AI_TITLE))
        self.ai_title.setStyleSheet(
            "font-weight: bold; color: #58A6FF; font-size: 12px; margin-top: 6px;"
        )
        layout.addWidget(self.ai_title, alignment=Qt.AlignmentFlag.AlignCenter)

        self.ai_enable_checkbox = QCheckBox(tr(DEOBF_AI_ENABLE))
        self.ai_enable_checkbox.setMinimumHeight(24)
        self.ai_enable_checkbox.toggled.connect(self._on_ai_enable_toggled)
        layout.addWidget(self.ai_enable_checkbox)

        ai_features_box = QVBoxLayout()
        ai_features_box.setSpacing(10)
        ai_features_box.setContentsMargins(28, 4, 0, 4)
        self.ai_annotate_checkbox = QCheckBox(tr(DEOBF_AI_ANNOTATE))
        self.ai_explain_checkbox = QCheckBox(tr(DEOBF_AI_EXPLAIN))
        self.ai_simplify_checkbox = QCheckBox(tr(DEOBF_AI_SIMPLIFY))
        for cb in (self.ai_annotate_checkbox, self.ai_explain_checkbox,
                   self.ai_simplify_checkbox):
            cb.setMinimumHeight(24)
            ai_features_box.addWidget(cb)
        layout.addLayout(ai_features_box)

        self.ai_status_label = QLabel("")
        self.ai_status_label.setWordWrap(True)
        self.ai_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ai_status_label.setStyleSheet("font-size: 11px; color: #8b949e;")
        layout.addWidget(self.ai_status_label)

        self.ai_configure_btn = QPushButton(tr(DEOBF_AI_CONFIGURE))
        self.ai_configure_btn.setFixedHeight(24)
        self.ai_configure_btn.clicked.connect(self._on_configure_ai)
        self.ai_configure_btn.hide()
        layout.addWidget(self.ai_configure_btn)

        self.ai_test_btn = QPushButton(tr(DEOBF_AI_TEST))
        self.ai_test_btn.setFixedHeight(25)
        self.ai_test_btn.clicked.connect(self._on_test_ai)
        layout.addWidget(self.ai_test_btn)

        layout.addStretch()

        self.deobf_btn = QPushButton(tr(DEOBF_DEOBFUSCATE))
        self.deobf_btn.setMinimumWidth(120)
        self.deobf_btn.clicked.connect(self._on_deobfuscate)
        layout.addWidget(self.deobf_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.disclaimer_label = QLabel(tr(DEOBF_RESEARCH_NOTE))
        self.disclaimer_label.setObjectName("DisclaimerLabel")
        self.disclaimer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.disclaimer_label.setWordWrap(True)
        self.disclaimer_label.setStyleSheet("font-size: 10px; color: #8b949e; margin-top: 4px;")
        layout.addWidget(self.disclaimer_label)

        return frame

    def _create_right_frame(self):
        frame = QFrame()
        frame.setObjectName("StyledFrame")
        frame.setMinimumHeight(350)
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)

        self.output = OutputTextArea(show_copy=True)
        layout.addWidget(self.output)

        return frame

    def _on_select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            "",
            "Python Files (*.py);;Python Compiled (*.pyc);;Exe Files (*.exe);;All Files (*.*)"
        )
        if file_path:
            self._load_file(file_path)

    def _load_file(self, file_path: str):
        self._file_path = file_path
        filename = os.path.basename(file_path)
        self.file_label.setText(filename)
        sentry.breadcrumb(f"File selected for deobfuscation: {filename}", category="user.action", path=file_path)

    def _on_deobfuscate(self):
        if not self._file_path:
            self.window().show_notification("warning", tr(MSG_NO_FILE_SELECTED))
            return

        if self.ai_enable_checkbox.isChecked():
            if not self._maybe_require_consent():
                self._pending_deobfuscate = True
                return
        self._pending_deobfuscate = False

        with sentry.transaction("Deobfuscation Run", "tool.deobfuscate"):
            file_size = os.path.getsize(self._file_path) if os.path.exists(self._file_path) else 0
            sentry.set_extra_context("deobfuscator_meta", {
                "file_path": self._file_path,
                "file_size": file_size
            })

            self.window().show_loading()

            ai_overrides = {
                "use_llm": self.ai_enable_checkbox.isChecked(),
                "annotate": self.ai_annotate_checkbox.isChecked(),
                "ai_explain": self.ai_explain_checkbox.isChecked(),
                "ai_simplify": self.ai_simplify_checkbox.isChecked(),
            }
            self._worker = DeobfuscatorWorker(
                self._file_path, self, ai_overrides=ai_overrides
            )
            self._worker.finished.connect(self._on_deobf_finished)
            self._worker.error.connect(self._on_deobf_error)
            self._worker.start()

    def _on_deobf_finished(self, result: str):
        self.window().hide_loading()
        self.output.set_text(result)
        self.window().show_notification("success", tr(MSG_OPERATION_COMPLETE))

    def _on_deobf_error(self, error: str):
        self.window().hide_loading()
        self.output.set_text(error)
        self.window().show_notification("failure", tr(MSG_OPERATION_FAILED))

    def _on_ai_enable_toggled(self, checked: bool):
        for cb in (self.ai_annotate_checkbox, self.ai_explain_checkbox,
                   self.ai_simplify_checkbox):
            cb.setEnabled(checked)
        if checked:
            self._maybe_require_consent()
        self._refresh_ai_status()

    def _on_test_ai(self):
        if self._ai_test_worker and self._ai_test_worker.isRunning():
            return
        self.ai_test_btn.setEnabled(False)
        self.ai_test_btn.setText(tr(DEOBF_AI_TESTING))
        self._ai_test_worker = AITestWorker(parent=self)
        self._ai_test_worker.test_complete.connect(self._on_ai_test_done)
        self._ai_test_worker.start()

    def _on_ai_test_done(self, _provider: str, ok: bool, message: str, _latency: float):
        self.ai_test_btn.setEnabled(True)
        self.ai_test_btn.setText(tr(DEOBF_AI_TEST))
        if ok:
            self.window().show_notification(
                "success", f"{tr(DEOBF_AI_TEST_OK)}: {message}"
            )
        else:
            self.window().show_notification(
                "failure", f"{tr(DEOBF_AI_TEST_FAIL)}: {message}"
            )

    def _on_configure_ai(self):
        mw = self.window()
        if mw and hasattr(mw, "open_ai_settings"):
            mw.open_ai_settings()

    def _maybe_require_consent(self) -> bool:
        """Returns True when AI can proceed without asking. For a cloud
        provider that has not been acknowledged yet, raises the consent
        overlay and returns False until the user decides."""
        try:
            from de4py.config.config import settings
            from de4py.ai.providers import is_local_provider
            provider = settings.ai_provider or "ollama"
            if is_local_provider(provider):
                if not self._local_notice_shown:
                    self._local_notice_shown = True
                    self._show_consent_overlay(provider, is_local=True)
                return True
            if settings.ai_consent.get(provider):
                return True
        except Exception:
            return True
        self._show_consent_overlay(provider, is_local=False)
        return False

    def _show_consent_overlay(self, provider: str, is_local: bool):
        self._consent_provider = None if is_local else provider
        overlay = self._ensure_consent_overlay()
        # Skip re-shows while the overlay is already up, but not while it is
        # mid-fade-out — a fresh request in that window must re-open it.
        if (overlay.isVisible() and not overlay._closing
                and self._consent_provider is not None):
            return
        if is_local:
            overlay.show_consent(tr(DEOBF_AI_CONSENT_LOCAL), allow_decline=False)
        else:
            try:
                from de4py.ai.providers import provider_label
                name = provider_label(provider)
            except Exception:
                name = provider
            overlay.show_consent(
                tr(DEOBF_AI_CONSENT_CLOUD, provider=name), allow_decline=True)
        overlay.raise_()
        overlay.fade_in()

    def _ensure_consent_overlay(self):
        if self._consent_overlay is None:
            self._consent_overlay = AIConsentOverlay(self.window())
            self._consent_overlay.accepted.connect(self._on_consent_accepted)
            self._consent_overlay.declined.connect(self._on_consent_declined)
        return self._consent_overlay

    def _on_consent_accepted(self):
        provider = self._consent_provider
        self._consent_provider = None
        if provider:
            try:
                from de4py.config.config import settings
                settings.ai_consent = {**settings.ai_consent, provider: True}
                settings.save()
            except Exception:
                pass
        if self._pending_deobfuscate:
            self._pending_deobfuscate = False
            self._on_deobfuscate()

    def _on_consent_declined(self):
        was_cloud = self._consent_provider is not None
        self._consent_provider = None
        self._pending_deobfuscate = False
        if was_cloud:
            self.ai_enable_checkbox.setChecked(False)

    def _refresh_ai_status(self):
        try:
            from de4py.config.config import settings
            from de4py.ai.providers import provider_label
            from de4py.ai.client import PROVIDERS, resolve_ai_config
            from de4py.ai.credentials import credential_source
        except Exception:
            self.ai_status_label.setText("")
            return
        provider = settings.ai_provider or "ollama"
        try:
            config = resolve_ai_config()
            model = config.model if config else ""
            needs_key = PROVIDERS.get(provider, {}).get("needs_key", True)
            env_key = PROVIDERS.get(provider, {}).get("env_key")
            source = credential_source(provider, env_key)
            configured = bool(
                config and config.base_url and model
                and (not needs_key or source != "none")
            )
        except Exception:
            configured = False
            model = ""
        status = tr(DEOBF_AI_STATUS, provider=provider_label(provider),
                    model=model or "—")
        if configured:
            self.ai_status_label.setText(f"● {status}")
            self.ai_status_label.setStyleSheet("font-size: 11px; color: #3fb950;")
            self.ai_configure_btn.hide()
        else:
            self.ai_status_label.setText(f"○ {status}\n{tr(DEOBF_AI_NOT_CONFIGURED)}")
            self.ai_status_label.setStyleSheet("font-size: 11px; color: #d29922;")
            self.ai_configure_btn.show()

    def _refresh_ai_options_from_settings(self):
        try:
            from de4py.config.config import settings
        except Exception:
            return
        self.ai_enable_checkbox.setChecked(settings.ai_enabled)
        self.ai_annotate_checkbox.setChecked(settings.ai_annotate)
        self.ai_explain_checkbox.setChecked(settings.ai_explain)
        self.ai_simplify_checkbox.setChecked(settings.ai_simplify)
        self._on_ai_enable_toggled(settings.ai_enabled)
        self._refresh_ai_status()

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_ai_options_from_settings()

    def retranslate_ui(self):
        self.title_label.setText(tr(SCREEN_TITLE_DEOBFUSCATOR))
        self.select_btn.setText(tr(DEOBF_SELECT_FILE))
        self.deobf_btn.setText(tr(DEOBF_DEOBFUSCATE))
        self.disclaimer_label.setText(tr(DEOBF_RESEARCH_NOTE))
        self.ai_title.setText(tr(DEOBF_AI_TITLE))
        self.ai_enable_checkbox.setText(tr(DEOBF_AI_ENABLE))
        self.ai_annotate_checkbox.setText(tr(DEOBF_AI_ANNOTATE))
        self.ai_explain_checkbox.setText(tr(DEOBF_AI_EXPLAIN))
        self.ai_simplify_checkbox.setText(tr(DEOBF_AI_SIMPLIFY))
        self.ai_test_btn.setText(tr(DEOBF_AI_TEST))
        self.ai_configure_btn.setText(tr(DEOBF_AI_CONFIGURE))
        if self._consent_overlay is not None:
            self._consent_overlay.consent_title.setText(tr(DEOBF_AI_CONSENT_TITLE))
        self._refresh_ai_status()
        self.output.retranslate_ui()
