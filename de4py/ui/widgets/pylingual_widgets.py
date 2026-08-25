# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextBrowser, QCheckBox, QFrame,
    QGraphicsOpacityEffect,
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Signal, Property
from PySide6.QtGui import QColor, QPainter

from de4py.lang import tr
from de4py.ui.widgets.glass_utils import GlassBlurCache
from de4py.lang.keys import (
    PYLINGUAL_CANCEL, PYLINGUAL_I_ACCEPT,
)


@dataclass
class TOSConfig:
    title: str = "PyLingual Terms of Service"
    acceptance_text: str = "I have read and accept the PyLingual privacy TOS"
    tos_content: str = ""


class TOSDialog(QWidget):
    accepted = Signal()
    rejected = Signal()

    def __init__(self, config: TOSConfig = TOSConfig(), parent=None):
        super().__init__(parent)
        self.config = config
        self.setObjectName("TOSOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        self._blurred_bg = None
        self._lock_events = False
        self._fade_target = None
        self._setup_ui()
        self._setup_animation()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addStretch(1)

        self.modal_frame = QFrame()
        self.modal_frame.setObjectName("StyledFrame")
        self.modal_frame.setFixedSize(500, 400)

        frame_layout = QVBoxLayout(self.modal_frame)
        frame_layout.setContentsMargins(20, 20, 20, 20)
        frame_layout.setSpacing(15)

        title_label = QLabel(self.config.title)
        title_label.setObjectName("TitleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(title_label)

        self.tos_browser = QTextBrowser()
        self.tos_browser.setObjectName("ChangelogContent")
        self.tos_browser.setText(self.config.tos_content)
        frame_layout.addWidget(self.tos_browser)

        self.accept_checkbox = QCheckBox(self.config.acceptance_text)
        self.accept_checkbox.stateChanged.connect(self._toggle_accept_btn)
        frame_layout.addWidget(self.accept_checkbox)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        self.cancel_btn = QPushButton(tr(PYLINGUAL_CANCEL))

        self.cancel_btn.setMinimumHeight(35)
        self.cancel_btn.clicked.connect(self._on_reject)

        self.accept_btn = QPushButton(tr(PYLINGUAL_I_ACCEPT))

        self.accept_btn.setMinimumHeight(35)
        self.accept_btn.setEnabled(False)
        self.accept_btn.clicked.connect(self._on_accept)

        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.accept_btn)
        frame_layout.addLayout(btn_layout)

        main_layout.addWidget(self.modal_frame, alignment=Qt.AlignmentFlag.AlignCenter)
        main_layout.addStretch(1)

    def _setup_animation(self):
        self.effect = QGraphicsOpacityEffect(self)
        # QGraphicsOpacityEffect defaults to 0.7 — reset so fade_in actually
        # fades from transparent instead of popping in at 70% opacity.
        self.effect.setOpacity(0.0)
        self.setGraphicsEffect(self.effect)
        self.anim = QPropertyAnimation(self.effect, b"opacity")
        self.anim.setDuration(300)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.finished.connect(self._on_fade_finished)

    def fade_in(self):
        self.anim.stop()
        self._fade_target = "visible"
        self.show()
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.setStartValue(self.effect.opacity())
        self.anim.setEndValue(1.0)
        self.anim.start()

    def fade_out(self):
        self.anim.stop()
        self._fade_target = "hidden"
        self.anim.setStartValue(self.effect.opacity())
        self.anim.setEndValue(0.0)
        self.anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self.anim.start()

    def _on_accept(self):
        self.accepted.emit()
        self.fade_out()

    def _on_reject(self):
        self.rejected.emit()
        self.fade_out()

    def _toggle_accept_btn(self, state):
        self.accept_btn.setEnabled(state == Qt.CheckState.Checked.value)

    def _create_blur_cache(self):
        top_window = self.window()
        if not top_window or self._lock_events:
            return None

        self._lock_events = True
        try:
            return GlassBlurCache.capture(
                top_window,
                exclude_widget=self,
                blur_radius=28,
                downsample_divisor=2,
                force_refresh=False,
            )
        finally:
            self._lock_events = False

    def showEvent(self, event):
        super().showEvent(event)
        if not self._lock_events and self.parent():
            self.setGeometry(self.parent().rect())
            # Resizing during show doesn't re-activate the layout on a
            # translucent widget, leaving the frame at the pre-show size.
            # Force a relayout so the modal_frame stays centered.
            self.layout().invalidate()
            self.layout().activate()
            self._blurred_bg = self._create_blur_cache()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.parent():
            self.setGeometry(self.parent().rect())

    def hideEvent(self, event):
        super().hideEvent(event)
        if not self._lock_events:
            self._blurred_bg = None

    def _on_fade_finished(self):
        if self._fade_target == "hidden":
            self.hide()
        self._fade_target = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        if self._blurred_bg:
            painter.drawPixmap(self.rect(), self._blurred_bg)

        painter.fillRect(self.rect(), QColor(0, 0, 0, 160))
        painter.end()


class ModernToggle(QWidget):
    toggled = Signal(bool)

    def __init__(self, parent=None, active_color="#0287CF"):
        super().__init__(parent)
        self.setFixedSize(50, 26)
        self._active_color = active_color
        self._checked = False
        self._thumb_pos = 3

        self._anim = QPropertyAnimation(self, b"thumb_pos")
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def get_thumb_pos(self):
        return self._thumb_pos

    def set_thumb_pos(self, pos):
        self._thumb_pos = pos
        self.update()

    thumb_pos = Property(int, get_thumb_pos, set_thumb_pos)

    def is_checked(self):
        return self._checked

    def set_checked(self, checked):
        if self._checked == checked:
            return
        self._checked = checked
        self._anim.setStartValue(self._thumb_pos)
        self._anim.setEndValue(27 if checked else 3)
        self._anim.start()
        self.toggled.emit(checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_checked(not self._checked)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        color = QColor(self._active_color) if self._checked else QColor("#333333")
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 13, 13)

        painter.setBrush(QColor("white"))
        painter.drawEllipse(self._thumb_pos, 3, 20, 20)
        painter.end()
