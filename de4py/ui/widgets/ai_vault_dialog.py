# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QFrame, QLineEdit
)

from de4py.lang import tr
from de4py.lang.keys import (
    SETTINGS_AI_VAULT_TITLE, SETTINGS_AI_VAULT_CREATE, SETTINGS_AI_VAULT_UNLOCK,
    SETTINGS_AI_VAULT_PASSWORD, SETTINGS_AI_VAULT_CONFIRM, SETTINGS_AI_VAULT_MISMATCH,
    SETTINGS_AI_VAULT_CHOOSE, SETTINGS_AI_VAULT_SESSION, DEOBF_AI_DECLINE,
)


class AIVaultDialog(QDialog):
    """Collect a vault password, or offer the session-only fallback when no
    secure storage backend is available.

    ``mode`` is ``create`` (password + confirm), ``unlock`` (password), or
    ``choose`` (create vault / session-only / cancel).
    """

    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.chosen = "cancel"
        self.password_value = ""
        self.setModal(True)
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        frame = QFrame()
        frame.setObjectName("StyledFrame")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(20, 16, 20, 16)
        frame_layout.setSpacing(10)

        if mode == "choose":
            title = QLabel(tr(SETTINGS_AI_VAULT_TITLE))
            title.setObjectName("SubtitleLabel")
            frame_layout.addWidget(title)
            message = QLabel(tr(SETTINGS_AI_VAULT_CHOOSE))
            message.setWordWrap(True)
            message.setStyleSheet("color: #c9d1d9;")
            frame_layout.addWidget(message)

            row = QHBoxLayout()
            row.addStretch()
            self.cancel_btn = QPushButton(tr(DEOBF_AI_DECLINE))
            self.cancel_btn.clicked.connect(self.reject)
            row.addWidget(self.cancel_btn)
            self.session_btn = QPushButton(tr(SETTINGS_AI_VAULT_SESSION))
            self.session_btn.clicked.connect(self._choose_session)
            row.addWidget(self.session_btn)
            self.create_btn = QPushButton(tr(SETTINGS_AI_VAULT_CREATE))
            self.create_btn.clicked.connect(self._choose_create)
            row.addWidget(self.create_btn)
            frame_layout.addLayout(row)
        else:
            self.setWindowTitle(tr(SETTINGS_AI_VAULT_UNLOCK if mode == "unlock"
                                   else SETTINGS_AI_VAULT_CREATE))
            title = QLabel(self.windowTitle())
            title.setObjectName("SubtitleLabel")
            frame_layout.addWidget(title)

            self.password_edit = QLineEdit()
            self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.password_edit.setPlaceholderText(tr(SETTINGS_AI_VAULT_PASSWORD))
            frame_layout.addWidget(self.password_edit)

            self.confirm_edit = None
            if mode == "create":
                self.confirm_edit = QLineEdit()
                self.confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
                self.confirm_edit.setPlaceholderText(tr(SETTINGS_AI_VAULT_CONFIRM))
                frame_layout.addWidget(self.confirm_edit)

            self.error_label = QLabel(tr(SETTINGS_AI_VAULT_MISMATCH))
            self.error_label.setStyleSheet("color: #f85149;")
            self.error_label.hide()
            frame_layout.addWidget(self.error_label)

            row = QHBoxLayout()
            row.addStretch()
            self.cancel_btn = QPushButton(tr(DEOBF_AI_DECLINE))
            self.cancel_btn.clicked.connect(self.reject)
            row.addWidget(self.cancel_btn)
            self.ok_btn = QPushButton(tr(SETTINGS_AI_VAULT_CREATE
                                         if mode == "create"
                                         else SETTINGS_AI_VAULT_UNLOCK))
            self.ok_btn.clicked.connect(self._submit_password)
            row.addWidget(self.ok_btn)
            frame_layout.addLayout(row)

        layout.addWidget(frame)

    def _choose_session(self):
        self.chosen = "session"
        self.accept()

    def _choose_create(self):
        self.chosen = "vault"
        self.accept()

    def _submit_password(self):
        password = self.password_edit.text()
        if not password:
            return
        if self.confirm_edit is not None and password != self.confirm_edit.text():
            self.error_label.show()
            return
        self.password_value = password
        self.chosen = "vault" if self.mode == "create" else "unlock"
        self.accept()
