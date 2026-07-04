# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from __future__ import annotations

import os
import math
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QPoint, QRect, QRectF, Property
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QPainter, QColor, QPixmap, QPen
from de4py.ui.constants import NOTIF_WIDTH, NOTIF_DURATION, NOTIF_PROGRESS_DURATION
from de4py.ui.widgets.glass_utils import GlassBlurCache
from de4py.ui.motion.spring import FramePacer, spring_responsive
from de4py.ui.motion.material import MaterialPainter

_ICON_CACHE: dict[tuple[str, str], QPixmap] = {}
_WIDGET_DIR = os.path.dirname(os.path.abspath(__file__))
_RESOURCES_DIR = os.path.join(_WIDGET_DIR, "..", "resources")
_NOTIF_ICON_MAP: dict[str, str] = {
    "success": "check-circle.svg",
    "failure": "x-circle.svg",
    "warning": "alert-triangle.svg",
}


class NotificationWidget(QFrame):
    SLIDE_OFFSET = 50

    def __init__(self, notif_type: str, message: str, parent=None,
                 blur_pixmap=None, stack_depth: int = 0):
        super().__init__(parent)
        self.setObjectName("NotificationFrame")
        self.setFixedWidth(NOTIF_WIDTH)
        self._notif_type = notif_type
        self._progress_value = 100
        self._blur_pixmap = blur_pixmap
        self._clip_path = None
        self._icon_color = QColor("white")
        self.is_closing = False
        self._stack_depth = stack_depth

        self._border_color = QColor("#0287CF")
        self._border_width = 1.5
        self._corner_radius = 14
        self._overlay_color = QColor(25, 25, 25, 170)

        self._cached_pen: QPen | None = None

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        self._pos_spring_x = spring_responsive()
        self._pos_spring_y = spring_responsive()

        self._setup_ui(notif_type, message)

    def getOverlayColor(self) -> QColor:
        return self._overlay_color

    def getOverlayColorName(self) -> str:
        return self._overlay_color.name(QColor.HexArgb)

    def setOverlayColorName(self, color_str: str):
        if color_str:
            c = QColor(color_str)
            if c.isValid():
                self._overlay_color = c
                self.update()

    overlayColorName = Property(str, getOverlayColorName, setOverlayColorName)

    def getIconColorName(self) -> str:
        return self._icon_color.name(QColor.HexArgb)

    def setIconColorName(self, color_str: str):
        if color_str:
            c = QColor(color_str)
            if c.isValid():
                self._icon_color = c
                self._set_icon(self._notif_type)
                self.update()

    iconColorName = Property(str, getIconColorName, setIconColorName)

    def getBorderColor(self) -> QColor:
        return self._border_color

    def setBorderColor(self, color):
        if isinstance(color, QColor):
            self._border_color = color
        else:
            self._border_color = QColor(color)
        self._cached_pen = None
        self.update()

    borderColor = Property(QColor, getBorderColor, setBorderColor)

    def getBorderWidth(self) -> float:
        return float(self._border_width)

    def setBorderWidth(self, w):
        try:
            self._border_width = float(w)
        except Exception:
            self._border_width = 1.5
        self._cached_pen = None
        self.update()

    borderWidth = Property(float, getBorderWidth, setBorderWidth)

    def spring_move_to(self, x: float, y: float):
        self._pos_spring_x.target = x
        self._pos_spring_y.target = y

    def snap_position(self, x: float, y: float):
        self._pos_spring_x.value = x
        self._pos_spring_x.target = x
        self._pos_spring_x.velocity = 0
        self._pos_spring_y.value = y
        self._pos_spring_y.target = y
        self._pos_spring_y.velocity = 0
        self.move(int(x), int(y))

        from PySide6.QtGui import QPainterPath
        self._clip_path = QPainterPath()
        rect = self.rect()
        bw = float(self._border_width)
        inset = bw / 2.0
        overlay_rect = rect.adjusted(math.ceil(inset), math.ceil(inset),
                                     -math.ceil(inset), -math.ceil(inset))
        self._clip_path.addRoundedRect(overlay_rect, self._corner_radius, self._corner_radius)

    def tick_position(self, dt: float) -> bool:
        self._pos_spring_x.tick(dt)
        self._pos_spring_y.tick(dt)
        self.move(int(self._pos_spring_x.value), int(self._pos_spring_y.value))
        return not (self._pos_spring_x.is_settled() and self._pos_spring_y.is_settled())

    def paintEvent(self, event):
        NoPen = Qt.PenStyle.NoPen
        NoBrush = Qt.BrushStyle.NoBrush

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect = self.rect()
        bw = float(self._border_width)
        radius = float(self._corner_radius)

        inset = bw / 2.0
        overlay_rect = rect.adjusted(math.ceil(inset), math.ceil(inset),
                                     -math.ceil(inset), -math.ceil(inset))

        if self._blur_pixmap and not self._blur_pixmap.isNull() and self.parent():
            painter.save()
            if self._clip_path:
                painter.setClipPath(self._clip_path)
            global_pos = self.mapTo(self.parent(), QPoint(0, 0))
            src = QRect(global_pos, self.size())
            painter.drawPixmap(rect, self._blur_pixmap, src)
            painter.restore()

        depth_opacity = max(0.6, 1.0 - self._stack_depth * 0.12)

        overlay_color = self._overlay_color
        painter.setBrush(QColor(overlay_color.red(), overlay_color.green(), overlay_color.blue(),
                                int(overlay_color.alpha() * depth_opacity)))
        painter.setPen(NoPen)
        painter.drawRoundedRect(overlay_rect, radius, radius)

        if bw > 0:
            if self._cached_pen is None:
                pen = QPen(self._border_color)
                pen.setWidthF(bw)
                pen.setCosmetic(False)
                self._cached_pen = pen
            border_color = self._border_color
            cached = self._cached_pen
            cached.setColor(QColor(border_color.red(), border_color.green(), border_color.blue(),
                                   int(border_color.alpha() * depth_opacity)))
            painter.setPen(cached)
            painter.setBrush(NoBrush)
            painter.drawRoundedRect(overlay_rect, radius, radius)

        frect = QRectF(overlay_rect)
        MaterialPainter.paint_edge_sheen(painter, frect, 0.6 * depth_opacity, radius)

        if depth_opacity > 0.5:
            MaterialPainter.paint_thickness(painter, frect, 0.3 * depth_opacity)

        painter.end()

    def _setup_ui(self, notif_type: str, message: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
        self.setMinimumHeight(80)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(24, 24)
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        self._set_icon(notif_type)
        content_layout.addWidget(self.icon_label)

        self.message_label = QLabel(message)
        self.message_label.setWordWrap(True)
        self.message_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.message_label.setMinimumHeight(24)
        content_layout.addWidget(self.message_label, 1)

        layout.addLayout(content_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMinimumHeight(4)
        self.progress_bar.setMaximumHeight(4)
        self.progress_bar.setValue(100)
        self.progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.progress_bar)

        self._progress_timer = QTimer(self)
        self._progress_timer.timeout.connect(self._update_progress)
        self._progress_timer.start(NOTIF_PROGRESS_DURATION // 100)

    def _set_icon(self, notif_type: str):
        icon_file = _NOTIF_ICON_MAP.get(notif_type, "info.svg")
        icon_path = os.path.join(_RESOURCES_DIR, icon_file)
        cache_key = (icon_path, self._icon_color.name(QColor.HexArgb))

        cached = _ICON_CACHE.get(cache_key)
        if cached is not None and not cached.isNull():
            self.icon_label.setPixmap(cached)
            return

        if os.path.exists(icon_path):
            renderer = QSvgRenderer(icon_path)

            size = 48
            pix = QPixmap(size, size)
            pix.fill(Qt.GlobalColor.transparent)

            painter = QPainter(pix)
            renderer.render(painter)

            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(pix.rect(), self._icon_color)
            painter.end()

            final_pix = pix.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            _ICON_CACHE[cache_key] = final_pix
            self.icon_label.setPixmap(final_pix)

    def _update_progress(self):
        if self._progress_value > 0:
            self._progress_value -= 1
            self.progress_bar.setValue(self._progress_value)
        else:
            self._progress_timer.stop()


class NotificationManager(QWidget):
    MAX_NOTIFICATIONS = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self._notifications: list[NotificationWidget] = []
        self._blurred_bg = None
        self._tick_timer = QTimer(self)
        self._tick_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._tick_timer.setInterval(16)
        self._tick_timer.timeout.connect(self._tick_positions)

        if parent:
            self.setGeometry(0, 0, parent.width(), parent.height())
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.show()

    def _create_blur_cache(self):
        top_window = self.window()
        if not top_window:
            return None
        return GlassBlurCache.capture(top_window, blur_radius=26, downsample_divisor=2)

    def show_notification(self, notif_type: str, message: str):
        parent_widget = self.parent() or self

        if not self._notifications:
            self._blurred_bg = self._create_blur_cache()

        if len(self._notifications) >= self.MAX_NOTIFICATIONS:
            oldest = self._notifications.pop(-1)
            self._slide_out(oldest)

        notif = NotificationWidget(
            notif_type, message, parent_widget,
            self._blurred_bg, stack_depth=0,
        )
        self._notifications.insert(0, notif)
        notif.show()
        notif.raise_()

        x_start = parent_widget.width() + NotificationWidget.SLIDE_OFFSET
        x_end = parent_widget.width() - NOTIF_WIDTH - 20
        y = 20
        notif.snap_position(x_start, y)
        notif.spring_move_to(x_end, y)

        self._restack_notifications()
        self._ensure_tick_running()

        try:
            from de4py.ui.motion.proximity import SurfaceLinker
            SurfaceLinker.instance().broadcast(notif, 0.5)
        except Exception:
            pass

        QTimer.singleShot(NOTIF_DURATION, lambda n=notif: self._slide_out(n))

    def _slide_out(self, notif: NotificationWidget):
        try:
            if not notif or notif.is_closing:
                return
            notif.is_closing = True
        except RuntimeError:
            return

        parent = self.parent() or self
        x_end = parent.width() + NotificationWidget.SLIDE_OFFSET
        notif.spring_move_to(x_end, notif.y())
        self._ensure_tick_running()

        QTimer.singleShot(500, lambda: self._cleanup_notif(notif))

    def _cleanup_notif(self, notif: NotificationWidget):
        try:
            if notif in self._notifications:
                self._notifications.remove(notif)
            notif.deleteLater()
        except RuntimeError:
            pass
        self._restack_notifications()
        if not self._notifications:
            self._blurred_bg = None

    def _restack_notifications(self):
        parent_widget = self.parent() or self
        y = 20
        for index, notification in enumerate(self._notifications):
            if notification.is_closing:
                continue
            notification._stack_depth = index
            x = parent_widget.width() - NOTIF_WIDTH - 20
            notification.spring_move_to(x, y)
            y += notification.height() + 10
        self._ensure_tick_running()

    def _tick_positions(self):
        dt = FramePacer.instance().tick()
        any_active = False
        for notification in self._notifications:
            try:
                if notification.tick_position(dt):
                    any_active = True
            except RuntimeError:
                pass
        if not any_active:
            self._tick_timer.stop()

    def _ensure_tick_running(self):
        if not self._tick_timer.isActive():
            self._tick_timer.start()
