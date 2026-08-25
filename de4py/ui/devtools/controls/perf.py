from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QTableWidget, QTableWidgetItem, QHeaderView,
                              QSlider, QCheckBox, QSizePolicy)

from .elided import ElidedCheckBox

from de4py.lang import tr, keys
from de4py.ui.constants import COLOR_ACCENT
from ..context import context
from ..metrics.paintrate import paint_rate
from ..metrics.repaint import repaint_tracker

try:
    import shiboken6 as shiboken
except ImportError:
    try:
        import shiboken
    except ImportError:
        shiboken = None

class Sparkline(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(48)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#1c1c1c"))

        samples = list(paint_rate.samples)
        if not samples:
            return

        w = self.width()
        h = self.height()
        max_v = max(samples) or 1
        step = w / len(samples)

        points = []
        for i, value in enumerate(samples):
            x = i * step + step / 2
            y = h - (value / max_v) * (h - 6) - 3
            points.append((x, y))

        painter.setPen(QPen(QColor(COLOR_ACCENT), 2))
        for i in range(1, len(points)):
            painter.drawLine(int(points[i - 1][0]), int(points[i - 1][1]),
                             int(points[i][0]), int(points[i][1]))

class PerfTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

        self._table_timer = QTimer(self)
        self._table_timer.timeout.connect(self.refresh_table)
        self._table_timer.start(1000)

    def _shrinkable(self, widget):
        widget.setMinimumWidth(0)
        policy = widget.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
        widget.setSizePolicy(policy)

    def _shrinkable_label(self, widget):
        widget.setMinimumWidth(0)
        policy = widget.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Policy.Preferred)
        widget.setSizePolicy(policy)

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)

        meter_row = QHBoxLayout()
        self.rate_label = QLabel("0")
        self.rate_label.setObjectName("DevRateValue")
        self.rate_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._shrinkable_label(self.rate_label)
        meter_row.addWidget(self.rate_label, 0)
        self.sparkline = Sparkline()
        meter_row.addWidget(self.sparkline, 1)
        self.layout.addLayout(meter_row)

        anim_row = QHBoxLayout()
        self.anim_label = QLabel(tr(keys.DEV_PERF_ANIM_SPEED))
        self._shrinkable_label(self.anim_label)
        anim_row.addWidget(self.anim_label)
        self.anim_slider = QSlider(Qt.Orientation.Horizontal)
        self.anim_slider.setRange(1, 50)
        self.anim_slider.setSingleStep(1)
        self.anim_slider.setPageStep(5)
        self.anim_slider.setValue(int(context.dev_flags.get("anim_speed", 1.0) * 10))
        self.anim_slider.valueChanged.connect(self.update_anim_speed)
        self.anim_val_label = QLabel(self._speed_text(self.anim_slider.value()))
        self.anim_val_label.setFixedWidth(56)
        anim_row.addWidget(self.anim_slider, 1)
        anim_row.addWidget(self.anim_val_label, 0)
        self.layout.addLayout(anim_row)

        region_row = QHBoxLayout()
        self.regions_check = ElidedCheckBox(tr(keys.DEV_PERF_SHOW_REGIONS))
        self._shrinkable_label(self.regions_check)
        self.regions_check.toggled.connect(self.set_show_regions)
        region_row.addWidget(self.regions_check)
        self.layout.addLayout(region_row)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([
            tr(keys.DEV_PERF_HEADER_WIDGET),
            tr(keys.DEV_PERF_HEADER_COUNT),
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.layout.addWidget(self.table, 1)

    @staticmethod
    def _speed_text(value):
        return f"{value / 10.0:.1f}x"

    def _is_alive(self, widget):
        if not widget:
            return False
        if shiboken:
            return shiboken.isValid(widget)
        try:
            widget.parent()
            return True
        except Exception:
            return False

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_table()

    def refresh_table(self):
        if not self.isVisible():
            return
        self.rate_label.setText(str(paint_rate.rate))
        self.sparkline.update()

        top = repaint_tracker.top(5)
        rows = []
        for widget, count in top:
            if not self._is_alive(widget):
                continue
            rows.append((widget.metaObject().className(), widget.objectName() or "-", count))

        self.table.setRowCount(len(rows))
        for row, (cls, name, count) in enumerate(rows):
            for col, text in enumerate((f"{cls} | {name}", str(count))):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, col, item)

    def update_anim_speed(self, value):
        speed = value / 10.0
        context.dev_flags["anim_speed"] = speed
        self.anim_val_label.setText(self._speed_text(value))

    def set_show_regions(self, enabled):
        context.dev_flags["repaint_regions"] = enabled
        if not enabled:
            overlay = getattr(context, "overlay", None)
            if overlay:
                overlay.clear_repaint_regions()

    def retranslate_ui(self):
        self.anim_label.setText(tr(keys.DEV_PERF_ANIM_SPEED))
        self.regions_check.setText(tr(keys.DEV_PERF_SHOW_REGIONS))
        self.table.setHorizontalHeaderLabels([
            tr(keys.DEV_PERF_HEADER_WIDGET),
            tr(keys.DEV_PERF_HEADER_COUNT),
        ])
