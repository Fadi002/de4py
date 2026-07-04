# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from __future__ import annotations

from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt, QPoint, QPointF, Property, QRectF
from PySide6.QtGui import (
    QPainter, QColor, QIcon, QRadialGradient, QBrush, QPixmap
)

from de4py.ui.motion.material import MaterialState
from de4py.ui.motion.spring import InertiaChain


_HAMBURGER_ICON_CACHE: dict[tuple[int, int, str], QPixmap] = {}


class HamburgerButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(50, 50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._scale_factor = 1.0
        self._hover_progress = 0.0
        self._icon = QIcon()
        self._icon_color_name = ""

        self._bg_color = QColor(255, 255, 255, 10)
        self._hover_color = QColor(255, 255, 255, 25)

        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

        self._cursor_local = QPointF(0, 0)
        self._material = MaterialState(self, on_tick=self._sync_material)

        from de4py.ui.motion.manager import MotionManager
        MotionManager.register_material(self, self._material)

        try:
            from de4py.ui.motion.proximity import ProximityTracker, SurfaceLinker
            pt = ProximityTracker.instance()
            if pt:
                pt.register(self)
            sl = SurfaceLinker.instance()
            if sl:
                sl.register(self)
        except Exception:
            pass

    def _sync_material(self):
        m = self._material
        self._scale_factor = m.scale
        self._hover_progress = m.glow_intensity

    def on_proximity(self, proximity: float, cursor_local: QPointF):
        self._material.proximity.target = proximity
        self._material._cursor_local = cursor_local
        self._cursor_local = cursor_local

    def on_linked_energy(self, energy: float):
        self._material.linked_energy.target = max(
            self._material.linked_energy.target, energy
        )

    def setIcon(self, icon: QIcon):
        self._icon = icon
        self.update()

    def getIconColorName(self) -> str:
        return self._icon_color_name

    def setIconColorName(self, color_name: str):
        self._icon_color_name = color_name
        self.update()

    iconColorName = Property(str, getIconColorName, setIconColorName)

    def get_scale_factor(self):
        return self._scale_factor

    def set_scale_factor(self, factor):
        self._scale_factor = factor
        self.update()

    scale_factor = Property(float, get_scale_factor, set_scale_factor)

    def get_hover_progress(self):
        return self._hover_progress

    def set_hover_progress(self, progress):
        self._hover_progress = progress
        self.update()

    hover_progress = Property(float, get_hover_progress, set_hover_progress)

    def enterEvent(self, event):
        self._material.drive('hover', 1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._material.drive('hover', 0.0)
        super().leaveEvent(event)

    def focusInEvent(self, event):
        self._material.drive('focus', 1.0)
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        if not self.underMouse():
            self._material.drive('focus', 0.0)
        super().focusOutEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._material.drive('press', 1.0)
            InertiaChain.instance().push(1.2)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._material.drive('press', 0.0)
        super().mouseReleaseEvent(event)

    def hitButton(self, pos: QPoint) -> bool:
        center = self.rect().center()
        radius = self.width() / 2
        dx = pos.x() - center.x()
        dy = pos.y() - center.y()
        return dx * dx + dy * dy <= radius * radius

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        center = rect.center()
        radius = min(rect.width(), rect.height()) / 2.0

        painter.translate(center)
        painter.scale(self._scale_factor, self._scale_factor)
        painter.translate(-center)

        m = self._material
        hp = max(0.0, min(1.0, m.glow_intensity))

        bg = QColor(self._bg_color)
        tgt = QColor(self._hover_color)
        r = bg.red() + (tgt.red() - bg.red()) * hp
        g = bg.green() + (tgt.green() - bg.green()) * hp
        b = bg.blue() + (tgt.blue() - bg.blue()) * hp
        a = bg.alpha() + (tgt.alpha() - bg.alpha()) * hp

        final_bg = QColor(int(r), int(g), int(b), int(a))
        painter.setBrush(QBrush(final_bg))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(rect)

        if hp > 0.08:
            glow = QRadialGradient(center, radius)
            glow.setColorAt(0.82, QColor(255, 255, 255, 0))
            glow.setColorAt(1.0, QColor(255, 255, 255, int(18 * hp)))
            painter.setBrush(QBrush(glow))
            painter.drawEllipse(rect)

        if m.specular_intensity > 0.01:
            sx = center.x() + self._cursor_local.x() * radius * 0.3
            sy = center.y() + self._cursor_local.y() * radius * 0.3
            sg = QRadialGradient(sx, sy, radius * 0.5)
            sa = int(min(20, 14 * m.specular_intensity))
            sg.setColorAt(0.0, QColor(255, 255, 255, sa))
            sg.setColorAt(0.6, QColor(255, 255, 255, sa // 3))
            sg.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setBrush(QBrush(sg))
            painter.drawEllipse(rect)

        if m.press.value > 0.05:
            pa = int(min(20, 12 * m.press.value))
            ig = QRadialGradient(center, radius)
            ig.setColorAt(0.0, QColor(0, 0, 0, 0))
            ig.setColorAt(0.7, QColor(0, 0, 0, 0))
            ig.setColorAt(1.0, QColor(0, 0, 0, pa))
            painter.setBrush(QBrush(ig))
            painter.drawEllipse(rect)

        if not self._icon.isNull():
            icon_size = 24
            final_icon_color = QColor(255, 255, 255)
            if self._icon_color_name:
                icon_color = QColor(self._icon_color_name)
                if icon_color.isValid():
                    final_icon_color = icon_color

            cache_key = (int(self._icon.cacheKey()), icon_size, final_icon_color.name(QColor.HexArgb))
            colored_pix = _HAMBURGER_ICON_CACHE.get(cache_key)
            if colored_pix is None or colored_pix.isNull():
                pix = self._icon.pixmap(icon_size, icon_size)
                if pix.isNull():
                    return

                colored_pix = QPixmap(pix.size())
                colored_pix.fill(Qt.GlobalColor.transparent)
                p = QPainter(colored_pix)
                p.drawPixmap(0, 0, pix)
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                p.fillRect(colored_pix.rect(), final_icon_color)
                p.end()
                _HAMBURGER_ICON_CACHE[cache_key] = colored_pix

            if not colored_pix.isNull():
                x = center.x() - icon_size / 2
                y = center.y() - icon_size / 2
                painter.drawPixmap(int(x), int(y), colored_pix)
