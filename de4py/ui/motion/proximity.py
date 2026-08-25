from __future__ import annotations

import math
import weakref
from PySide6.QtCore import QObject, QEvent, QPointF, QElapsedTimer
from PySide6.QtWidgets import QApplication, QWidget


class ProximityTracker(QObject):
    _instance: ProximityTracker | None = None
    INFLUENCE_RADIUS = 80
    INFLUENCE_RADIUS_SQ = INFLUENCE_RADIUS ** 2

    @classmethod
    def instance(cls) -> ProximityTracker:
        if cls._instance is None:
            app = QApplication.instance()
            if app:
                cls._instance = cls(app)
        return cls._instance

    def __init__(self, parent=None):
        super().__init__(parent)
        self._widgets = weakref.WeakSet()
        self._last_pos = QPointF(-9999, -9999)

        self._vel_timer = QElapsedTimer()
        self._vel_timer.start()

        if parent:
            parent.installEventFilter(self)

    def register(self, widget: QWidget):
        self._widgets.add(widget)

    def unregister(self, widget: QWidget):
        self._widgets.discard(widget)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseMove:
            pos = event.globalPosition()

            dt = self._vel_timer.restart() / 1000.0

            dx = pos.x() - self._last_pos.x()
            dy = pos.y() - self._last_pos.y()

            dist_sq = dx * dx + dy * dy
            velocity = math.sqrt(dist_sq) / max(dt, 0.001)

            threshold_sq = 36 if velocity > 1000 else 9

            if dist_sq > threshold_sq:
                self._last_pos = pos
                self._broadcast(pos)
        return False

    def _broadcast(self, gpos: QPointF):
        for widget in self._widgets:
            if not widget.isVisible():
                continue

            rect = widget.rect()
            try:
                local = widget.mapFromGlobal(gpos.toPoint())
            except RuntimeError:
                continue

            cx = max(rect.left(), min(local.x(), rect.right()))
            cy = max(rect.top(), min(local.y(), rect.bottom()))
            dx = local.x() - cx
            dy = local.y() - cy
            dist_sq = dx * dx + dy * dy

            if dist_sq > self.INFLUENCE_RADIUS_SQ:
                if hasattr(widget, 'on_proximity'):
                    try:
                        widget.on_proximity(0.0, QPointF(0, 0))
                    except RuntimeError:
                        pass
                continue

            if dist_sq == 0:
                proximity = 1.0
            else:
                proximity = max(0.0, 1.0 - math.sqrt(dist_sq) / self.INFLUENCE_RADIUS)

            center = rect.center()
            hw = max(1, rect.width() / 2)
            hh = max(1, rect.height() / 2)
            cursor_local = QPointF(
                max(-1.0, min(1.0, (local.x() - center.x()) / hw)),
                max(-1.0, min(1.0, (local.y() - center.y()) / hh)),
            )

            if hasattr(widget, 'on_proximity'):
                try:
                    widget.on_proximity(proximity, cursor_local)
                except RuntimeError:
                    pass


class SurfaceLinker:
    _instance: SurfaceLinker | None = None
    LINK_RADIUS = 120
    LINK_RADIUS_SQ = LINK_RADIUS ** 2
    LINK_STRENGTH = 0.15

    @classmethod
    def instance(cls) -> SurfaceLinker:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._widgets = weakref.WeakSet()

    def register(self, widget: QWidget):
        self._widgets.add(widget)

    def broadcast(self, source: QWidget, energy: float):
        if energy < 0.01:
            return
        try:
            sc = source.mapToGlobal(source.rect().center())
        except RuntimeError:
            return

        for widget in self._widgets:
            if widget is source or not widget.isVisible():
                continue

            try:
                target_center = widget.mapToGlobal(widget.rect().center())
            except RuntimeError:
                continue

            dx = sc.x() - target_center.x()
            dy = sc.y() - target_center.y()
            dist_sq = dx * dx + dy * dy

            if dist_sq < self.LINK_RADIUS_SQ:
                dist = math.sqrt(dist_sq)
                linked = energy * max(0.0, 1.0 - dist / self.LINK_RADIUS) * self.LINK_STRENGTH
                if hasattr(widget, 'on_linked_energy'):
                    try:
                        widget.on_linked_energy(linked)
                    except RuntimeError:
                        pass
