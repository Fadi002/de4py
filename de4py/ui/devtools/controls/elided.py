# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFontMetrics, QPainter
from PySide6.QtWidgets import QCheckBox, QLabel, QStyle, QStyleOptionButton

class ElidedLabel(QLabel):
    def minimumSizeHint(self):
        return QSize(8, self.fontMetrics().height())

    def paintEvent(self, event):
        painter = QPainter(self)
        metrics = QFontMetrics(self.font())
        elided = metrics.elidedText(self.text(), Qt.TextElideMode.ElideRight, self.width())
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)
        painter.end()

class ElidedCheckBox(QCheckBox):
    def minimumSizeHint(self):
        return QSize(28, self.fontMetrics().height() + 8)

    def paintEvent(self, event):
        painter = QPainter(self)
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        metrics = self.fontMetrics()
        available = self.width() - 24
        opt.text = metrics.elidedText(self.text(), Qt.TextElideMode.ElideRight, max(available, 4))
        self.style().drawControl(QStyle.ControlElement.CE_CheckBox, opt, painter, self)
        painter.end()