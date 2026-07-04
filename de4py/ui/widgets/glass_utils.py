from __future__ import annotations

from collections import OrderedDict
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPixmap, QColor
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsBlurEffect,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QWidget,
)

_CACHE_MAX_SIZE = 8
_LUMINANCE_TARGET = 0.45


class GlassBlurCache:
    _cache: OrderedDict[tuple[int, int, int, int, int], QPixmap] = OrderedDict()

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
                cls._cache.move_to_end(key)
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
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                scaled_blur_radius = max(8, blur_radius // divisor)
            else:
                working = snapshot
                scaled_blur_radius = blur_radius

            contrast, lum = cls._analyze_image(working)
            adjusted_radius = int(scaled_blur_radius * (0.85 + contrast * 0.3))

            blur_effect = QGraphicsBlurEffect()
            blur_effect.setBlurRadius(adjusted_radius)

            scene = QGraphicsScene()
            item = QGraphicsPixmapItem(working)
            item.setGraphicsEffect(blur_effect)
            scene.addItem(item)

            blurred_small = QPixmap(working.size())
            blurred_small.fill(Qt.GlobalColor.transparent)
            painter = QPainter(blurred_small)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            scene.render(painter, QRectF(blurred_small.rect()), QRectF(working.rect()))
            painter.end()

            blurred = (
                blurred_small.scaled(width, height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
                if divisor > 1
                else blurred_small
            )

            if lum > 0:
                ratio = lum / _LUMINANCE_TARGET
                if abs(ratio - 1.0) > 0.15:
                    alpha = int(min(30, abs(ratio - 1.0) * 40))
                    overlay_color = QColor(0, 0, 0, alpha) if ratio > 1.0 else QColor(255, 255, 255, alpha // 2)
                    overlay_painter = QPainter(blurred)
                    overlay_painter.fillRect(blurred.rect(), overlay_color)
                    overlay_painter.end()

            blurred.setDevicePixelRatio(dpr)

            if len(cls._cache) >= _CACHE_MAX_SIZE:
                cls._cache.popitem(last=False)
            cls._cache[key] = blurred
            return blurred
        finally:
            if hidden:
                exclude_widget.show()

    @classmethod
    def _analyze_image(cls, pixmap: QPixmap) -> tuple[float, float]:
        """
        Single-pass image analysis. Returns (contrast, avg_luminance) in [0, 1].
        Samples the image at 8x8 pixels. Uses Welford-style running mean+variance
        to avoid a second pass.
        """
        img = pixmap.toImage().scaled(8, 8, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        if img.isNull():
            return 0.5, 0.5

        n = img.width() * img.height()
        if n == 0:
            return 0.5, 0.5

        total = 0.0
        total_sq = 0.0
        for y in range(img.height()):
            for x in range(img.width()):
                px = img.pixel(x, y)          # ARGB packed int
                r = (px >> 16) & 0xFF         # red channel
                g = (px >> 8)  & 0xFF         # green channel
                b =  px        & 0xFF         # blue channel
                lum = r * 0.299 + g * 0.587 + b * 0.114
                total += lum
                total_sq += lum * lum

        mean = total / n
        variance = (total_sq / n) - (mean * mean)
        contrast = min(1.0, (max(0.0, variance) ** 0.5) / 128.0)
        avg_lum = mean / 255.0
        return contrast, avg_lum


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
        win_id = int(window.winId())
        for key in cls._cache:
            if key[0] == win_id and key[1] == width and key[2] == height:
                return True
        return False
