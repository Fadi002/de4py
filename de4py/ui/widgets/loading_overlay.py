# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from __future__ import annotations

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QTimer, QPoint, QRect, QPointF, QRectF
from PySide6.QtGui import QPainter, QColor, QConicalGradient, QBrush, QPen
from de4py.ui.widgets.glass_utils import GlassBlurCache
from de4py.ui.motion.spring import FramePacer, spring_gentle

_SPINNER_RADIUS = 22.0
_SPINNER_WIDTH = 3.5
_SPINNER_BOUNDS_MARGIN = 4.0
_SPRING_TICK_MS = 16
_BACKDROP_MAX_ALPHA = 200.0
_BACKDROP_TARGET_ALPHA = 160.0
_DEFAULT_BRAND_COLOR = QColor(2, 135, 207)
_OPACITY_SETTLE_EPS = 1.0 / 510.0
_BACKDROP_SETTLE_EPS = 0.5


class LoadingOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LoadingOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._angle = 0.0
        self._blurred_bg = None
        self._lock_events = False
        self._brand_color = QColor(_DEFAULT_BRAND_COLOR)
        self._spinner_pen = None
        self._spinner_head_color = None
        self._rebuild_spinner_paint_objects()

        self._dragging = False
        self._drag_pos = QPoint()

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_spring = spring_gentle()
        self._backdrop_spring = spring_gentle()
        self._backdrop_alpha = 0.0
        self._closing = False
        self._pacer = FramePacer()

        self._spin_timer = QTimer(self)
        self._spin_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._spin_timer.setInterval(_SPRING_TICK_MS)
        self._spin_timer.timeout.connect(self._tick)

        self._fade_timer = QTimer(self)
        self._fade_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._fade_timer.setInterval(_SPRING_TICK_MS)
        self._fade_timer.timeout.connect(self._tick_springs)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(60)

        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

    def set_status(self, text: str):
        self.status_label.setText(text)
        self.update()

    def setBrandColor(self, color: QColor):
        self._brand_color = QColor(color)
        self._rebuild_spinner_paint_objects()
        self.update()

    def _rebuild_spinner_paint_objects(self):
        gradient = QConicalGradient(0, 0, 0)
        color_head = QColor(self._brand_color)
        color_tail = QColor(self._brand_color)
        color_tail.setAlpha(0)

        gradient.setColorAt(0.0, color_head)
        gradient.setColorAt(0.75, color_tail)
        gradient.setColorAt(1.0, color_tail)

        pen = QPen(QBrush(gradient), _SPINNER_WIDTH)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        self._spinner_pen = pen
        self._spinner_head_color = color_head

    def _tick(self):
        self._angle = (self._angle + 6.0) % 360.0
        self.update(self._spinner_bounds())

    def _spinner_bounds(self) -> QRect:
        center = self.rect().center()
        radius = _SPINNER_RADIUS + _SPINNER_WIDTH + _SPINNER_BOUNDS_MARGIN
        side = int(radius * 2.0)
        return QRect(
            int(center.x() - radius), int(center.y() - radius), side, side
        )

    def _tick_springs(self):
        dt = self._pacer.tick()
        self._fade_spring.tick(dt)
        self._backdrop_spring.tick(dt)
        self._angle = (self._angle + 6.0) % 360.0

        self._opacity_effect.setOpacity(max(0.0, min(1.0, self._fade_spring.value)))
        self._backdrop_alpha = max(0.0, min(_BACKDROP_MAX_ALPHA, self._backdrop_spring.value))

        if self._fade_spring.is_settled(eps=_OPACITY_SETTLE_EPS) and \
                self._backdrop_spring.is_settled(eps=_BACKDROP_SETTLE_EPS):
            self._fade_timer.stop()
            if self._closing:
                self._closing = False
                self.setHidden(True)
                return
            self._opacity_effect.setEnabled(False)
            self._spin_timer.start()

        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._lock_events and self.parent():
            self.setGeometry(self.parent().rect())
            self._blurred_bg = self._create_blur_cache()
        self._spin_timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.parent():
            self.setGeometry(self.parent().rect())

    def hideEvent(self, event):
        super().hideEvent(event)
        self._spin_timer.stop()
        self._fade_timer.stop()
        if not self._lock_events:
            self._blurred_bg = None

    def fade_in(self):
        self._closing = False
        self._opacity_effect.setEnabled(True)
        self.setHidden(False)
        self._spin_timer.stop()
        self._fade_spring.value = self._opacity_effect.opacity()
        self._fade_spring.target = 1.0
        self._backdrop_spring.value = self._backdrop_alpha
        self._backdrop_spring.target = _BACKDROP_TARGET_ALPHA
        self._fade_timer.start()

    def fade_out(self):
        self._closing = True
        self._opacity_effect.setEnabled(True)
        self._spin_timer.stop()
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
                blur_radius=28, downsample_divisor=2, force_refresh=False,
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

        center = rect.center()
        painter.translate(center)
        painter.rotate(self._angle)

        painter.setPen(self._spinner_pen)

        r = _SPINNER_RADIUS
        painter.drawEllipse(QRectF(-r, -r, r * 2.0, r * 2.0))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._spinner_head_color)
        head_radius = _SPINNER_WIDTH / 2.0
        painter.drawEllipse(QPointF(r, 0), head_radius, head_radius)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_pos = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        event.accept()
