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
    QPushButton, QGraphicsDropShadowEffect, QStackedWidget,
    QWidget, QGraphicsOpacityEffect, QCheckBox
)
from PySide6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, Property,
    QParallelAnimationGroup, QSize, QPoint, QPointF,
    QRectF, Signal
)
from PySide6.QtGui import QColor, QCursor, QPainter, QBrush, QPen, QIcon, QPixmap

from de4py.utils import sentry
from de4py.ui.motion.material import MaterialState, MaterialPainter
from de4py.ui.motion.spring import InertiaChain, spring_responsive, spring_settle


class AnimatedButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._shadow_active_color = QColor(0, 255, 34, 80)

        self._base_icon = QIcon()
        self._icon_color_name = ""

        self._scale = 1.0
        self._hover_progress = 0.0

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(0)
        self._shadow.setOffset(0, 2)
        self._shadow.setColor(QColor(0, 0, 0, 0))
        self.setGraphicsEffect(self._shadow)

        self._material = MaterialState(self, on_tick=self._sync_material)
        self._cursor_local = QPointF(0, 0)

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
        self._scale = m.scale
        self._hover_progress = m.hover.value

        c = self._shadow_active_color
        glow = m.glow_intensity
        if glow > 0.01:
            self._shadow.setBlurRadius(m.shadow_blur)
            self._shadow.setOffset(0, m.shadow_offset)
            self._shadow.setColor(QColor(
                c.red(), c.green(), c.blue(),
                int(c.alpha() * min(1.0, m.shadow_alpha + glow * 0.3))
            ))
        else:
            self._shadow.setBlurRadius(0)
            self._shadow.setOffset(0, 2)
            self._shadow.setColor(QColor(0, 0, 0, 0))

    def on_proximity(self, proximity: float, cursor_local: QPointF):
        self._material.proximity.target = proximity
        self._material._cursor_local = cursor_local
        self._cursor_local = cursor_local

    def on_linked_energy(self, energy: float):
        self._material.linked_energy.target = max(
            self._material.linked_energy.target, energy
        )

    @Property(float)
    def scale_factor(self):
        return self._scale

    @scale_factor.setter
    def scale_factor(self, value):
        self._scale = value
        self.update()

    @Property(float)
    def hover_progress(self):
        return self._hover_progress

    @hover_progress.setter
    def hover_progress(self, value):
        self._hover_progress = value
        self.update()

    @Property(QColor)
    def shadow_active_color(self):
        return self._shadow_active_color

    @shadow_active_color.setter
    def shadow_active_color(self, color):
        self._shadow_active_color = color

    def setIcon(self, icon):
        self._base_icon = icon
        self._update_icon_color()

    def _update_icon_color(self):
        if not self._base_icon or self._base_icon.isNull():
            super().setIcon(QIcon())
            return

        if not self._icon_color_name:
            super().setIcon(self._base_icon)
            return

        c = QColor(self._icon_color_name)
        if not c.isValid():
            super().setIcon(self._base_icon)
            return

        size = self.iconSize()
        if size.isEmpty():
            size = QSize(24, 24)

        pix = self._base_icon.pixmap(size)
        if pix.isNull():
            super().setIcon(self._base_icon)
            return

        tinter = QPainter(pix)
        tinter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        tinter.fillRect(pix.rect(), c)
        tinter.end()

        super().setIcon(QIcon(pix))

    def getIconColorName(self) -> str:
        return self._icon_color_name

    def setIconColorName(self, color_name: str):
        self._icon_color_name = color_name
        self._update_icon_color()

    iconColorName = Property(str, getIconColorName, setIconColorName)

    def enterEvent(self, event):
        self._material.drive('hover', 1.0)
        from de4py.ui.motion.proximity import SurfaceLinker
        try:
            SurfaceLinker.instance().broadcast(self, 0.8)
        except Exception:
            pass
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
        self._material.drive('press', 1.0)
        InertiaChain.instance().push(1.0)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._material.drive('press', 0.0)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        rect = self.rect()
        center = rect.center()
        painter.translate(center)
        painter.scale(self._scale, self._scale)
        painter.translate(-center)

        from PySide6.QtWidgets import QStyleOptionButton, QStyle
        opt = QStyleOptionButton()
        self.initStyleOption(opt)

        if self.isDown():
            opt.state |= QStyle.State_Sunken
        else:
            opt.state &= ~QStyle.State_Sunken

        self.style().drawControl(QStyle.ControlElement.CE_PushButton, opt, painter, self)

        m = self._material
        frect = QRectF(rect)

        if m.specular_intensity > 0.01:
            MaterialPainter.paint_specular(painter, frect, self._cursor_local, m.specular_intensity)

        if m.bloom_radius > 0.5:
            MaterialPainter.paint_bloom(painter, frect, m.bloom_radius)


class AnimatedToggle(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._position = 0.0
        self._track_color_on = QColor(0, 255, 34)
        self._track_color_off = QColor(60, 60, 60)
        self._knob_color = QColor(255, 255, 255)

        self._spring = spring_settle()
        self._material = MaterialState(self, on_tick=self._sync_spring)

        from de4py.ui.motion.manager import MotionManager
        MotionManager.register_material(self, self._material)

        self.stateChanged.connect(self._handle_state_change)

    def _sync_spring(self):
        self._spring.tick(0.016)
        self._position = max(0.0, min(1.0, self._spring.value))

    @Property(float)
    def position(self):
        return self._position

    @position.setter
    def position(self, pos):
        self._position = pos
        self.update()

    def _handle_state_change(self, state):
        self._spring.target = 1.0 if state == 2 else 0.0
        self._material._dirty = True
        from de4py.ui.motion.manager import MotionManager
        MotionManager.wake()

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        rect = self.rect()
        h = rect.height()
        w = rect.width()

        track_radius = h / 2
        painter.setPen(Qt.PenStyle.NoPen)

        r = self._track_color_off.red() + (self._track_color_on.red() - self._track_color_off.red()) * self._position
        g = self._track_color_off.green() + (self._track_color_on.green() - self._track_color_off.green()) * self._position
        b = self._track_color_off.blue() + (self._track_color_on.blue() - self._track_color_off.blue()) * self._position
        track_color = QColor(int(r), int(g), int(b))

        painter.setBrush(track_color)
        painter.drawRoundedRect(rect, track_radius, track_radius)

        knob_margin = 4
        knob_size = h - (knob_margin * 2)
        knob_x_start = knob_margin
        knob_x_end = w - knob_margin - knob_size

        current_knob_x = knob_x_start + (knob_x_end - knob_x_start) * self._position

        knob_rect = QRectF(current_knob_x, knob_margin, knob_size, knob_size)
        painter.setBrush(self._knob_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(knob_rect, knob_size/2, knob_size/2)


class AnimatedCheckBox(QCheckBox):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._check_progress = 0.0
        self._hover_progress = 0.0

        self._active_color = QColor(0, 255, 34)
        self._border_color = QColor(100, 100, 100)
        self._bg_color = QColor(30, 30, 30)

        self._spring = spring_settle()
        self._material = MaterialState(self, on_tick=self._sync_spring)

        from de4py.ui.motion.manager import MotionManager
        MotionManager.register_material(self, self._material)

    def _sync_spring(self):
        self._spring.tick(0.016)
        self._check_progress = max(0.0, min(1.0, self._spring.value))

    @Property(float)
    def check_progress(self):
        return self._check_progress

    @check_progress.setter
    def check_progress(self, val):
        self._check_progress = val
        self.update()

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def checkStateSet(self):
        super().checkStateSet()
        self._spring.target = 1.0 if self.isChecked() else 0.0
        self._material._dirty = True
        from de4py.ui.motion.manager import MotionManager
        MotionManager.wake()

    def nextCheckState(self):
        super().nextCheckState()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        font_metrics = painter.fontMetrics()
        text_height = font_metrics.height()

        rect = self.rect()
        box_size = 18
        box_y = (rect.height() - box_size) / 2
        box_rect = QRectF(0, box_y, box_size, box_size)

        painter.setPen(QPen(self._border_color if self._check_progress < 0.5 else self._active_color, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self._check_progress > 0:
             painter.setBrush(QColor(self._active_color.red(), self._active_color.green(), self._active_color.blue(), int(255 * self._check_progress)))
             painter.setPen(Qt.PenStyle.NoPen)
             painter.drawRoundedRect(box_rect, 4, 4)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(self._border_color if self._check_progress < 0.5 else self._active_color, 2))
        painter.drawRoundedRect(box_rect, 4, 4)

        if self._check_progress > 0.1:
            painter.save()
            painter.translate(box_size / 2, box_y + box_size / 2)
            painter.scale(self._check_progress, self._check_progress)
            painter.translate(-box_size / 2, -box_size / 2)

            pen = QPen(QColor(0, 0, 0) if self._active_color.lightness() > 150 else QColor(255, 255, 255), 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)

            painter.drawLine(4, 9, 7, 12)
            painter.drawLine(7, 12, 14, 5)
            painter.restore()

        if self.text():
             text_rect = QRectF(box_size + 8, 0, rect.width() - box_size - 8, rect.height())
             painter.setPen(self.palette().text().color())
             painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())


class AnimatedStackedWidget(QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._anim_group = None
        self._is_animating = False
        self._pending_index = None

    def fade_to_index(self, index):
        if index == self.currentIndex():
            return

        if self._is_animating:
            if self._anim_group:
                self._anim_group.stop()
            self._is_animating = False

        current_widget = self.currentWidget()
        next_widget = self.widget(index)

        if not current_widget or not next_widget:
            self.setCurrentIndex(index)
            return

        with sentry.span("ui.transition", description=f"Index {self.currentIndex()} → {index}"):
            next_widget.setVisible(True)

            current_effect = QGraphicsOpacityEffect(current_widget)
            next_effect = QGraphicsOpacityEffect(next_widget)
            current_widget.setGraphicsEffect(current_effect)
            next_widget.setGraphicsEffect(next_effect)

            next_effect.setOpacity(0)

            self._anim_group = QParallelAnimationGroup(self)

            inherited_v = InertiaChain.instance().pop(0.4)
            dur = max(160, int(250 - abs(inherited_v) * 40))

            anim_out = QPropertyAnimation(current_effect, b"opacity")
            anim_out.setDuration(dur)
            anim_out.setStartValue(1)
            anim_out.setEndValue(0)
            anim_out.setEasingCurve(QEasingCurve.Type.InQuad)

            anim_in = QPropertyAnimation(next_effect, b"opacity")
            anim_in.setDuration(dur)
            anim_in.setStartValue(0)
            anim_in.setEndValue(1)
            anim_in.setEasingCurve(QEasingCurve.Type.OutCubic)

            self._anim_group.addAnimation(anim_out)
            self._anim_group.addAnimation(anim_in)

            def on_finished():
                self.setCurrentIndex(index)
                current_widget.setGraphicsEffect(None)
                next_widget.setGraphicsEffect(None)
                current_widget.setVisible(False)
                self._is_animating = False

            self._anim_group.finished.connect(on_finished)
            self._is_animating = True
            self._anim_group.start()
