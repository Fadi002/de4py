from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt, QSize, QPoint, Property, QRectF
from PySide6.QtGui import QPainter, QColor, QIcon, QRadialGradient, QBrush, QPen, QPixmap

from de4py.ui.motion.manager import MotionManager

class HamburgerButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(50, 50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self._scale_factor = 1.0
        self._hover_progress = 0.0 
        self._icon = QIcon()
        self._icon_color_name = ""
        
        self._bg_color = QColor(255, 255, 255, 10) 
        self._hover_color = QColor(255, 255, 255, 25) 
        
        self.setAttribute(Qt.WA_NoSystemBackground)

    def setIcon(self, icon: QIcon):
        self._icon = icon
        self.update()

    def getIconColorName(self) -> str:
        return self._icon_color_name

    def setIconColorName(self, color_name: str):
        self._icon_color_name = color_name
        self.update()

    iconColorName = Property(str, getIconColorName, setIconColorName)

    # --- Properties for Animation ---
    
    def get_scale_factor(self):
        return self._scale_factor

    def set_scale_factor(self, factor):
        self._scale_factor = factor
        self.update()

    scale_factor = Property(float, get_scale_factor, set_scale_factor)
    
    def get_hover_progress(self):
        return self._hover_progress
        
    def set_hover_progress(self, progress):
        self._hover_progress = progress
        self.update()
        
    hover_progress = Property(float, get_hover_progress, set_hover_progress)

    # --- Interaction ---

    def enterEvent(self, event):
        MotionManager.stop_animations(self) 
        
        from PySide6.QtCore import QPropertyAnimation
        
        anim = QPropertyAnimation(self, b"hover_progress")
        anim.setDuration(MotionManager.DURATION_MICRO)
        anim.setStartValue(self._hover_progress)
        anim.setEndValue(1.0)
        anim.setEasingCurve(MotionManager.EASE_STANDARD)
        anim.start(QPropertyAnimation.DeleteWhenStopped)
        
        super().enterEvent(event)

    def leaveEvent(self, event):
        # Hover Out
        MotionManager.stop_animations(self)
        
        from PySide6.QtCore import QPropertyAnimation
        anim = QPropertyAnimation(self, b"hover_progress")
        anim.setDuration(MotionManager.DURATION_MICRO)
        anim.setStartValue(self._hover_progress)
        anim.setEndValue(0.0)
        anim.setEasingCurve(MotionManager.EASE_STANDARD)
        anim.start(QPropertyAnimation.DeleteWhenStopped)
        
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Scale Down (Compression)
            MotionManager.animate_scale(self, self._scale_factor, 0.92, MotionManager.DURATION_PRESS, MotionManager.EASE_STANDARD)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Spring Release
            MotionManager.animate_scale(self, self._scale_factor, 1.0, MotionManager.DURATION_SPRING, MotionManager.EASE_SPRING)
        super().mouseReleaseEvent(event)
        
    def hitButton(self, pos: QPoint) -> bool:
        center = self.rect().center()
        radius = self.width() / 2 # Assuming square fixed size
        dx = pos.x() - center.x()
        dy = pos.y() - center.y()
        dist_squared = dx*dx + dy*dy
        return dist_squared <= (radius * radius)

    # --- Rendering ---

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Center point
        rect = self.rect()
        center = rect.center()
        radius = min(rect.width(), rect.height()) / 2.0
        
        painter.translate(center)
        painter.scale(self._scale_factor, self._scale_factor)
        painter.translate(-center)

        # Draw Background
        bg_color = QColor(self._bg_color)
        target_color = QColor(self._hover_color)
        
        r = bg_color.red() + (target_color.red() - bg_color.red()) * self._hover_progress
        g = bg_color.green() + (target_color.green() - bg_color.green()) * self._hover_progress
        b = bg_color.blue() + (target_color.blue() - bg_color.blue()) * self._hover_progress
        a = bg_color.alpha() + (target_color.alpha() - bg_color.alpha()) * self._hover_progress
        
        final_bg = QColor(int(r), int(g), int(b), int(a))
        
        painter.setBrush(QBrush(final_bg))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, radius, radius)
        
        if self._hover_progress > 0.1:
            glow = QRadialGradient(center, radius)
            glow.setColorAt(0.85, QColor(255, 255, 255, 0))
            glow.setColorAt(1.0, QColor(255, 255, 255, int(15 * self._hover_progress)))
            painter.setBrush(QBrush(glow))
            painter.drawEllipse(center, radius, radius)

        # Draw Icon
        if not self._icon.isNull():
            icon_size = 24
            
            # Determine Color
            final_icon_color = QColor(255, 255, 255) # default
            if self._icon_color_name:
                c = QColor(self._icon_color_name)
                if c.isValid():
                    final_icon_color = c

            # Render icon to pixmap
            pix = self._icon.pixmap(icon_size, icon_size)
            if not pix.isNull():
                # Tint
                painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

                colored_pix = QPixmap(pix.size())
                colored_pix.fill(Qt.transparent)
                p = QPainter(colored_pix)
                p.drawPixmap(0, 0, pix)
                p.setCompositionMode(QPainter.CompositionMode_SourceIn)
                p.fillRect(colored_pix.rect(), final_icon_color)
                p.end()
                
                # Draw centered
                x = center.x() - icon_size/2
                y = center.y() - icon_size/2
                painter.drawPixmap(int(x), int(y), colored_pix)
