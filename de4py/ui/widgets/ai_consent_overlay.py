# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal

from de4py.lang import tr
from de4py.lang.keys import (
    DEOBF_AI_CONSENT_TITLE, DEOBF_AI_ACCEPT, DEOBF_AI_DECLINE,
)
from de4py.ui.widgets.modal_overlay import ModalOverlay


class AIConsentOverlay(ModalOverlay):
    """Full-window overlay asking the user before code is sent to a cloud AI
    provider.

    Reuses ModalOverlay's blur/spring/backdrop machinery; the content is a
    warning message with Continue / Cancel actions instead of a text input.
    ``accepted`` / ``declined`` fire when the user picks a side (the X button
    counts as decline).
    """

    accepted = Signal()
    declined = Signal()

    def __init__(self, parent=None):
        super().__init__("", "", "", parent)

    def _setup_ui(self, title="", input_label="", button_label=""):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.modal_frame = QFrame()
        self.modal_frame.setObjectName("StyledFrame")
        self.modal_frame.setFixedWidth(480)
        self.modal_frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)

        frame_layout = QVBoxLayout(self.modal_frame)
        frame_layout.setContentsMargins(30, 24, 30, 24)
        frame_layout.setSpacing(16)

        header_layout = QHBoxLayout()
        self.consent_title = QLabel(tr(DEOBF_AI_CONSENT_TITLE))
        self.consent_title.setObjectName("SubtitleLabel")
        header_layout.addWidget(self.consent_title)
        header_layout.addStretch()

        self.close_btn = QPushButton("X")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.clicked.connect(self._on_decline)
        header_layout.addWidget(self.close_btn)
        frame_layout.addLayout(header_layout)

        self.consent_message = QLabel("")
        self.consent_message.setWordWrap(True)
        self.consent_message.setStyleSheet("font-size: 13px; color: #e1e1e1; padding: 6px 4px;")
        frame_layout.addWidget(self.consent_message)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.decline_btn = QPushButton(tr(DEOBF_AI_DECLINE))
        self.decline_btn.setFixedHeight(32)
        self.decline_btn.clicked.connect(self._on_decline)
        btn_row.addWidget(self.decline_btn)
        self.accept_btn = QPushButton(tr(DEOBF_AI_ACCEPT))
        self.accept_btn.setFixedHeight(32)
        self.accept_btn.clicked.connect(self._on_accept)
        btn_row.addWidget(self.accept_btn)
        frame_layout.addLayout(btn_row)

        layout.addWidget(self.modal_frame, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)

    def show_consent(self, message: str, allow_decline: bool = True):
        """Fill the card with the warning and decide whether the user may
        cancel (cloud consent) or only acknowledge (local notice)."""
        self.consent_message.setText(message)
        self.decline_btn.setVisible(allow_decline)

    def _on_accept(self):
        self.accepted.emit()
        self.fade_out()

    def _on_decline(self):
        self.declined.emit()
        self.fade_out()

    def showEvent(self, event):
        # ModalOverlay.showEvent clears/focuses a text input this overlay does
        # not have — keep the geometry + blur capture, drop the input part.
        QWidget.showEvent(self, event)
        if not self._lock_events and self.parent():
            self.setGeometry(self.parent().rect())
            self._blurred_bg = self._create_blur_cache()
