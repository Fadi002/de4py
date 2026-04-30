# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from __future__ import annotations

import weakref
from PySide6.QtCore import (
    QObject, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup,
    QAbstractAnimation, QPoint, QRect, Property, Qt, QTimer
)
from PySide6.QtWidgets import QWidget, QGraphicsOpacityEffect, QGraphicsScale

from de4py.ui.motion.spring import FramePacer
from de4py.ui.motion.material import MaterialState, set_wake_callback


class MotionManager(QObject):
    DURATION_MICRO = 150
    DURATION_PRESS = 85
    DURATION_SPRING = 240
    DURATION_SLIDE = 320
    DURATION_TRANSITION = 260

    EASE_STANDARD = QEasingCurve.Type.OutCubic
    EASE_HEAVY = QEasingCurve.Type.OutQuart
    EASE_SPRING = QEasingCurve.Type.OutBack
    EASE_FADE = QEasingCurve.Type.InOutCubic

    _active_animations: dict = {}
    _material_registry: dict[int, tuple[weakref.ref, MaterialState]] = {}
    _sim_timer: QTimer | None = None
    _pacer: FramePacer | None = None

    @classmethod
    def start_simulation(cls):
        if cls._sim_timer is not None:
            return
        cls._pacer = FramePacer.instance()
        set_wake_callback(cls.wake)
        cls._sim_timer = QTimer()
        cls._sim_timer.setTimerType(Qt.TimerType.PreciseTimer)
        cls._sim_timer.setInterval(16)
        cls._sim_timer.timeout.connect(cls._tick)
        cls._sim_timer.start()

    @classmethod
    def stop_simulation(cls):
        if cls._sim_timer:
            cls._sim_timer.stop()
            cls._sim_timer = None

    @classmethod
    def register_material(cls, widget: QWidget, mat: MaterialState):
        cls._material_registry[id(widget)] = (weakref.ref(widget), mat)
        if cls._sim_timer is None:
            cls.start_simulation()

    @classmethod
    def unregister_material(cls, widget: QWidget):
        cls._material_registry.pop(id(widget), None)

    @classmethod
    def wake(cls):
        if cls._sim_timer and not cls._sim_timer.isActive():
            cls._sim_timer.start()

    @classmethod
    def _tick(cls):
        dt = cls._pacer.tick()
        any_active = False
        dead = []
        for wid, (ref, mat) in cls._material_registry.items():
            w = ref()
            if w is None:
                dead.append(wid)
                continue
            if mat.tick(dt):
                any_active = True
                try:
                    w.update()
                except RuntimeError:
                    dead.append(wid)
        for wid in dead:
            cls._material_registry.pop(wid, None)
        if not any_active and cls._sim_timer:
            cls._sim_timer.stop()

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
