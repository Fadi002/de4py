# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from __future__ import annotations

import math
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QTimer, QElapsedTimer
from PySide6.QtGui import QPainter, QColor, QPixmap
from de4py.ui.widgets.glass_utils import GlassBlurCache
from de4py.ui.motion.spring import spring_gentle


class LoadingOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LoadingOverlay")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._blurred_bg = None
        self._lock_events = False
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_spring = spring_gentle()
        self._backdrop_spring = spring_gentle()
        self._backdrop_alpha = 0.0
        self._closing = False

        self._elapsed = QElapsedTimer()
        self._elapsed.start()

        self._fade_timer = QTimer(self)
        self._fade_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._fade_timer.setInterval(16)
        self._fade_timer.timeout.connect(self._tick_springs)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(100)

        self.status_label = QLabel("")
        self.status_label.setObjectName("SubtitleLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: white; font-weight: bold; font-size: 18px;")
        layout.addWidget(self.status_label)

    def set_status(self, text: str):
        self.status_label.setText(text)
        self.update()

    def _tick_springs(self):
        dt = 0.016
        self._fade_spring.tick(dt)
        self._backdrop_spring.tick(dt)

        self._opacity_effect.setOpacity(max(0.0, min(1.0, self._fade_spring.value)))
        self._backdrop_alpha = max(0.0, min(200.0, self._backdrop_spring.value))

        if self._fade_spring.is_settled() and self._backdrop_spring.is_settled():
            self._fade_timer.stop()
            if self._closing:
                self._closing = False
                self.setHidden(True)

        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._lock_events and self.parent():
            self.setGeometry(self.parent().rect())
            self._blurred_bg = self._create_blur_cache()
        self._timer.start(16)

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()
        if not self._lock_events:
            self._blurred_bg = None

    def fade_in(self):
        self._closing = False
        self.setHidden(False)
        self._fade_spring.value = self._opacity_effect.opacity()
        self._fade_spring.target = 1.0
        self._backdrop_spring.value = self._backdrop_alpha
        self._backdrop_spring.target = 160.0
        self._fade_timer.start()

    def fade_out(self):
        self._closing = True
        self._fade_spring.value = self._opacity_effect.opacity()
        self._fade_spring.target = 0.0
        self._backdrop_spring.value = self._backdrop_alpha
        self._backdrop_spring.target = 0.0
        self._fade_timer.start()

    def _rotate(self):
        self._angle = (self._angle + 6) % 360
        self.update()

    def _create_blur_cache(self):
        top_window = self.window()
        if not top_window or self._lock_events:
            return None
        self._lock_events = True
        try:
            return GlassBlurCache.capture(
                top_window, exclude_widget=self,
                blur_radius=28, downsample_divisor=2, force_refresh=True,
            )
        finally:
            self._lock_events = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        rect = self.rect()

        if self._blurred_bg:
            painter.drawPixmap(rect, self._blurred_bg)

        painter.fillRect(rect, QColor(0, 0, 0, int(self._backdrop_alpha)))

        center = rect.center()
        radius = 25

        elapsed_s = self._elapsed.elapsed() / 1000.0
        glow_pulse = 0.15 + 0.15 * math.sin(elapsed_s * 5.0)

        painter.save()
        painter.translate(center)

        from PySide6.QtGui import QRadialGradient
        glow_alpha = int(255 * glow_pulse)
        glow = QRadialGradient(0, 0, radius * 2.5)
        glow.setColorAt(0.0, QColor(2, 135, 207, glow_alpha))
        glow.setColorAt(0.4, QColor(2, 135, 207, glow_alpha // 3))
        glow.setColorAt(1.0, QColor(2, 135, 207, 0))
        painter.setBrush(glow)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(-radius * 2, -radius * 2, radius * 4, radius * 4)

        painter.rotate(self._angle)

        for i in range(10, 0, -1):
            alpha = int((10 - i) * 5)
            pen = painter.pen()
            pen.setWidthF(2 + i)
            pen.setColor(QColor(2, 135, 207, alpha))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawArc(-radius, -radius, radius*2, radius*2, 0*16, 270*16)

        pen = painter.pen()
        pen.setWidthF(4)
        pen.setColor(QColor(2, 135, 207))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(-radius, -radius, radius*2, radius*2, 0*16, 270*16)

        pen.setColor(QColor(255, 255, 255))
        painter.setPen(pen)
        painter.drawArc(-radius, -radius, radius*2, radius*2, 270*16, 90*16)

        painter.restore()
        painter.end()
