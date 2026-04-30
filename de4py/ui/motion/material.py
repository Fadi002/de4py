from __future__ import annotations

import math
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QPainter, QColor, QLinearGradient, QRadialGradient, QPen, QPainterPath
)

from de4py.ui.motion.spring import DampedSpring, spring_responsive, spring_gentle


_wake_cb = None


def set_wake_callback(cb):
    global _wake_cb
    _wake_cb = cb


def _wake():
    if _wake_cb:
        _wake_cb()


class MaterialState:
    __slots__ = (
        'widget', 'hover', 'press', 'focus', 'proximity',
        'active', 'linked_energy', '_memory', '_memory_decay',
        '_cursor_local', '_dirty', '_on_tick',
    )

    def __init__(self, widget=None, on_tick=None):
        self.widget = widget
        self._on_tick = on_tick
        self.hover = spring_responsive()
        self.press = spring_responsive()
        self.focus = spring_gentle()
        self.proximity = spring_gentle()
        self.active = spring_gentle()
        self.linked_energy = DampedSpring(200, 30, 1.0)
        self._memory = 0.0
        self._memory_decay = 0.92
        self._cursor_local = QPointF(0, 0)
        self._dirty = False

    def drive(self, channel: str, target: float, velocity_boost: float = 0.0):
        spring: DampedSpring = getattr(self, channel)
        spring.target = target
        if velocity_boost:
            spring.velocity += velocity_boost
        if target > 0 and channel in ('hover', 'press', 'focus'):
            self._memory = max(self._memory, target)
        self._dirty = True
        _wake()

    def tick(self, dt: float) -> bool:
        any_active = False
        for ch in ('hover', 'press', 'focus', 'proximity', 'active', 'linked_energy'):
            s: DampedSpring = getattr(self, ch)
            s.tick(dt)
            if not s.is_settled():
                any_active = True

        if self._memory > 0.001:
            self._memory *= self._memory_decay
            any_active = True
        else:
            self._memory = 0.0

        self._dirty = any_active

        if any_active and self._on_tick:
            self._on_tick()

        return any_active

    @property
    def depth(self) -> float:
        return max(
            self.hover.value * 0.6,
            self.focus.value * 0.8,
            self.press.value * 0.3,
            self.active.value * 0.7,
            self.proximity.value * 0.25,
            self.linked_energy.value * 0.1,
            self._memory * 0.15,
        )

    @property
    def surface_opacity(self) -> float:
        return min(1.0, 0.75 + self.depth * 0.25)

    @property
    def shadow_blur(self) -> float:
        return self.depth * 24.0

    @property
    def shadow_offset(self) -> float:
        return 1.0 + self.depth * 4.0

    @property
    def shadow_alpha(self) -> float:
        return self.depth * 0.35

    @property
    def specular_intensity(self) -> float:
        return self.proximity.value * 0.08 + self.hover.value * 0.04

    @property
    def bloom_radius(self) -> float:
        return self.focus.value * 6.0

    @property
    def glow_intensity(self) -> float:
        return (
            self.hover.value * 0.6
            + self.proximity.value * 0.3
            + self.linked_energy.value * 0.1
            + self._memory * 0.2
        )

    @property
    def scale(self) -> float:
        return 1.0 - self.press.value * 0.018

    def is_active(self) -> bool:
        return self._dirty


class MaterialPainter:

    @staticmethod
    def paint_thickness(painter: QPainter, rect: QRectF, depth: float):
        if depth < 0.05:
            return
        painter.save()
        painter.setPen(Qt.NoPen)
        edge_alpha = int(min(30, 12 * depth))
        r = max(rect.width(), rect.height()) * 0.7
        grad = QRadialGradient(rect.center().x(), rect.center().y(), r)
        grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        grad.setColorAt(0.82, QColor(0, 0, 0, 0))
        grad.setColorAt(1.0, QColor(0, 0, 0, edge_alpha))
        painter.setBrush(grad)
        painter.drawRoundedRect(rect, 14, 14)

        refract_alpha = int(min(10, 3 * depth))
        if refract_alpha > 0:
            shifted = rect.adjusted(1.5, 1.5, -0.5, -0.5)
            g2 = QLinearGradient(shifted.topLeft(), shifted.bottomRight())
            g2.setColorAt(0.0, QColor(255, 255, 255, refract_alpha))
            g2.setColorAt(0.5, QColor(255, 255, 255, 0))
            g2.setColorAt(1.0, QColor(200, 220, 255, refract_alpha // 2))
            painter.setBrush(g2)
            painter.drawRoundedRect(shifted, 13, 13)

        painter.restore()

    @staticmethod
    def paint_specular(painter: QPainter, rect: QRectF,
                       cursor_local: QPointF, intensity: float):
        if intensity < 0.01:
            return
        painter.save()
        painter.setPen(Qt.NoPen)
        cx = rect.center().x() + cursor_local.x() * rect.width() * 0.2
        cy = rect.center().y() + cursor_local.y() * rect.height() * 0.2
        radius = min(rect.width(), rect.height()) * 0.4
        alpha = int(min(35, 20 * intensity))
        grad = QRadialGradient(cx, cy, max(1.0, radius))
        grad.setColorAt(0.0, QColor(255, 255, 255, alpha))
        grad.setColorAt(0.45, QColor(255, 255, 255, alpha // 3))
        grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setBrush(grad)
        painter.drawRoundedRect(rect, 14, 14)

        streak_alpha = int(min(15, 8 * intensity))
        if streak_alpha > 1:
            angle = math.atan2(cursor_local.y(), max(0.001, cursor_local.x()))
            sx = rect.center().x() + math.cos(angle) * rect.width() * 0.25
            sy = rect.center().y() + math.sin(angle) * rect.height() * 0.15
            sg = QRadialGradient(sx, sy, radius * 0.3)
            sg.setColorAt(0.0, QColor(255, 255, 255, streak_alpha))
            sg.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setBrush(sg)
            painter.drawRoundedRect(rect, 14, 14)

        painter.restore()

    @staticmethod
    def paint_edge_sheen(painter: QPainter, rect: QRectF, proximity: float,
                         corner_radius: float = 14.0):
        if proximity < 0.05:
            return
        painter.save()
        alpha = int(min(25, 18 * proximity))
        pen = QPen(QColor(255, 255, 255, alpha), 1.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        inset = corner_radius + 2
        painter.drawLine(
            int(rect.left() + inset), int(rect.top() + 1),
            int(rect.right() - inset), int(rect.top() + 1),
        )

        side_alpha = alpha // 2
        if side_alpha > 1:
            pen2 = QPen(QColor(255, 255, 255, side_alpha), 1.0)
            painter.setPen(pen2)
            painter.drawLine(
                int(rect.left() + 1), int(rect.top() + inset),
                int(rect.left() + 1), int(rect.bottom() - inset),
            )
        painter.restore()

    @staticmethod
    def paint_bloom(painter: QPainter, rect: QRectF,
                    bloom_radius: float, color: QColor | None = None):
        if bloom_radius < 0.5:
            return
        if color is None:
            color = QColor(88, 166, 255)
        painter.save()
        painter.setPen(Qt.NoPen)
        alpha = int(min(25, bloom_radius * 4))
        r = max(rect.width(), rect.height()) * 0.6
        grad = QRadialGradient(rect.center().x(), rect.center().y(), max(1.0, r))
        grad.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), alpha))
        grad.setColorAt(0.55, QColor(color.red(), color.green(), color.blue(), alpha // 3))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(grad)
        painter.drawRoundedRect(rect, 14, 14)
        painter.restore()

    @staticmethod
    def paint_depth_tint(painter: QPainter, rect: QRectF, depth: float):
        if depth < 0.08:
            return
        painter.save()
        painter.setPen(Qt.NoPen)
        alpha = int(min(12, 6 * depth))
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        grad.setColorAt(0.7, QColor(0, 0, 0, 0))
        grad.setColorAt(1.0, QColor(10, 15, 30, alpha))
        painter.setBrush(grad)
        painter.drawRoundedRect(rect, 14, 14)
        painter.restore()
