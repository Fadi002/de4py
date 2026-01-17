from PySide6.QtCore import (
    QObject, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, 
    QAbstractAnimation, QPoint, QRect, Property
)
from PySide6.QtWidgets import QWidget, QGraphicsOpacityEffect, QGraphicsScale

class MotionManager(QObject):
    DURATION_MICRO = 120       # Hover, subtle feedback (90-140ms range)
    DURATION_PRESS = 100       # Button press/release (100-120ms range)
    DURATION_SPRING = 300      # Bouncy release effects
    DURATION_SLIDE = 350       # Sidebar/Panel movement (heavier feel)
    DURATION_TRANSITION = 220  # Screen transitions
    
    EASE_STANDARD = QEasingCurve.OutCubic 
    EASE_HEAVY = QEasingCurve.OutExpo
    EASE_SPRING = QEasingCurve.OutBack
    EASE_FADE = QEasingCurve.InOutSine

    _active_animations = {}

    @staticmethod
    def stop_animations(target: QObject):
        if target in MotionManager._active_animations:
            group = MotionManager._active_animations[target]
            if group.state() == QAbstractAnimation.Running:
                group.stop()
            del MotionManager._active_animations[target]

    @staticmethod
    def _register_animation(target: QObject, anim_group: QParallelAnimationGroup):
        MotionManager.stop_animations(target)
        MotionManager._active_animations[target] = anim_group
        
        def cleanup():
            if target in MotionManager._active_animations:
                if MotionManager._active_animations[target] == anim_group:
                    del MotionManager._active_animations[target]
        
        anim_group.finished.connect(cleanup)
        anim_group.start(QAbstractAnimation.DeleteWhenStopped)

    @staticmethod
    def animate_scale(target: QObject, start: float, end: float, duration: int = DURATION_MICRO, easing=EASE_STANDARD):
        prop_name = b"scale_factor"
        if target.metaObject().indexOfProperty("scale_factor") != -1:
             anim = QPropertyAnimation(target, prop_name)
             anim.setDuration(duration)
             anim.setStartValue(start)
             anim.setEndValue(end)
             anim.setEasingCurve(easing)
             
             group = QParallelAnimationGroup()
             group.addAnimation(anim)
             MotionManager._register_animation(target, group)
             return

        scale_transform = None
        if isinstance(target, QWidget):
            for t in target.transforms():
                if isinstance(t, QGraphicsScale):
                    scale_transform = t
                    break
            
            if not scale_transform:
                scale_transform = QGraphicsScale(target)
                target.setTransform(scale_transform)
                if target.rect().isValid():
                     scale_transform.setOrigin(
                        target.rect().center().x(), 
                        target.rect().center().y()
                    )
            
            anim = QPropertyAnimation(scale_transform, b"xScale")
            anim.setDuration(duration)
            anim.setStartValue(start)
            anim.setEndValue(end)
            anim.setEasingCurve(easing)
            
            anim_y = QPropertyAnimation(scale_transform, b"yScale")
            anim_y.setDuration(duration)
            anim_y.setStartValue(start)
            anim_y.setEndValue(end)
            anim_y.setEasingCurve(easing)
            
            group = QParallelAnimationGroup()
            group.addAnimation(anim)
            group.addAnimation(anim_y)
            MotionManager._register_animation(target, group)


    @staticmethod
    def animate_sidebar_width(target: QWidget, start: int, end: int, duration=DURATION_SLIDE, easing=EASE_HEAVY):
        group = QParallelAnimationGroup()
        
        anim_min = QPropertyAnimation(target, b"minimumWidth")
        anim_min.setDuration(duration)
        anim_min.setStartValue(start)
        anim_min.setEndValue(end)
        anim_min.setEasingCurve(easing)
        
        anim_max = QPropertyAnimation(target, b"maximumWidth")
        anim_max.setDuration(duration)
        anim_max.setStartValue(start)
        anim_max.setEndValue(end)
        anim_max.setEasingCurve(easing)
        
        group.addAnimation(anim_min)
        group.addAnimation(anim_max)
        
        MotionManager._register_animation(target, group)

    @staticmethod
    def animate_opacity_fade(target: QWidget, start: float, end: float, duration=DURATION_TRANSITION):
        effect = target.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(target)
            target.setGraphicsEffect(effect)
        
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(MotionManager.EASE_FADE)
        
        group = QParallelAnimationGroup()
        group.addAnimation(anim)
        MotionManager._register_animation(target, group)
