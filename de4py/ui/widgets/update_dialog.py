# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import os
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QTextBrowser, QSizePolicy,
    QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, Signal, QRectF, QTimer, QSize
from PySide6.QtGui import QPainter, QColor, QIcon, QPixmap
from PySide6.QtSvg import QSvgRenderer

from de4py.ui.widgets.glass_utils import GlassBlurCache
from de4py.ui.motion.spring import spring_gentle, spring_settle, InertiaChain
from de4py.ui.motion.material import MaterialPainter

_RESOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resources")


class UpdateDialog(QWidget):
    update_confirmed = Signal()
    install_confirmed = Signal()
    dismissed = Signal()

    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.result = result
        self._lock_events = False
        self._blurred_bg = None
        self._setup_ui()
        self._show_available()

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_spring = spring_gentle()
        self._scale_spring = spring_settle(0.94)
        self._translate_spring = spring_settle(20.0)
        self._backdrop_spring = spring_gentle()
        self._backdrop_alpha = 100.0
        self._opening = False
        self._closing = False

        self._anim_timer = QTimer(self)
        self._anim_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._tick_anim)

    def _tick_anim(self):
        dt = 0.016
        self._fade_spring.tick(dt)
        self._scale_spring.tick(dt)
        self._translate_spring.tick(dt)
        self._backdrop_spring.tick(dt)

        self._opacity_effect.setOpacity(max(0.0, min(1.0, self._fade_spring.value)))
        self._backdrop_alpha = max(0.0, min(200.0, self._backdrop_spring.value))

        all_settled = (
            self._fade_spring.is_settled()
            and self._scale_spring.is_settled()
            and self._translate_spring.is_settled()
            and self._backdrop_spring.is_settled()
        )

        if all_settled:
            self._anim_timer.stop()
            if self._closing:
                self._closing = False
                self.setHidden(True)

        self.update()

    def _setup_ui(self):
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addStretch(1)

        self.modal_frame = QFrame()
        self.modal_frame.setObjectName("StyledFrame")
        self.modal_frame.setFixedWidth(480)
        self.modal_frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        frame_layout = QVBoxLayout(self.modal_frame)
        frame_layout.setContentsMargins(20, 15, 20, 15)
        frame_layout.setSpacing(10)

        header_layout = QHBoxLayout()
        self.title = QLabel("Update Available")
        self.title.setObjectName("SubtitleLabel")
        header_layout.addWidget(self.title)
        header_layout.addStretch()

        close_btn = QPushButton()
        close_btn.setObjectName("CloseButton")
        close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(self._on_close)

        icon_path = os.path.join(_RESOURCES_DIR, "x.svg")
        if os.path.exists(icon_path):
            renderer = QSvgRenderer(icon_path)
            pix = QPixmap(16, 16)
            pix.fill(Qt.GlobalColor.transparent)
            p = QPainter(pix)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            renderer.render(p)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            p.fillRect(pix.rect(), QColor(255, 255, 255, 180))
            p.end()
            close_btn.setIcon(QIcon(pix))
            close_btn.setIconSize(QSize(16, 16))

        header_layout.addWidget(close_btn)
        frame_layout.addLayout(header_layout)

        self.version_label = QLabel()
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(self.version_label)

        self.changelog_view = QTextBrowser()
        self.changelog_view.setOpenExternalLinks(True)
        self.changelog_view.setMaximumHeight(200)
        frame_layout.addWidget(self.changelog_view)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("UpdateProgressBar")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        frame_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(self.status_label)

        btn_layout = QHBoxLayout()
        self.btn_dismiss = QPushButton("Later")
        self.btn_dismiss.clicked.connect(self._on_dismiss)
        btn_layout.addWidget(self.btn_dismiss)

        self.btn_primary = QPushButton("Update Now")
        self.btn_primary.setObjectName("PrimaryButton")
        self.btn_primary.clicked.connect(self._on_primary)
        btn_layout.addWidget(self.btn_primary)
        frame_layout.addLayout(btn_layout)

        layout.addWidget(self.modal_frame, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

    def _show_available(self):
        self.version_label.setText(
            f"{self.result.local}  →  <b>{self.result.remote}</b>"
        )
        html = ""
        for entry in self.result.changelog:
            html += f"<h3>v{entry['version']}</h3><ul>"
            for ch in entry.get('changes', []):
                html += f"<li>{ch}</li>"
            html += "</ul>"
        self.changelog_view.setHtml(html or "<p>No changelog available.</p>")
        self.btn_primary.setText("Update Now")

    def show_downloading(self):
        self.progress_bar.show()
        self.progress_bar.setRange(0, 0)
        self.status_label.setText("Downloading...")
        self.btn_primary.setEnabled(False)
        self.btn_dismiss.setEnabled(False)

    def set_download_progress(self, pct: int):
        if self.progress_bar.maximum() == 0:
            self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(pct)
        self.status_label.setText(f"Downloading... {pct}%")

    def show_ready(self):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.status_label.setText("Download complete. Ready to install.")
        self.btn_primary.setText("Install & Restart")
        self.btn_primary.setEnabled(True)
        self.btn_dismiss.setEnabled(True)

    def show_error(self, msg: str):
        self.status_label.setText(f"Error: {msg}")
        self.btn_primary.setText("Retry")
        self.btn_primary.setEnabled(True)
        self.btn_dismiss.setEnabled(True)

    def _on_primary(self):
        text = self.btn_primary.text()
        if text == "Update Now" or text == "Retry":
            self.show_downloading()
            self.update_confirmed.emit()
        elif text == "Install & Restart":
            self.install_confirmed.emit()

    def _on_dismiss(self):
        self.fade_out()
        self.dismissed.emit()

    def _on_close(self):
        self.fade_out()
        self.dismissed.emit()

    def fade_in(self):
        self._closing = False
        self._opening = True
        self.setHidden(False)
        self.raise_()

        inherited_v = InertiaChain.instance().pop(0.5)

        self._fade_spring.value = self._opacity_effect.opacity()
        self._fade_spring.target = 1.0
        self._fade_spring.velocity = inherited_v * 2.0

        self._scale_spring.value = 0.94
        self._scale_spring.target = 1.0
        self._scale_spring.velocity = inherited_v

        self._translate_spring.value = 20.0
        self._translate_spring.target = 0.0
        self._translate_spring.velocity = -inherited_v * 10.0

        self._backdrop_spring.value = 100.0
        self._backdrop_spring.target = 160.0

        if not self._anim_timer.isActive():
            self._anim_timer.start()

    def fade_out(self):
        self._opening = False
        self._closing = True

        self._fade_spring.value = self._opacity_effect.opacity()
        self._fade_spring.target = 0.0

        self._scale_spring.value = max(0.94, min(1.0, self._scale_spring.value))
        self._scale_spring.target = 0.97

        self._translate_spring.target = 8.0

        self._backdrop_spring.value = self._backdrop_alpha
        self._backdrop_spring.target = 0.0

        if not self._anim_timer.isActive():
            self._anim_timer.start()

    def _create_blur_cache(self):
        top_window = self.window()
        if not top_window or self._lock_events:
            return None
        self._lock_events = True
        try:
            return GlassBlurCache.capture(
                top_window, exclude_widget=self,
                blur_radius=28, downsample_divisor=2, force_refresh=False,
            )
        finally:
            self._lock_events = False

    def showEvent(self, event):
        super().showEvent(event)
        if not self._lock_events and self.parent():
            self.setGeometry(self.parent().rect())
            self._blurred_bg = self._create_blur_cache()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.parent():
            self.setGeometry(self.parent().rect())

    def hideEvent(self, event):
        super().hideEvent(event)
        if not self._lock_events:
            self._blurred_bg = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        if self._blurred_bg:
            painter.drawPixmap(self.rect(), self._blurred_bg)

        painter.fillRect(self.rect(), QColor(0, 0, 0, int(self._backdrop_alpha)))

        scale = max(0.9, min(1.05, self._scale_spring.value))
        ty = self._translate_spring.value
        depth = max(0.0, 1.0 - scale) * 5.0

        if self.modal_frame and (abs(scale - 1.0) > 0.001 or abs(ty) > 0.5):
            frame_rect = self.modal_frame.geometry()
            center = frame_rect.center()
            painter.save()
            painter.translate(center)
            painter.scale(scale, scale)
            painter.translate(-center.x(), -center.y() + ty)
            painter.restore()

        frect = QRectF(self.modal_frame.geometry())
        if depth > 0.1:
            MaterialPainter.paint_edge_sheen(painter, frect, min(1.0, depth * 0.5))

        painter.end()
