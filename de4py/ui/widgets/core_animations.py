from PySide6.QtWidgets import (
    QPushButton, QGraphicsDropShadowEffect, QStackedWidget, 
    QWidget, QGraphicsOpacityEffect, QCheckBox, QAbstractButton
)
from PySide6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QRect, Property, 
    QAbstractAnimation, QParallelAnimationGroup, QPoint, QSize, 
    QRectF, Signal, QPointF
)
from PySide6.QtGui import QColor, QCursor, QPainter, QBrush, QPen, QFont, QPalette, QIcon, QPixmap

from de4py.utils import sentry

class AnimatedButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._shadow_active_color = QColor(0, 255, 34, 80)
        
        # Icon theming support
        self._base_icon = QIcon()
        self._icon_color_name = ""
        
        # Internal state for animations
        self._scale = 1.0
        self._hover_progress = 0.0 
        
        # Shadow effect
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(0)
        self._shadow.setOffset(0, 2)
        self._shadow.setColor(QColor(0, 0, 0, 0))
        self.setGraphicsEffect(self._shadow)
        
        # Animation Group
        self._anim_group = QParallelAnimationGroup(self)

    @Property(float)
    def scale_factor(self):
        return self._scale

    @scale_factor.setter
    def scale_factor(self, value):
        self._scale = value
        self.update()

    @Property(float)
    def hover_progress(self):
        return self._hover_progress

    @hover_progress.setter
    def hover_progress(self, value):
        self._hover_progress = value
        # Update shadow based on progress
        if value > 0:
            self._shadow.setBlurRadius(20 * value)
            c = self._shadow_active_color
            self._shadow.setColor(QColor(c.red(), c.green(), c.blue(), int(c.alpha() * value)))
        else:
            self._shadow.setBlurRadius(0)
            self._shadow.setColor(QColor(0, 0, 0, 0))
        self.update()

    @Property(QColor)
    def shadow_active_color(self):
        return self._shadow_active_color
        
    @shadow_active_color.setter
    def shadow_active_color(self, color):
        self._shadow_active_color = color

    # --- Icon Theming Support ---
    def setIcon(self, icon):
        self._base_icon = icon
        self._update_icon_color()
        
    def _update_icon_color(self):
        if not self._base_icon or self._base_icon.isNull():
            super().setIcon(QIcon())
            return
            
        if not self._icon_color_name:
            super().setIcon(self._base_icon)
            return
            
        c = QColor(self._icon_color_name)
        if not c.isValid():
            super().setIcon(self._base_icon)
            return
            
        # Tint the icon
        # We'll assume a standard size or the current icon size
        size = self.iconSize()
        if size.isEmpty(): 
            size = QSize(24, 24)
            
        pix = self._base_icon.pixmap(size)
        if pix.isNull():
            super().setIcon(self._base_icon)
            return
            
        # Paint color over pixmap
        tinter = QPainter(pix)
        tinter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        tinter.fillRect(pix.rect(), c)
        tinter.end()
        
        super().setIcon(QIcon(pix))

    def getIconColorName(self) -> str:
        return self._icon_color_name

    def setIconColorName(self, color_name: str):
        self._icon_color_name = color_name
        self._update_icon_color()

    iconColorName = Property(str, getIconColorName, setIconColorName)
    # ----------------------------

    def enterEvent(self, event):
        self._animate_hover(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_hover(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._animate_press(True)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._animate_press(False)
        super().mouseReleaseEvent(event)

    def _animate_hover(self, active):
        anim = QPropertyAnimation(self, b"hover_progress", self)
        anim.setDuration(200)
        anim.setStartValue(self._hover_progress)
        anim.setEndValue(1.0 if active else 0.0)
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def _animate_press(self, pressed):
        anim = QPropertyAnimation(self, b"scale_factor", self)
        anim.setDuration(100)
        anim.setStartValue(self._scale)
        anim.setEndValue(0.97 if pressed else 1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def paintEvent(self, event):
        # We customized painting to handle scaling
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Apply scaling around center
        rect = self.rect()
        center = rect.center()
        painter.translate(center)
        painter.scale(self._scale, self._scale)
        painter.translate(-center)
        
        from PySide6.QtWidgets import QStyleOptionButton, QStyle
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        
        if self.isDown():
            opt.state |= QStyle.State_Sunken
        else:
            opt.state &= ~QStyle.State_Sunken

        self.style().drawControl(QStyle.ControlElement.CE_PushButton, opt, painter, self)


class AnimatedToggle(QCheckBox):
    """
    iOS-style toggle switch.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._position = 0.0 # 0.0 = Left (Off), 1.0 = Right (On)
        self._track_color_on = QColor(0, 255, 34) # Default Neon Green
        self._track_color_off = QColor(60, 60, 60)
        self._knob_color = QColor(255, 255, 255)
        
        # Setup animation
        self._anim = QPropertyAnimation(self, b"position", self)
        self._anim.setDuration(300)
        self._anim.setEasingCurve(QEasingCurve.Type.OutBack) # Slight bounce
        
        self.stateChanged.connect(self._handle_state_change)

    @Property(float)
    def position(self):
        return self._position
    
    @position.setter
    def position(self, pos):
        self._position = pos
        self.update()

    def _handle_state_change(self, state):
        self._anim.stop()
        self._anim.setStartValue(self._position)
        self._anim.setEndValue(1.0 if state == Qt.CheckState.Checked.value else 0.0)
        self._anim.start()

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        h = rect.height()
        w = rect.width()
        
        # Track
        track_radius = h / 2
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Interpolate color
        r = self._track_color_off.red() + (self._track_color_on.red() - self._track_color_off.red()) * self._position
        g = self._track_color_off.green() + (self._track_color_on.green() - self._track_color_off.green()) * self._position
        b = self._track_color_off.blue() + (self._track_color_on.blue() - self._track_color_off.blue()) * self._position
        track_color = QColor(int(r), int(g), int(b))
        
        painter.setBrush(track_color)
        painter.drawRoundedRect(rect, track_radius, track_radius)
        
        # Knob
        knob_margin = 4
        knob_size = h - (knob_margin * 2)
        knob_x_start = knob_margin
        knob_x_end = w - knob_margin - knob_size
        
        current_knob_x = knob_x_start + (knob_x_end - knob_x_start) * self._position
        
        knob_rect = QRectF(current_knob_x, knob_margin, knob_size, knob_size)
        painter.setBrush(self._knob_color)
        painter.setPen(Qt.PenStyle.NoPen)
        d = 0 
        painter.drawRoundedRect(knob_rect, knob_size/2, knob_size/2)


class AnimatedCheckBox(QCheckBox):
    """
    Checkbox with smooth fade/scale animations.
    """
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self._check_progress = 0.0
        self._hover_progress = 0.0
        
        self._active_color = QColor(0, 255, 34)
        self._border_color = QColor(100, 100, 100)
        self._bg_color = QColor(30, 30, 30)

    @Property(float)
    def check_progress(self):
        return self._check_progress
    
    @check_progress.setter
    def check_progress(self, val):
        self._check_progress = val
        self.update()

    def hitButton(self, pos):
        return self.rect().contains(pos)
        
    def checkStateSet(self):
        super().checkStateSet()
        self._animate_check()

    def nextCheckState(self):
        super().nextCheckState()

    def _animate_check(self):
        anim = QPropertyAnimation(self, b"check_progress", self)
        anim.setDuration(250)
        anim.setStartValue(self._check_progress)
        anim.setEndValue(1.0 if self.isChecked() else 0.0)
        anim.setEasingCurve(QEasingCurve.Type.OutBack)
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw Text
        font_metrics = painter.fontMetrics()
        text_height = font_metrics.height()
        
        rect = self.rect()
        box_size = 18
        box_y = (rect.height() - box_size) / 2
        box_rect = QRectF(0, box_y, box_size, box_size)
        
        painter.setPen(QPen(self._border_color if self._check_progress < 0.5 else self._active_color, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self._check_progress > 0:
             # Fill bg
             painter.setBrush(QColor(self._active_color.red(), self._active_color.green(), self._active_color.blue(), int(255 * self._check_progress)))
             painter.setPen(Qt.PenStyle.NoPen)
             painter.drawRoundedRect(box_rect, 4, 4)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(self._border_color if self._check_progress < 0.5 else self._active_color, 2))
        painter.drawRoundedRect(box_rect, 4, 4)
   
        # Draw Checkmark`
        if self._check_progress > 0.1:
            painter.translate(0, box_y)
            path = QPainter.Path()
            painter.translate(box_size/2, box_size/2)
            painter.scale(self._check_progress, self._check_progress)
            painter.translate(-box_size/2, -box_size/2)
            
            pen = QPen(QColor(0,0,0) if self._active_color.lightness() > 150 else QColor(255,255,255), 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            
            painter.drawLine(4, 9, 7, 12)
            painter.drawLine(7, 12, 14, 5)
            
            painter.translate(0, -box_y)

        # Draw Text
        if self.text():
             text_rect = QRectF(box_size + 8, 0, rect.width() - box_size - 8, rect.height())
             painter.setPen(self.palette().text().color())
             painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())


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

        with sentry.span("ui.transition", description=f"Index {self.currentIndex()} → {index}"):
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
            current_widget.setVisible(False) 
            self._is_animating = False
            
        self._anim_group.finished.connect(on_finished)
        self._is_animating = True
        self._anim_group.start()
