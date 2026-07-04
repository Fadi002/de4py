# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QVBoxLayout, QWidget

from de4py.ui.widgets.glass_utils import GlassBlurCache
from de4py.ui.motion.spring import FramePacer, spring_gentle

_BOX_WIDTH = 400
_BOX_HEIGHT = 250
_BOX_RADIUS = 15
_BOX_BORDER_WIDTH = 4
_DEFAULT_BORDER_COLOR = QColor(88, 166, 255, 200)
_BOX_DASH_PATTERN = [4, 4]
_BACKDROP_TARGET_ALPHA = 180.0
_BACKDROP_MAX_ALPHA = 200.0
_LABEL_STYLE = "color: white; font-weight: bold; font-size: 32px;"
_SPRING_TICK_MS = 16


class DropOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DropOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._blurred_bg = None
        self._lock_events = False
        self._border_color = QColor(_DEFAULT_BORDER_COLOR)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_spring = spring_gentle()
        self._backdrop_spring = spring_gentle()
        self._backdrop_alpha = 0.0
        self._closing = False

        self._fade_timer = QTimer(self)
        self._fade_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._fade_timer.setInterval(_SPRING_TICK_MS)
        self._fade_timer.timeout.connect(self._tick_springs)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.status_label = QLabel("Drop File Here")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(_LABEL_STYLE)
        layout.addWidget(self.status_label)
        self.setHidden(True)

    def set_border_color(self, color: QColor):
        self._border_color = QColor(color)

    def _tick_springs(self):
        dt = FramePacer.instance().tick()
        self._fade_spring.tick(dt)
        self._backdrop_spring.tick(dt)

        self._opacity_effect.setOpacity(max(0.0, min(1.0, self._fade_spring.value)))
        self._backdrop_alpha = max(0.0, min(_BACKDROP_MAX_ALPHA, self._backdrop_spring.value))

        if self._fade_spring.is_settled() and self._backdrop_spring.is_settled():
            self._fade_timer.stop()
            if self._closing:
                self._closing = False
                self.setHidden(True)
                return

        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._lock_events and self.parent():
            self.setGeometry(self.parent().rect())
            self._blurred_bg = self._create_blur_cache()
        self._fade_timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.parent():
            self.setGeometry(self.parent().rect())

    def hideEvent(self, event):
        super().hideEvent(event)
        self._fade_timer.stop()
        if not self._lock_events:
            self._blurred_bg = None

    def fade_in(self):
        if not self.isHidden() and not self._closing:
            return
        self._closing = False
        self.setHidden(False)
        self._fade_spring.value = self._opacity_effect.opacity()
        self._fade_spring.target = 1.0
        self._backdrop_spring.value = self._backdrop_alpha
        self._backdrop_spring.target = _BACKDROP_TARGET_ALPHA
        self._fade_timer.start()
        self.update()

    def fade_out(self):
        if self._closing or self.isHidden():
            return
        self._closing = True
        self._fade_spring.value = self._opacity_effect.opacity()
        self._fade_spring.target = 0.0
        self._backdrop_spring.value = self._backdrop_alpha
        self._backdrop_spring.target = 0.0
        self._fade_timer.start()

    def _create_blur_cache(self):
        top_window = self.window()
        if not top_window or self._lock_events:
            return None
        self._lock_events = True
        try:
            return GlassBlurCache.capture(
                top_window, exclude_widget=self,
                blur_radius=20, downsample_divisor=2, force_refresh=False,
            )
        finally:
            self._lock_events = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        if self._blurred_bg:
            painter.drawPixmap(rect, self._blurred_bg)

        painter.fillRect(rect, QColor(0, 0, 0, int(self._backdrop_alpha)))

        half_w = rect.width() // 2
        half_h = rect.height() // 2
        half_box_w = _BOX_WIDTH // 2
        half_box_h = _BOX_HEIGHT // 2
        box_rect = rect.adjusted(
            half_w - half_box_w, half_h - half_box_h,
            -(half_w - half_box_w), -(half_h - half_box_h),
        )

        pen = QPen(self._border_color)
        pen.setWidth(_BOX_BORDER_WIDTH)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setDashPattern(_BOX_DASH_PATTERN)

        painter.save()
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(box_rect, _BOX_RADIUS, _BOX_RADIUS)
        painter.restore()
