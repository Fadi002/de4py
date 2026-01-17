from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QApplication, QSizePolicy,
    QLineEdit, QPushButton, QGraphicsBlurEffect, QGraphicsScene, QGraphicsPixmapItem, QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, Signal, QRectF, QPropertyAnimation
from PySide6.QtGui import QPainter, QColor, QPixmap

from de4py.lang import tr
from de4py.lang.keys import DIALOG_VALUE_PLACEHOLDER



class ModalOverlay(QWidget):
    submitted = Signal(str)
    closed = Signal()

    def __init__(self, title: str, input_label: str, button_label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("ModalOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._setup_ui(title, input_label, button_label)
        self._blurred_bg = None
        self._lock_events = False

    def _setup_ui(self, title: str, input_label: str, button_label: str):
        # Main overlay layout (full-size transparent parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # no padding
        layout.setSpacing(0)
        
        # Top stretch to push frame to center vertically
        layout.addStretch(1)
        
        # Modal frame
        self.modal_frame = QFrame()
        self.modal_frame.setObjectName("StyledFrame")
        self.modal_frame.setFixedWidth(400)  # fixed width, flexible height
        self.modal_frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        
        # Frame layout
        frame_layout = QVBoxLayout(self.modal_frame)
        frame_layout.setContentsMargins(20, 15, 20, 15)
        frame_layout.setSpacing(10)
        
        # Header
        header_layout = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("SubtitleLabel")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        self.close_btn = QPushButton("X")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.clicked.connect(self._on_close)
        header_layout.addWidget(self.close_btn)
        frame_layout.addLayout(header_layout)
        
        # Input row
        input_layout = QHBoxLayout()
        input_label_widget = QLabel(input_label)
        input_layout.addWidget(input_label_widget)
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText(tr(DIALOG_VALUE_PLACEHOLDER))

        self.input_field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        input_layout.addWidget(self.input_field)
        frame_layout.addLayout(input_layout)
        
        # Submit button
        self.submit_btn = QPushButton(button_label)
        self.submit_btn.setFixedHeight(35)
        self.submit_btn.clicked.connect(self._on_submit)
        frame_layout.addWidget(self.submit_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Add frame to main layout
        layout.addWidget(self.modal_frame, alignment=Qt.AlignmentFlag.AlignHCenter)
        
        # Bottom stretch for vertical centering
        layout.addStretch(1)

    def _on_close(self):
        self.fade_out()
        self.closed.emit()

    def _on_submit(self):
        value = self.input_field.text().strip()
        if value:
            self.submitted.emit(value)
            self.fade_out()

    def fade_in(self):
        self.setHidden(False)
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.anim = QPropertyAnimation(self.effect, b"opacity")
        self.anim.setDuration(250)
        self.anim.setStartValue(0)
        self.anim.setEndValue(1)
        self.anim.start()

    def fade_out(self):
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.anim = QPropertyAnimation(self.effect, b"opacity")
        self.anim.setDuration(250)
        self.anim.setStartValue(1)
        self.anim.setEndValue(0)
        self.anim.finished.connect(lambda: self.setHidden(True))
        self.anim.start()

    def _create_blur_cache(self):
        top_window = self.window()
        if not top_window or self._lock_events:
            return None
        
        self._lock_events = True
        super().hide() # Hide modal immediately to see what's behind it
        
        # Give the event loop a tiny moment to process the hide
        # if needed, but usually grabWindow is immediate on the last buffer
        
        screen = top_window.screen()
        if not screen:
            screen = QApplication.primaryScreen()
            
        # Capture the actual screen pixels at the window's geometry
        # Using winId() is the key to capturing natively rendered content
        snapshot = screen.grabWindow(
            top_window.winId(),
            0, 0, top_window.width(), top_window.height()
        )
        
        super().show()
        self._lock_events = False
        
        # Apply blur effect via QGraphicsScene (most performant way in Qt)
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
        self.input_field.clear()
        self.input_field.setFocus()

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
