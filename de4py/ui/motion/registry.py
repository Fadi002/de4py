from __future__ import annotations

from PySide6.QtCore import QObject, QPropertyAnimation

class AnimationRegistry:
    """
    Central registry for tracking active animations and preventing overlap.
    Enforces the rule: One active animation per property per widget.
    """
    _instance: AnimationRegistry | None = None

    @classmethod
    def instance(cls) -> AnimationRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        # key: (id(target), prop_name), value: QPropertyAnimation
        self._animations: dict[tuple[int, bytes], QPropertyAnimation] = {}

    def get_or_create(self, target: QObject, prop_name: bytes) -> QPropertyAnimation:
        """
        Retrieves an existing animation for the target/property, or creates a new one.
        If an existing animation is running, it stops it.
        """
        key = (id(target), prop_name)

        if key in self._animations:
            anim = self._animations[key]
            # Verify the target still matches the anim's target (in case of object reuse/deletion)
            if anim.targetObject() is target:
                if anim.state() == QPropertyAnimation.State.Running:
                    anim.stop()
                return anim
            else:
                self._animations.pop(key, None)

        anim = QPropertyAnimation(target, prop_name)
        # The dict owns the animation, not the target; the destroyed signal prunes dead entries.
        self._animations[key] = anim

        target.destroyed.connect(lambda obj=None, k=key: self._animations.pop(k, None))

        return anim

    def cancel_all(self, target: QObject):
        target_id = id(target)
        keys_to_remove = []
        for key, animation in self._animations.items():
            if key[0] == target_id:
                if animation.state() == QPropertyAnimation.State.Running:
                    animation.stop()
                keys_to_remove.append(key)

        for key in keys_to_remove:
            self._animations.pop(key, None)
