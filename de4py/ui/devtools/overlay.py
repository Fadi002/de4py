import time

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget, QApplication

from de4py.ui.constants import COLOR_ACCENT, qcolor_rgba

_AMBER = "#ffb020"
_REGION_LIFETIME = 0.3

class DebugOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.show_boundaries = False
        self.show_highlight = False
        self.show_inspector = False

        self.highlight_rect = None
        self.inspect_rect = None

        self._repaint_regions = []
        self._dirty = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_overlay)
        self.timer.start(16)

    def _is_alive(self):
        try:
            self.isVisible()
            return True
        except RuntimeError:
            return False

    def set_highlight_mode(self, on):
        if not self._is_alive():
            return
        self.show_highlight = bool(on)
        self._dirty = True

    def set_inspect_mode(self, on):
        if not self._is_alive():
            return
        self.show_inspector = bool(on)
        self._dirty = True

    def set_highlight(self, rect):
        if not self._is_alive():
            return
        self.highlight_rect = rect
        self._dirty = True

    def clear_highlight(self):
        self.highlight_rect = None
        self._dirty = True

    def set_inspect_rect(self, rect):
        if not self._is_alive():
            return
        self.inspect_rect = rect
        self._dirty = True

    def clear_inspect_rect(self):
        self.inspect_rect = None
        self._dirty = True

    def set_repaint_region(self, rect):
        self._repaint_regions.append((rect, time.time()))

    def clear_repaint_regions(self):
        self._repaint_regions = []
        self._dirty = True

    def update_overlay(self):
        if not self._is_alive():
            return

        now = time.time()
        self._repaint_regions = [(r, t) for r, t in self._repaint_regions
                                 if now - t < _REGION_LIFETIME]

        has_content = any([
            self.show_boundaries,
            self.show_highlight,
            self.show_inspector,
            self._repaint_regions,
        ])
        if not has_content:
            if self.isVisible():
                self.hide()
            return

        if not self.isVisible():
            self.show()
            self.raise_()

        main_win = self.parentWidget() or QApplication.activeWindow()
        if main_win:
            self.setGeometry(main_win.rect())
            if self._dirty or self._repaint_regions:
                self.repaint()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        if self.show_boundaries:
            self._draw_boundaries(painter)

        if self.show_highlight or self.show_inspector:
            self._draw_highlights(painter)

        if self._repaint_regions:
            self._draw_repaint_regions(painter)
        self._dirty = False

    def _draw_repaint_regions(self, painter):
        for rect, _t in self._repaint_regions:
            x, y, w, h = rect
            painter.fillRect(x, y, w, h, qcolor_rgba(_AMBER + "22"))
            painter.setPen(QPen(qcolor_rgba(_AMBER + "88"), 1))
            painter.drawRect(x, y, w, h)

    def _draw_highlights(self, painter):
        if self.show_highlight and self.highlight_rect:
            x, y, w, h = self.highlight_rect
            painter.setPen(QPen(qcolor_rgba(COLOR_ACCENT + "88"), 4))
            painter.drawRect(x - 2, y - 2, w + 4, h + 4)
            painter.setPen(QPen(qcolor_rgba(COLOR_ACCENT), 2))
            painter.drawRect(x, y, w, h)
            painter.fillRect(x, y, w, h, qcolor_rgba(COLOR_ACCENT + "22"))

        if self.show_inspector and self.inspect_rect:
            x, y, w, h = self.inspect_rect
            painter.setPen(QPen(qcolor_rgba(_AMBER + "55"), 4))
            painter.drawRect(x - 2, y - 2, w + 4, h + 4)
            painter.setPen(QPen(qcolor_rgba(_AMBER), 2, Qt.PenStyle.DashLine))
            painter.drawRect(x, y, w, h)
            painter.fillRect(x, y, w, h, qcolor_rgba(_AMBER + "33"))

    def _draw_boundaries(self, painter):
        main_win = self.parentWidget() or QApplication.activeWindow()
        if not main_win:
            return
        painter.setPen(QPen(qcolor_rgba(COLOR_ACCENT + "55"), 1))
        for w in main_win.findChildren(QWidget):
            if not w.isVisible():
                continue
            try:
                pos = w.mapTo(main_win, QPoint(0, 0))
            except RuntimeError:
                continue
            painter.drawRect(pos.x(), pos.y(), w.width(), w.height())
