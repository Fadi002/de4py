from __future__ import annotations

import weakref
from PySide6.QtCore import QObject, QEvent, QPointF
from PySide6.QtWidgets import QApplication, QWidget


class ProximityTracker(QObject):
    _instance: ProximityTracker | None = None
    INFLUENCE_RADIUS = 80

    @classmethod
    def instance(cls) -> ProximityTracker:
        if cls._instance is None:
            app = QApplication.instance()
            if app:
                cls._instance = cls(app)
        return cls._instance

    def __init__(self, parent=None):
        super().__init__(parent)
        self._widgets: list[weakref.ref] = []
        self._last_pos = QPointF(-9999, -9999)
        if parent:
            parent.installEventFilter(self)

    def register(self, widget: QWidget):
        for ref in self._widgets:
            if ref() is widget:
                return
        self._widgets.append(weakref.ref(widget))

    def unregister(self, widget: QWidget):
        self._widgets = [r for r in self._widgets if r() is not None and r() is not widget]

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseMove:
            pos = event.globalPosition()
            
            # Adaptive threshold calculation based on time
            from PySide6.QtCore import QElapsedTimer
            if not hasattr(self, '_vel_timer'):
                self._vel_timer = QElapsedTimer()
                self._vel_timer.start()
            
            dt = self._vel_timer.elapsed() / 1000.0
            self._vel_timer.restart()
            
            dx = pos.x() - self._last_pos.x()
            dy = pos.y() - self._last_pos.y()
            
            velocity = (dx * dx + dy * dy) ** 0.5 / max(dt, 0.001)
            
            # Fast movement -> higher threshold (skip frames for stability)
            # Slow movement -> lower threshold (capture fine details)
            threshold_sq = 36 if velocity > 1000 else 9
            
            if dx * dx + dy * dy > threshold_sq:
                self._last_pos = pos
                self._broadcast(pos)
        return False

    def _broadcast(self, gpos: QPointF):
        alive = []
        for ref in self._widgets:
            w = ref()
            if w is None:
                continue
            alive.append(ref)
            if not w.isVisible():
                continue

            rect = w.rect()
            try:
                local = w.mapFromGlobal(gpos.toPoint())
            except RuntimeError:
                continue

            cx = max(rect.left(), min(local.x(), rect.right()))
            cy = max(rect.top(), min(local.y(), rect.bottom()))
            dx = local.x() - cx
            dy = local.y() - cy
            dist = (dx * dx + dy * dy) ** 0.5

            proximity = max(0.0, min(1.0, 1.0 - dist / self.INFLUENCE_RADIUS))

            center = rect.center()
            hw = max(1, rect.width() / 2)
            hh = max(1, rect.height() / 2)
            cursor_local = QPointF(
                max(-1.0, min(1.0, (local.x() - center.x()) / hw)),
                max(-1.0, min(1.0, (local.y() - center.y()) / hh)),
            )

            if hasattr(w, 'on_proximity'):
                try:
                    w.on_proximity(proximity, cursor_local)
                except RuntimeError:
                    pass

        self._widgets = alive


class SurfaceLinker:
    _instance: SurfaceLinker | None = None
    LINK_RADIUS = 120
    LINK_STRENGTH = 0.15

    @classmethod
    def instance(cls) -> SurfaceLinker:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._widgets: list[weakref.ref] = []

    def register(self, widget: QWidget):
        for ref in self._widgets:
            if ref() is widget:
                return
        self._widgets.append(weakref.ref(widget))

    def broadcast(self, source: QWidget, energy: float):
        if energy < 0.01:
            return
        try:
            sc = source.mapToGlobal(source.rect().center())
        except RuntimeError:
            return

        alive = []
        for ref in self._widgets:
            w = ref()
            if w is None or w is source:
                continue
            alive.append(ref)
            if not w.isVisible():
                continue
            try:
                tc = w.mapToGlobal(w.rect().center())
            except RuntimeError:
                continue
            dx = sc.x() - tc.x()
            dy = sc.y() - tc.y()
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < self.LINK_RADIUS:
                linked = energy * max(0.0, 1.0 - dist / self.LINK_RADIUS) * self.LINK_STRENGTH
                if hasattr(w, 'on_linked_energy'):
                    try:
                        w.on_linked_energy(linked)
                    except RuntimeError:
                        pass
        self._widgets = alive
