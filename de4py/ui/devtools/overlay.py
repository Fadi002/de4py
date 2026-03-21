# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QTimer, QRect, QPoint
from PySide6.QtGui import QPainter, QColor, QPen
from de4py.lang import tr, keys

class DebugOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.show_boundaries = False
        self.show_highlight = False
        self.show_inspector = False
        self.show_fps = False
        
        self.highlight_rect = None # (x, y, w, h)
        self.inspect_rect = None   # (x, y, w, h)
        
        self._repaint_regions = []  # List of (rect, time)
        
        import time
        self._last_fps_time = time.time()
        self._frame_count = 0
        self._current_fps = 0
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_overlay)
        self.timer.start(16)

    def update_overlay(self):
        if not any([self.show_boundaries, self.show_highlight, self.show_inspector, self.show_fps, self._repaint_regions]):
            return
            
        import time
        now = time.time()
        self._repaint_regions = [(r, t) for r, t in self._repaint_regions if now - t < 0.3]
        
        main_win = self.parentWidget() or QApplication.activeWindow()
        if main_win:
            self.setGeometry(main_win.rect())
            self.repaint()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.show_boundaries:
            self._draw_boundaries(painter)
            
        if self.show_highlight or self.show_inspector:
            self._draw_highlights(painter)

        if self.show_fps:
            self._draw_fps(painter)

    def _draw_fps(self, painter):
        import time
        now = time.time()
        self._frame_count += 1
        
        elapsed = now - self._last_fps_time
        if elapsed >= 0.05:
            self._current_fps = int(self._frame_count / elapsed)
            self._last_fps_time = now
            self._frame_count = 0

        fps_text = tr(keys.DEV_UI_FPS_LABEL).format(fps=self._current_fps)
        width = 65
        height = 24
        x = self.width() - width - 10
        y = 35
        
        # Background
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 180))
        painter.drawRoundedRect(x, y, width, height, 4, 4)
        
        if self._current_fps >= 55:
            color = QColor(0, 255, 0)
        elif self._current_fps >= 30:
            color = QColor(255, 200, 0)
        else:
            color = QColor(255, 50, 50)
            
        painter.setPen(color)
        from PySide6.QtGui import QFont
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(QRect(x, y, width, height), Qt.AlignmentFlag.AlignCenter, fps_text)

    def _draw_highlights(self, painter):
        if self.show_highlight and self.highlight_rect:
            x, y, w, h = self.highlight_rect
            painter.setPen(QPen(QColor(0, 255, 255, 50), 4))
            painter.drawRect(x-2, y-2, w+4, h+4)
            painter.setPen(QPen(QColor(0, 255, 255, 220), 2))
            painter.drawRect(x, y, w, h)
            painter.fillRect(x, y, w, h, QColor(0, 255, 255, 20))

        if self.show_inspector and self.inspect_rect:
            x, y, w, h = self.inspect_rect
            painter.setPen(QPen(QColor(255, 255, 0, 60), 4))
            painter.drawRect(x-2, y-2, w+4, h+4)
            painter.setPen(QPen(QColor(255, 255, 0, 255), 2, Qt.PenStyle.DashLine))
            painter.drawRect(x, y, w, h)
            painter.fillRect(x, y, w, h, QColor(255, 255, 0, 30))

    def _draw_boundaries(self, painter):
        main_win = QApplication.activeWindow()
        if not main_win: return
        
        pen = QPen(QColor(0, 255, 255, 100), 1)
        painter.setPen(pen)
        
        widgets = main_win.findChildren(QWidget)
        for w in widgets:
            if w.isVisible():
                pos = w.mapTo(main_win, QPoint(0, 0))
                painter.drawRect(pos.x(), pos.y(), w.width(), w.height())

    def _draw_repaints(self, painter):
        import time
        now = time.time()
        for rect, timestamp in self._repaint_regions:
            alpha = int(255 * (1.0 - (now - timestamp) / 0.3))
            painter.fillRect(rect, QColor(255, 0, 0, alpha))

    def add_repaint(self, rect):
        import time
        self._repaint_regions.append((rect, time.time()))
