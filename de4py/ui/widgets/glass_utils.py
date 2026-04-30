from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPixmap, QImage, QColor
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsBlurEffect,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QWidget,
)


class GlassBlurCache:
    _cache: dict[tuple[int, int, int, int, int], QPixmap] = {}

    @classmethod
    def capture(
        cls,
        window: QWidget,
        *,
        exclude_widget: QWidget | None = None,
        blur_radius: int = 25,
        downsample_divisor: int = 2,
        force_refresh: bool = False,
    ) -> QPixmap | None:
        if not window:
            return None

        width = max(1, window.width())
        height = max(1, window.height())
        key = (int(window.winId()), width, height, blur_radius, downsample_divisor)
        if not force_refresh and key in cls._cache:
            cached = cls._cache[key]
            if not cached.isNull():
                return cached

        hidden = False
        if exclude_widget and exclude_widget.isVisible():
            hidden = True
            exclude_widget.hide()

        try:
            screen = window.screen() or QApplication.primaryScreen()
            if not screen:
                return None

            snapshot = screen.grabWindow(int(window.winId()), 0, 0, width, height)
            if snapshot.isNull():
                return None

            dpr = max(1.0, snapshot.devicePixelRatio())

            divisor = max(1, downsample_divisor)
            if divisor > 1:
                working = snapshot.scaled(
                    max(1, snapshot.width() // divisor),
                    max(1, snapshot.height() // divisor),
                    Qt.IgnoreAspectRatio,
                    Qt.SmoothTransformation,
                )
                scaled_blur_radius = max(8, blur_radius // divisor)
            else:
                working = snapshot
                scaled_blur_radius = blur_radius

            contrast = cls._estimate_contrast(working)
            adjusted_radius = int(scaled_blur_radius * (0.85 + contrast * 0.3))

            blur_effect = QGraphicsBlurEffect()
            blur_effect.setBlurRadius(adjusted_radius)

            scene = QGraphicsScene()
            item = QGraphicsPixmapItem(working)
            item.setGraphicsEffect(blur_effect)
            scene.addItem(item)

            blurred_small = QPixmap(working.size())
            blurred_small.fill(Qt.transparent)
            painter = QPainter(blurred_small)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            scene.render(painter, QRectF(blurred_small.rect()), QRectF(working.rect()))
            painter.end()

            blurred = (
                blurred_small.scaled(width, height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                if divisor > 1
                else blurred_small
            )

            lum = cls._average_luminance(blurred_small)
            if lum > 0:
                target_lum = max(0.3, min(0.7, 0.45))
                ratio = lum / target_lum if target_lum > 0 else 1.0
                if abs(ratio - 1.0) > 0.15:
                    alpha = int(min(30, abs(ratio - 1.0) * 40))
                    overlay_color = QColor(0, 0, 0, alpha) if ratio > 1.0 else QColor(255, 255, 255, alpha // 2)
                    p = QPainter(blurred)
                    p.fillRect(blurred.rect(), overlay_color)
                    p.end()

            blurred.setDevicePixelRatio(dpr)
            cls._cache[key] = blurred
            return blurred
        finally:
            if hidden:
                exclude_widget.show()

    @classmethod
    def _estimate_contrast(cls, pixmap: QPixmap) -> float:
        img = pixmap.toImage().scaled(8, 8, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        if img.isNull():
            return 0.5
        values = []
        for y in range(img.height()):
            for x in range(img.width()):
                c = QColor(img.pixel(x, y))
                values.append(c.red() * 0.299 + c.green() * 0.587 + c.blue() * 0.114)
        if not values:
            return 0.5
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        normalized = min(1.0, (variance ** 0.5) / 128.0)
        return normalized

    @classmethod
    def _average_luminance(cls, pixmap: QPixmap) -> float:
        img = pixmap.toImage().scaled(4, 4, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        if img.isNull():
            return 0.5
        total = 0.0
        count = 0
        for y in range(img.height()):
            for x in range(img.width()):
                c = QColor(img.pixel(x, y))
                total += (c.red() * 0.299 + c.green() * 0.587 + c.blue() * 0.114) / 255.0
                count += 1
        return total / max(1, count)

    @classmethod
    def invalidate(cls, window: QWidget | None = None):
        if not window:
            cls._cache.clear()
            return

        win_id = int(window.winId())
        stale_keys = [key for key in cls._cache if key[0] == win_id]
        for key in stale_keys:
            cls._cache.pop(key, None)

    @classmethod
    def is_current(cls, window: QWidget) -> bool:
        width = max(1, window.width())
        height = max(1, window.height())
        for key in cls._cache:
            if key[0] == int(window.winId()) and key[1] == width and key[2] == height:
                return True
        return False
