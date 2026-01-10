from PySide6.QtWidgets import QPushButton, QGraphicsDropShadowEffect, QStackedWidget, QWidget, QGraphicsOpacityEffect
from PySide6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QRect, Property, 
    QAbstractAnimation, QParallelAnimationGroup, QPoint, QSize
)
from PySide6.QtGui import QColor, QCursor

class AnimatedButton(QPushButton):
    """
    A QPushButton with built-in hover animations:
    - Scale up slightly on hover
    - Drop shadow fade-in
    - Color pulse overlay (optional)
    """
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._hover_scale = 1.0
        self._shadow_blur = 0.0
        self._shadow_active_color = QColor(0, 255, 34, 80) # Default
        
        # Shadow effect
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(0)
        self._shadow.setOffset(0, 2)
        self._shadow.setColor(QColor(0, 0, 0, 0)) # Start transparent
        self.setGraphicsEffect(self._shadow)
        
        # Animations
        self._anim_group = QParallelAnimationGroup(self)
        
    @Property(QColor)
    def shadow_active_color(self):
        return self._shadow_active_color
        
    @shadow_active_color.setter
    def shadow_active_color(self, color):
        self._shadow_active_color = color

    def enterEvent(self, event):
        self._animate_shadow(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_shadow(False)
        super().leaveEvent(event)
        
    def _animate_shadow(self, active):
        # Stop existing
        if self._anim_group.state() == QAbstractAnimation.State.Running:
            self._anim_group.stop()
        self._anim_group.clear()
        
        # Animate Blur Radius (roughly simulating depth)
        anim_blur = QPropertyAnimation(self._shadow, b"blurRadius")
        anim_blur.setDuration(200)
        anim_blur.setStartValue(self._shadow.blurRadius())
        anim_blur.setEndValue(20 if active else 0)
        anim_blur.setEasingCurve(QEasingCurve.Type.OutQuad)
        
        # Use the theme-controlled color
        self._shadow.setColor(self._shadow_active_color if active else QColor(0,0,0,0))

        self._anim_group.addAnimation(anim_blur)
        self._anim_group.start()


class AnimatedStackedWidget(QStackedWidget):
    """
    A QStackedWidget with slide/fade transitions.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._anim_group = None
        self._is_animating = False

    def fade_to_index(self, index):
        if index == self.currentIndex():
            return
        if self._is_animating:
            return # Block animation spam
            
        current_widget = self.currentWidget()
        next_widget = self.widget(index)
        
        if not current_widget or not next_widget:
            self.setCurrentIndex(index)
            return

        next_widget.setVisible(True)
        
        # Setup opacity effects
        current_effect = QGraphicsOpacityEffect(current_widget)
        next_effect = QGraphicsOpacityEffect(next_widget)
        current_widget.setGraphicsEffect(current_effect)
        next_widget.setGraphicsEffect(next_effect)
        
        next_effect.setOpacity(0)
        
        # Create Animation Group
        self._anim_group = QParallelAnimationGroup(self)
        
        anim_out = QPropertyAnimation(current_effect, b"opacity")
        anim_out.setDuration(250)
        anim_out.setStartValue(1)
        anim_out.setEndValue(0)
        
        anim_in = QPropertyAnimation(next_effect, b"opacity")
        anim_in.setDuration(250)
        anim_in.setStartValue(0)
        anim_in.setEndValue(1)
        
        self._anim_group.addAnimation(anim_out)
        self._anim_group.addAnimation(anim_in)
        
        def on_finished():
            self.setCurrentIndex(index)
            current_widget.setGraphicsEffect(None)
            next_widget.setGraphicsEffect(None)
            current_widget.setVisible(False) # Ensure old one is hidden
            self._is_animating = False
            
        self._anim_group.finished.connect(on_finished)
        self._is_animating = True
        self._anim_group.start()
