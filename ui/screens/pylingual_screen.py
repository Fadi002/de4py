"""
De4py PyLingual Screen
"""

import os
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QSplitter, QApplication, QTextBrowser, QFileDialog,
    QGraphicsBlurEffect, QGraphicsScene, QGraphicsPixmapItem, 
    QGraphicsOpacityEffect, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QTextEdit, QCheckBox, QScrollArea, QFrame,
    QProgressBar,
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize, Signal, QRectF, Property
from PySide6.QtGui import QColor, QPainter, QPixmap

from ui.workers.pylingual_worker import PyLingualWorker


@dataclass
class TOSConfig:
    title: str = "PyLingual Terms of Service"
    acceptance_text: str = "I have read and accept the PyLingual privacy TOS"
    tos_content: str = (
        "By using this service, you accept the PyLingual privacy TOS:\n\n"
        "Files and patches submitted to the PyLingual web service are retained to support "
        "future research and development.\n\n"
        "By using this service, you warrant that you are not violating export control laws, "
        "intellectual property rights, licenses, or other legal or contractual obligations, "
        "and that you are not using this service for improper, unauthorized, or malicious purposes. "
        "Proprietary files uploaded to PyLingual may be disclosed to relevant third parties."
    )


class TOSDialog(QWidget):
    accepted = Signal()
    rejected = Signal()

    def __init__(self, config: TOSConfig = TOSConfig(), parent=None):
        super().__init__(parent)
        self.config = config
        self.setObjectName("TOSOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        
        self._blurred_bg = None
        self._lock_events = False
        self._setup_ui()
        self._setup_animation()

    def _setup_ui(self):
        # Full-sized overlay layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addStretch(1)

        # Centered modal frame
        self.modal_frame = QFrame()
        self.modal_frame.setObjectName("StyledFrame")
        self.modal_frame.setFixedSize(500, 400)
        
        frame_layout = QVBoxLayout(self.modal_frame)
        frame_layout.setContentsMargins(20, 20, 20, 20)
        frame_layout.setSpacing(15)

        # Title
        title_label = QLabel(self.config.title)
        title_label.setObjectName("TitleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(title_label)

        # Scrollable TOS Text Area
        self.tos_browser = QTextBrowser()
        self.tos_browser.setObjectName("ChangelogContent") 
        self.tos_browser.setText(self.config.tos_content)
        frame_layout.addWidget(self.tos_browser)

        # Checkbox for acceptance
        self.accept_checkbox = QCheckBox(self.config.acceptance_text)
        self.accept_checkbox.stateChanged.connect(self._toggle_accept_btn)
        frame_layout.addWidget(self.accept_checkbox)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setMinimumHeight(35)
        self.cancel_btn.clicked.connect(self._on_reject)
        
        self.accept_btn = QPushButton("I Accept")
        self.accept_btn.setMinimumHeight(35)
        self.accept_btn.setEnabled(False)
        self.accept_btn.clicked.connect(self._on_accept)
        
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.accept_btn)
        frame_layout.addLayout(btn_layout)

        main_layout.addWidget(self.modal_frame, alignment=Qt.AlignmentFlag.AlignCenter)
        main_layout.addStretch(1)

    def _setup_animation(self):
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.anim = QPropertyAnimation(self.effect, b"opacity")
        self.anim.setDuration(300)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def fade_in(self):
        self.show()
        self.anim.setStartValue(0)
        self.anim.setEndValue(1)
        self.anim.start()

    def fade_out(self):
        self.anim.setStartValue(1)
        self.anim.setEndValue(0)
        self.anim.finished.connect(self.hide)
        self.anim.start()

    def _on_accept(self):
        self.accepted.emit()
        self.fade_out()

    def _on_reject(self):
        self.rejected.emit()
        self.fade_out()

    def _toggle_accept_btn(self, state):
        self.accept_btn.setEnabled(state == Qt.CheckState.Checked.value)

    def _create_blur_cache(self):
        top_window = self.window()
        if not top_window or self._lock_events:
            return None
        
        self._lock_events = True
        super().hide()
        
        screen = top_window.screen()
        if not screen:
            screen = QApplication.primaryScreen()
            
        snapshot = screen.grabWindow(
            top_window.winId(),
            0, 0, top_window.width(), top_window.height()
        )
        
        super().show()
        self._lock_events = False
        
        blur_effect = QGraphicsBlurEffect()
        blur_effect.setBlurRadius(25) 
        
        scene = QGraphicsScene()
        item = QGraphicsPixmapItem(snapshot)
        item.setGraphicsEffect(blur_effect)
        scene.addItem(item)
        
        blurred_pixmap = QPixmap(snapshot.size())
        blurred_pixmap.fill(Qt.transparent)
        
        painter = QPainter(blurred_pixmap)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        scene.render(painter, QRectF(blurred_pixmap.rect()), QRectF(snapshot.rect()))
        painter.end()
        
        return blurred_pixmap

    def showEvent(self, event):
        super().showEvent(event)
        if not self._lock_events and self.parent():
            self.setGeometry(self.parent().rect())
            self._blurred_bg = self._create_blur_cache()

    def hideEvent(self, event):
        super().hideEvent(event)
        if not self._lock_events:
            self._blurred_bg = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if self._blurred_bg:
            painter.drawPixmap(self.rect(), self._blurred_bg)
            
        painter.fillRect(self.rect(), QColor(0, 0, 0, 160))
        painter.end()


class ModernToggle(QWidget):
    toggled = Signal(bool)

    def __init__(self, parent=None, active_color="#0287CF"):
        super().__init__(parent)
        self.setFixedSize(50, 26)
        self._active_color = active_color
        self._checked = False
        self._thumb_pos = 3
        
        self._anim = QPropertyAnimation(self, b"thumb_pos")
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def get_thumb_pos(self):
        return self._thumb_pos

    def set_thumb_pos(self, pos):
        self._thumb_pos = pos
        self.update()

    thumb_pos = Property(int, get_thumb_pos, set_thumb_pos)

    def is_checked(self):
        return self._checked

    def set_checked(self, checked):
        if self._checked == checked:
            return
        self._checked = checked
        self._anim.setStartValue(self._thumb_pos)
        self._anim.setEndValue(27 if checked else 3)
        self._anim.start()
        self.toggled.emit(checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_checked(not self._checked)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background
        color = QColor(self._active_color) if self._checked else QColor("#333333")
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 13, 13)
        
        # Draw thumb
        painter.setBrush(QColor("white"))
        painter.drawEllipse(self._thumb_pos, 3, 20, 20)
        painter.end()


class PyLingualScreen(QWidget):
    """
    PyLingual screen for decompiling .pyc files.
    
    Supports two modes:
    - Offline (Local): Uses local decompilation (placeholder)
    - Online (Server): Uses PyLingual API for decompilation
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._consent_accepted = False
        self._test_mode = False 
        self._file_selected = False
        self._selected_file_path = None
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        # Root layout for the screen
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(40, 20, 40, 20)
        root_layout.setSpacing(20)

        # Title Header
        title = QLabel("PYLINGUAL")
        title.setObjectName("TitleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root_layout.addWidget(title)

        # Mode Selection with Toggle
        mode_frame = QFrame()
        mode_frame.setObjectName("ModeSelectorFrame") 
        mode_frame.setFixedHeight(60)
        
        mode_layout = QHBoxLayout(mode_frame)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(15)
        
        self.offline_label = QLabel("Offline (Local)")
        self.offline_label.setObjectName("ModeLabel")
        self.offline_label.setProperty("active", True)
        self.offline_label.setFixedHeight(26)
        self.offline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.mode_toggle = ModernToggle()
        self.mode_toggle.toggled.connect(self._on_mode_toggled)
        
        self.online_label = QLabel("Online (Server)")
        self.online_label.setObjectName("ModeLabel")
        self.online_label.setProperty("active", False)
        self.online_label.setFixedHeight(26)
        self.online_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Absolute centering using stretches and centered widget alignment
        mode_layout.addStretch()
        mode_layout.addWidget(self.offline_label, 0, Qt.AlignmentFlag.AlignCenter)
        mode_layout.addWidget(self.mode_toggle, 0, Qt.AlignmentFlag.AlignCenter)
        mode_layout.addWidget(self.online_label, 0, Qt.AlignmentFlag.AlignCenter)
        mode_layout.addStretch()
        
        root_layout.addWidget(mode_frame)

        # Main Content Area
        self.content_container = QFrame()
        self.content_container.setObjectName("StyledFrame")
        root_layout.addWidget(self.content_container, 1)
        
        content_layout = QVBoxLayout(self.content_container)
        content_layout.setSpacing(20)

        # Actions Row
        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(15)
        
        self.select_btn = QPushButton("Select File")
        self.select_btn.setToolTip("Select a Python file for processing.")
        self.select_btn.setFixedHeight(45)
        self.select_btn.clicked.connect(self._on_select_file_clicked)
        actions_layout.addWidget(self.select_btn, 1)

        self.execute_btn = QPushButton("Execute")
        self.execute_btn.setToolTip("Start the decompilation process.")
        self.execute_btn.setFixedHeight(45)
        self.execute_btn.setEnabled(False)  # Wait for file selection
        self.execute_btn.clicked.connect(self._on_execute_clicked)
        actions_layout.addWidget(self.execute_btn, 1)
        
        self.copy_btn = QPushButton("Copy Result")
        self.copy_btn.setToolTip("Copy decompiled output to clipboard.")
        self.copy_btn.setFixedHeight(45)
        self.copy_btn.setFixedWidth(140)
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        actions_layout.addWidget(self.copy_btn)
        
        content_layout.addLayout(actions_layout)

        # Progress Section (hidden by default)
        self.progress_frame = QFrame()
        self.progress_frame.setVisible(False)
        progress_layout = QVBoxLayout(self.progress_frame)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(8)
        
        self.progress_label = QLabel("")
        self.progress_label.setObjectName("SubtitleLabel")
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setFixedHeight(22)
        
        # Apply premium styling to ensure text is visible and bar looks modern
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(2, 135, 207, 0.3);
                border-radius: 11px;
                text-align: center;
                color: #ffffff;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #0287CF, stop:1 #58a6ff);
                border-radius: 10px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        
        content_layout.addWidget(self.progress_frame)

        # Result Area
        result_title = QLabel("Decompiled Result")
        result_title.setObjectName("SubtitleLabel")
        content_layout.addWidget(result_title)
        
        self.result_area = QTextEdit()
        self.result_area.setPlaceholderText("Decompiled result will appear here...")
        self.result_area.setReadOnly(True)
        content_layout.addWidget(self.result_area)

    def _on_mode_toggled(self, checked):
        # Update dynamic properties for QSS
        self.online_label.setProperty("active", checked)
        self.offline_label.setProperty("active", not checked)
        
        # Refresh styling
        for label in [self.online_label, self.offline_label]:
            label.style().unpolish(label)
            label.style().polish(label)

        if checked:
            if not self._consent_accepted:
                self._check_consent()
        else:
            self.content_container.setEnabled(True)

    def _on_select_file_clicked(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select Python File",
            "",
            "Python Files (*.py *.pyc *.pyo);;All Files (*)"
        )
        
        if filename:
            self._selected_file_path = filename
            self._file_selected = True
            self.execute_btn.setEnabled(True)
            
            # Show only the basename for a cleaner look
            basename = os.path.basename(filename)
            self.result_area.setPlaceholderText(f"File '{basename}' selected. Click Execute to start.")
            
            if hasattr(self.window(), "show_notification"):
                self.window().show_notification("success", f"Selected: {basename}")

    def _on_execute_clicked(self):
        if not self._file_selected:
            return

        elif self.mode_toggle.is_checked():
            # Online mode - use PyLingual API
            self._execute_online()
        else:
            # Offline mode - local decompilation (placeholder)
            self._execute_offline()

    def _execute_online(self):
        """Execute decompilation using PyLingual API."""
        if self._worker is not None and self._worker.isRunning():
            return
        
        # Reset UI
        self.result_area.clear()
        self._show_progress(True)
        self._set_controls_enabled(False)
        
        # Create and start worker
        self._worker = PyLingualWorker(self._selected_file_path)
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.cached.connect(self._on_worker_cached)
        self._worker.start()

    def _execute_offline(self):
        """Execute local decompilation (placeholder for future implementation)."""
        main_win = self.window()
        if hasattr(main_win, "show_notification"):
            main_win.show_notification("info", "Offline mode is not yet implemented")

    def _on_worker_progress(self, stage: str, percentage: float, message: str):
        """Handle progress updates from the worker."""
        # Scale normalization: if percentage is in 0-1 range (and > 0), scale to 0-100
        # This makes the integration robust to different API response formats
        display_value = percentage
        if 0 < percentage <= 1.0:
            display_value = percentage * 100
            
        self.progress_label.setText(message)
        self.progress_bar.setValue(int(display_value))

    def _on_worker_finished(self, source_code: str):
        """Handle successful decompilation."""
        self._show_progress(False)
        self._set_controls_enabled(True)
        self.result_area.setText(source_code)
        
        main_win = self.window()
        if hasattr(main_win, "show_notification"):
            main_win.show_notification("success", "Decompilation complete!")

    def _on_worker_error(self, error_message: str):
        """Handle decompilation error."""
        self._show_progress(False)
        self._set_controls_enabled(True)
        self.result_area.setText(f"# Error\n# {error_message}")
        
        main_win = self.window()
        if hasattr(main_win, "show_notification"):
            main_win.show_notification("error", error_message)

    def _on_worker_cached(self):
        """Handle cached result notification."""
        main_win = self.window()
        if hasattr(main_win, "show_notification"):
            main_win.show_notification("info", "Result retrieved from cache")

    def _show_progress(self, show: bool):
        """Show or hide progress indicators."""
        self.progress_frame.setVisible(show)
        if show:
            self.progress_bar.setValue(0)
            self.progress_label.setText("Initializing...")

    def _set_controls_enabled(self, enabled: bool):
        """Enable or disable controls during processing."""
        self.select_btn.setEnabled(enabled)
        self.execute_btn.setEnabled(enabled and self._file_selected)
        self.mode_toggle.setEnabled(enabled)

    def _copy_to_clipboard(self):
        data = self.result_area.toPlainText()
        if data:
            QApplication.clipboard().setText(data)
            main_win = self.window()
            if hasattr(main_win, "show_notification"):
                main_win.show_notification("info", "Result copied to clipboard.")

    def showEvent(self, event):
        super().showEvent(event)

    def _check_consent(self):
        self.tos_overlay = TOSDialog(parent=self.window())
        self.tos_overlay.accepted.connect(self._on_consent_accepted)
        self.tos_overlay.rejected.connect(self._on_consent_rejected)
        self.tos_overlay.fade_in()

    def _on_consent_accepted(self):
        self._consent_accepted = True
        self.content_container.setEnabled(True)

    def _on_consent_rejected(self):
        self.mode_toggle.set_checked(False)
        self.content_container.setEnabled(True)
