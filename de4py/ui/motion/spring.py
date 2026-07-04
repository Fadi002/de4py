from __future__ import annotations

from PySide6.QtCore import QElapsedTimer


class DampedSpring:
    __slots__ = ('value', 'target', 'velocity', 'tension', 'damping', 'mass')

    def __init__(self, tension: float = 300, damping: float = 26,
                 mass: float = 1.0, initial: float = 0.0):
        self.value = initial
        self.target = initial
        self.velocity = 0.0
        self.tension = tension
        self.damping = damping
        self.mass = mass

    def tick(self, dt: float):
        force = -self.tension * (self.value - self.target) - self.damping * self.velocity
        self.velocity += (force / self.mass) * dt
        self.value += self.velocity * dt

    def is_settled(self, eps: float = 0.0008) -> bool:
        return abs(self.value - self.target) < eps and abs(self.velocity) < eps

    def snap(self):
        self.value = self.target
        self.velocity = 0.0


def spring_responsive(initial: float = 0.0) -> DampedSpring:
    return DampedSpring(420, 34, 1.0, initial)


def spring_gentle(initial: float = 0.0) -> DampedSpring:
    return DampedSpring(170, 22, 1.0, initial)


def spring_heavy(initial: float = 0.0) -> DampedSpring:
    return DampedSpring(120, 20, 1.5, initial)


def spring_settle(initial: float = 0.0) -> DampedSpring:
    return DampedSpring(250, 35, 1.0, initial)


class FramePacer:
    _instance: FramePacer | None = None

    @classmethod
    def instance(cls) -> FramePacer:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._timer = QElapsedTimer()
        self._timer.start()
        self._last_ns= self._timer.nsecsElapsed()
        self._smooth_dt= 0.016

    def tick(self) -> float:
        now = self._timer.nsecsElapsed()
        raw = (now - self._last_ns) / 1_000_000_000.0
        self._last_ns = now
        raw = max(0.004, min(0.05, raw))
        self._smooth_dt = self._smooth_dt * 0.8 + raw * 0.2
        return self._smooth_dt

    @property
    def dt(self) -> float:
        return self._smooth_dt


class InertiaChain:
    _instance: InertiaChain | None = None

    @classmethod
    def instance(cls) -> InertiaChain:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._velocity= 0.0
        self._ts= 0
        self._timer = QElapsedTimer()
        self._timer.start()

    def push(self, velocity: float):
        self._velocity = velocity
        self._ts = self._timer.elapsed()

    def pop(self, decay: float = 0.6) -> float:
        age = self._timer.elapsed() - self._ts
        if age > 300:
            return 0.0
        v = self._velocity * decay * max(0.0, 1.0 - age / 300.0)
        self._velocity = 0.0
        return v

