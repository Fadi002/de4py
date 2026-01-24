import os
import math
from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QApplication,
    QProgressBar, QSizePolicy, QGraphicsBlurEffect, QGraphicsScene, QGraphicsPixmapItem
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QRect, QRectF, Property
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QPainter, QColor, QPixmap, QPen
from de4py.ui.constants import NOTIF_WIDTH, NOTIF_DURATION, NOTIF_PROGRESS_DURATION, ANIM_DURATION_NORMAL


class NotificationWidget(QFrame):
    SLIDE_OFFSET = 50  # how much it slides from the right

    def __init__(self, notif_type: str, message: str, parent=None, blur_pixmap=None):
        super().__init__(parent)
        self.setObjectName("NotificationFrame")
        self.setFixedWidth(NOTIF_WIDTH)
        self._notif_type = notif_type
        self._progress_value = 100
        self._blur_pixmap = blur_pixmap
        self._icon_color = QColor("white") # Default

        # Glass + border properties
        self._border_color = QColor("#0287CF")
        self._border_width = 1.5
        self._corner_radius = 14
        self._overlay_color = QColor(25, 25, 25, 170)  # Default dark

        # Transparent for glass effect
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)

        self._setup_ui(notif_type, message)

    # Qt properties so QSS can set them dynamically
    def getOverlayColor(self) -> QColor:
        return self._overlay_color

    # Qt properties so QSS can set them dynamically
    def getOverlayColorName(self) -> str:
        return self._overlay_color.name(QColor.HexArgb)

    def setOverlayColorName(self, color_str: str):
        if color_str:
            # Handle hex with alpha or standard names
            c = QColor(color_str)
            if c.isValid():
                self._overlay_color = c
                self.update()

    overlayColorName = Property(str, getOverlayColorName, setOverlayColorName)

    # New Property for Icon Color
    def getIconColorName(self) -> str:
        return self._icon_color.name(QColor.HexArgb)

    def setIconColorName(self, color_str: str):
        if color_str:
            c = QColor(color_str)
            if c.isValid():
                self._icon_color = c
                # Refresh icon
                self._set_icon(self._notif_type)
                self.update()
            
    iconColorName = Property(str, getIconColorName, setIconColorName)

    def getBorderColor(self) -> QColor:
        return self._border_color

    def setBorderColor(self, color):
        if isinstance(color, QColor):
            self._border_color = color
        else:
            self._border_color = QColor(color)
        self.update()

    borderColor = Property(QColor, getBorderColor, setBorderColor)

    def getBorderWidth(self) -> float:
        return float(self._border_width)

    def setBorderWidth(self, w):
        try:
            self._border_width = float(w)
        except Exception:
            self._border_width = 1.5
        self.update()

    borderWidth = Property(float, getBorderWidth, setBorderWidth)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        bw = float(self._border_width)
        radius = float(self._corner_radius)

        inset = bw / 2.0
        overlay_rect = rect.adjusted(math.ceil(inset), math.ceil(inset),
                                     -math.ceil(inset), -math.ceil(inset))

        if self._blur_pixmap and not self._blur_pixmap.isNull() and self.parent():
            from PySide6.QtGui import QPainterPath
            path = QPainterPath()
            path.addRoundedRect(overlay_rect, radius, radius)
            
            painter.save()
            painter.setClipPath(path)
            
            global_pos = self.mapTo(self.parent(), QPoint(0, 0))
            src = QRect(global_pos, self.size())
            painter.drawPixmap(rect, self._blur_pixmap, src)
            
            painter.restore()

        inset = bw / 2.0
        overlay_rect = rect.adjusted(math.ceil(inset), math.ceil(inset),
                                     -math.ceil(inset), -math.ceil(inset))
        
        painter.setBrush(self._overlay_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(overlay_rect, radius, radius)

        if bw > 0:
            pen = QPen(self._border_color)
            pen.setWidthF(bw)
            pen.setCosmetic(False)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(overlay_rect, radius, radius)

        painter.end()

    def _setup_ui(self, notif_type: str, message: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
        self.setMinimumHeight(80)

        # Icon + message
        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)

        # Replaced QSvgWidget with QLabel for easier pixmap manipulation
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(24, 24)
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        self._set_icon(notif_type)
        content_layout.addWidget(self.icon_label)

        self.message_label = QLabel(message)
        self.message_label.setWordWrap(True)
        self.message_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.message_label.setMinimumHeight(24)
        # Removed hardcoded color/font to allow QSS inheritance
        # self.message_label.setStyleSheet("color: #ffffff; font-weight: 500;")
        content_layout.addWidget(self.message_label, 1)

        layout.addLayout(content_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMinimumHeight(4)
        self.progress_bar.setMaximumHeight(4)
        self.progress_bar.setValue(100)
        self.progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.progress_bar)

        # Timer for progress
        self._progress_timer = QTimer(self)
        self._progress_timer.timeout.connect(self._update_progress)
        self._progress_timer.start(NOTIF_PROGRESS_DURATION // 100)

    def _set_icon(self, notif_type: str):
        base_path = os.path.dirname(os.path.abspath(__file__))
        resources_path = os.path.join(base_path, "..", "resources")
        icon_map = {
            "success": "check-circle.svg",
            "failure": "x-circle.svg",
            "warning": "alert-triangle.svg",
        }
        icon_file = icon_map.get(notif_type, "info.svg")
        icon_path = os.path.join(resources_path, icon_file)

        if os.path.exists(icon_path):
            renderer = QSvgRenderer(icon_path)
            
            # Create a pixmap larger than needed for quality, then scale down
            size = 48
            pix = QPixmap(size, size)
            pix.fill(Qt.transparent)
            
            painter = QPainter(pix)
            renderer.render(painter)
            
            # Now tint it using CompositionMode
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(pix.rect(), self._icon_color)
            painter.end()
            
            # Scale down to 24x24
            final_pix = pix.scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.icon_label.setPixmap(final_pix)

    def _update_progress(self):
        if self._progress_value > 0:
            self._progress_value -= 1
            self.progress_bar.setValue(self._progress_value)
        else:
            self._progress_timer.stop()


class NotificationManager(QWidget):
    MAX_NOTIFICATIONS = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self._notifications = []
        self._blurred_bg = None

        if parent:
            self.setParent(parent)
            self.setGeometry(0, 0, parent.width(), parent.height())
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)  # pass clicks through
            self.show()

    def _create_blur_cache(self, _):
        top_window = self.window()
        if not top_window:
            return None

        screen = top_window.screen()
        if not screen:
            screen = QApplication.primaryScreen()

        snapshot = screen.grabWindow(
            top_window.winId(),
            0, 0, top_window.width(), top_window.height()
        )

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

    def show_notification(self, notif_type: str, message: str):
        parent_widget = self.parent() or self
        top_window = self.window()

        if not self._notifications:
            self._blurred_bg = self._create_blur_cache(top_window)

        if len(self._notifications) >= self.MAX_NOTIFICATIONS:
            oldest = self._notifications.pop(0)
            oldest.deleteLater()

        notif = NotificationWidget(notif_type, message, parent_widget, self._blurred_bg)
        self._notifications.insert(0, notif)
        notif.show()
        notif.raise_()

        x_start = parent_widget.width() + NotificationWidget.SLIDE_OFFSET
        x_end = parent_widget.width() - NOTIF_WIDTH - 20
        y = 20 + sum(n.height() + 10 for n in self._notifications[:-1])
        notif.move(x_start, y)

        anim_in = QPropertyAnimation(notif, b"pos", notif)
        anim_in.setDuration(ANIM_DURATION_NORMAL)
        anim_in.setStartValue(QPoint(x_start, y))
        anim_in.setEndValue(QPoint(x_end, y))
        anim_in.setEasingCurve(QEasingCurve.OutCubic)
        anim_in.start()
        anim_in.valueChanged.connect(notif.update)

        QTimer.singleShot(NOTIF_DURATION, lambda n=notif: self._slide_out(n))

    def _slide_out(self, notif: NotificationWidget):
        if notif not in self._notifications:
            return

        x_end = self.parent().width() + NotificationWidget.SLIDE_OFFSET
        anim_out = QPropertyAnimation(notif, b"pos", notif)
        anim_out.setDuration(ANIM_DURATION_NORMAL)
        anim_out.setEndValue(QPoint(x_end, notif.y()))
        anim_out.setEasingCurve(QEasingCurve.InCubic)
        anim_out.valueChanged.connect(notif.update)

        def on_finished():
            if notif in self._notifications:
                self._notifications.remove(notif)
            notif.deleteLater()
            self._restack_notifications()
            if not self._notifications:
                self._blurred_bg = None

        anim_out.finished.connect(on_finished)
        anim_out.start()

    def _restack_notifications(self):
        parent_widget = self.parent() or self
        y = 20
        for n in self._notifications:
            x = parent_widget.width() - NOTIF_WIDTH - 20
            anim = QPropertyAnimation(n, b"pos", n)
            anim.setDuration(ANIM_DURATION_NORMAL)
            anim.setEndValue(QPoint(x, y))
            anim.setEasingCurve(QEasingCurve.InOutCubic)
            anim.valueChanged.connect(n.update)
            anim.start()
            y += n.height() + 10
