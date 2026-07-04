# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy,
    QLineEdit, QPushButton, QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QPainter, QColor

from de4py.lang import tr
from de4py.lang.keys import DIALOG_VALUE_PLACEHOLDER
from de4py.ui.widgets.glass_utils import GlassBlurCache
from de4py.ui.motion.spring import spring_gentle, spring_settle, InertiaChain
from de4py.ui.motion.material import MaterialState, MaterialPainter


class ModalOverlay(QWidget):
    submitted = Signal(str)
    closed = Signal()

    def __init__(self, title: str, input_label: str, button_label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("ModalOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._setup_ui(title, input_label, button_label)
        self._blurred_bg = None
        self._lock_events = False

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_spring = spring_gentle()
        self._scale_spring = spring_settle(0.94)
        self._translate_spring = spring_settle(20.0)
        self._backdrop_spring = spring_gentle()
        self._backdrop_alpha = 100.0
        self._opening = False
        self._closing = False

        self._material = MaterialState(self, on_tick=self._sync_springs)
        from de4py.ui.motion.manager import MotionManager
        MotionManager.register_material(self, self._material)

    def _sync_springs(self):
        dt = 0.016
        self._fade_spring.tick(dt)
        self._scale_spring.tick(dt)
        self._translate_spring.tick(dt)
        self._backdrop_spring.tick(dt)

        self._opacity_effect.setOpacity(max(0.0, min(1.0, self._fade_spring.value)))
        self._backdrop_alpha = max(0.0, min(200.0, self._backdrop_spring.value))

        all_settled = (
            self._fade_spring.is_settled()
            and self._scale_spring.is_settled()
            and self._translate_spring.is_settled()
            and self._backdrop_spring.is_settled()
        )

        if all_settled:
            if self._closing:
                self._closing = False
                self.setHidden(True)
            self._material._dirty = False

    def _setup_ui(self, title: str, input_label: str, button_label: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addStretch(1)

        self.modal_frame = QFrame()
        self.modal_frame.setObjectName("StyledFrame")
        self.modal_frame.setFixedWidth(400)
        self.modal_frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        frame_layout = QVBoxLayout(self.modal_frame)
        frame_layout.setContentsMargins(20, 15, 20, 15)
        frame_layout.setSpacing(10)

        header_layout = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("SubtitleLabel")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        self.close_btn = QPushButton("X")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.clicked.connect(self._on_close)
        header_layout.addWidget(self.close_btn)
        frame_layout.addLayout(header_layout)

        input_layout = QHBoxLayout()
        input_label_widget = QLabel(input_label)
        input_layout.addWidget(input_label_widget)
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText(tr(DIALOG_VALUE_PLACEHOLDER))
        self.input_field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        input_layout.addWidget(self.input_field)
        frame_layout.addLayout(input_layout)

        self.submit_btn = QPushButton(button_label)
        self.submit_btn.setFixedHeight(35)
        self.submit_btn.clicked.connect(self._on_submit)
        frame_layout.addWidget(self.submit_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.modal_frame, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

    def _on_close(self):
        self.fade_out()
        self.closed.emit()

    def _on_submit(self):
        value = self.input_field.text().strip()
        if value:
            self.submitted.emit(value)
            self.fade_out()

    def fade_in(self):
        self._closing = False
        self._opening = True
        self.setHidden(False)

        inherited_v = InertiaChain.instance().pop(0.5)

        self._fade_spring.value = self._opacity_effect.opacity()
        self._fade_spring.target = 1.0
        self._fade_spring.velocity = inherited_v * 2.0

        self._scale_spring.value = 0.94
        self._scale_spring.target = 1.0
        self._scale_spring.velocity = inherited_v

        self._translate_spring.value = 20.0
        self._translate_spring.target = 0.0
        self._translate_spring.velocity = -inherited_v * 10.0

        self._backdrop_spring.value = 100.0
        self._backdrop_spring.target = 160.0

        self._material._dirty = True
        from de4py.ui.motion.manager import MotionManager
        MotionManager.wake()

        try:
            from de4py.ui.motion.proximity import SurfaceLinker
            SurfaceLinker.instance().broadcast(self, 0.6)
        except Exception:
            pass

    def fade_out(self):
        self._opening = False
        self._closing = True

        self._fade_spring.value = self._opacity_effect.opacity()
        self._fade_spring.target = 0.0

        self._scale_spring.value = max(0.94, min(1.0, self._scale_spring.value))
        self._scale_spring.target = 0.97

        self._translate_spring.target = 8.0

        self._backdrop_spring.value = self._backdrop_alpha
        self._backdrop_spring.target = 0.0

        self._material._dirty = True
        from de4py.ui.motion.manager import MotionManager
        MotionManager.wake()

    def _create_blur_cache(self):
        top_window = self.window()
        if not top_window or self._lock_events:
            return None
        self._lock_events = True
        try:
            return GlassBlurCache.capture(
                top_window, exclude_widget=self,
                blur_radius=28, downsample_divisor=2, force_refresh=False,
            )
        finally:
            self._lock_events = False

    def showEvent(self, event):
        super().showEvent(event)
        if not self._lock_events and self.parent():
            self.setGeometry(self.parent().rect())
            self._blurred_bg = self._create_blur_cache()
        self.input_field.clear()
        self.input_field.setFocus()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.parent():
            self.setGeometry(self.parent().rect())

    def hideEvent(self, event):
        super().hideEvent(event)
        if not self._lock_events:
            self._blurred_bg = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        if self._blurred_bg:
            painter.drawPixmap(self.rect(), self._blurred_bg)

        painter.fillRect(self.rect(), QColor(0, 0, 0, int(self._backdrop_alpha)))

        scale = max(0.9, min(1.05, self._scale_spring.value))
        ty = self._translate_spring.value
        depth = max(0.0, 1.0 - scale) * 5.0

        if self.modal_frame and (abs(scale - 1.0) > 0.001 or abs(ty) > 0.5):
            frame_rect = self.modal_frame.geometry()
            center = frame_rect.center()
            painter.save()
            painter.translate(center)
            painter.scale(scale, scale)
            painter.translate(-center.x(), -center.y() + ty)
            painter.restore()

            self.modal_frame.move(
                frame_rect.x(),
                frame_rect.y() + int(ty * 0.3),
            )

        frect = QRectF(self.modal_frame.geometry())
        if depth > 0.1:
            MaterialPainter.paint_edge_sheen(painter, frect, min(1.0, depth * 0.5))

        painter.end()
