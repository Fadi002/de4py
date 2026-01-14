from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGraphicsBlurEffect, QGraphicsScene, QGraphicsPixmapItem, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QTimer, QRectF, QPropertyAnimation
from PySide6.QtGui import QPainter, QColor, QPixmap


class LoadingOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LoadingOverlay")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self._blurred_bg = None
        self._lock_events = False
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        # Setup Status Label
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Spacer for spinner (handled in paintEvent)
        layout.addSpacing(100)
        
        self.status_label = QLabel("")
        self.status_label.setObjectName("SubtitleLabel") # Use existing style
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: white; font-weight: bold; font-size: 18px;")
        layout.addWidget(self.status_label)

    def set_status(self, text: str):
        self.status_label.setText(text)
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._lock_events and self.parent():
            self.setGeometry(self.parent().rect())
            self._blurred_bg = self._create_blur_cache()
        self._timer.start(16)  # ~60 FPS

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()
        if not self._lock_events:
            self._blurred_bg = None

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

    def _rotate(self):
        self._angle = (self._angle + 6) % 360  # smaller increment = smoother
        self.update()  # trigger paintEvent

    def _create_blur_cache(self):
        top_window = self.window()
        if not top_window or self._lock_events:
            return None
        
        self._lock_events = True
        super().hide() # Use native hide for immediate effect
        screen = top_window.screen()
        if not screen:
            from PySide6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
            
        snapshot = screen.grabWindow(top_window.winId(),
                                     0, 0, top_window.width(), top_window.height())
        super().show() # Use native show
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
        scene.render(painter, QRectF(blurred_pixmap.rect()), QRectF(snapshot.rect()))
        painter.end()
        return blurred_pixmap

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        # 1. Draw blurred background
        if self._blurred_bg:
            painter.drawPixmap(rect, self._blurred_bg)

        # 2. Draw semi-transparent overlay
        painter.fillRect(rect, QColor(0, 0, 0, 160))

        # 3. Draw spinner
        center = rect.center()
        radius = 25

        painter.save()
        painter.translate(center)
        painter.rotate(self._angle)  # rotate spinner

        # Glow arcs (for visual depth)
        for i in range(10, 0, -1):
            alpha = int((10 - i) * 5)
            pen = painter.pen()
            pen.setWidthF(2 + i)  # thicker for outer glow
            pen.setColor(QColor(2, 135, 207, alpha))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawArc(-radius, -radius, radius*2, radius*2, 0*16, 270*16)

        # Main blue arc
        pen = painter.pen()
        pen.setWidthF(4)
        pen.setColor(QColor(2, 135, 207))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(-radius, -radius, radius*2, radius*2, 0*16, 270*16)

        # Small white highlight
        pen.setColor(QColor(255, 255, 255))
        painter.setPen(pen)
        painter.drawArc(-radius, -radius, radius*2, radius*2, 270*16, 90*16)

        painter.restore()
        painter.end()
