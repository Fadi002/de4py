# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""Regression tests for AnimatedButton's QGraphicsDropShadowEffect.

Covers a past perf bug: every AnimatedButton permanently attached an
*enabled* QGraphicsDropShadowEffect even while fully idle (blurRadius=0,
transparent color). QGraphicsEffect forces Qt to route every paint through
an offscreen compositing buffer regardless of whether the effect is visually
doing anything, roughly doubling per-paint cost for idle buttons (measured
~2x on 50 buttons under QT_QPA_PLATFORM=offscreen).

The fix disables the effect while idle and only enables it while actually
glowing. This was verified pixel-identical to the old always-enabled
behavior, but only once the button has a real parent background — grabbing
an isolated, parentless button is NOT representative: the effect's offscreen
buffer composites the button's rounded corners against transparency instead
of a real background, which only matches the disabled path once something
is actually behind it to composite onto.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_shadow_effect_starts_disabled(qapp):
    from de4py.ui.widgets.core_animations import AnimatedButton

    btn = AnimatedButton("hi")
    try:
        assert btn._shadow.isEnabled() is False
    finally:
        btn.deleteLater()


def test_shadow_effect_toggles_with_glow(qapp):
    from de4py.ui.widgets.core_animations import AnimatedButton

    btn = AnimatedButton("hi")
    try:
        btn._material.drive("hover", 1.0)
        for _ in range(300):
            btn._material.tick(1 / 60)
            if btn._material.hover.is_settled():
                break

        assert btn._material.glow_intensity > 0.01
        assert btn._shadow.isEnabled() is True

        btn._material.drive("hover", 0.0)
        for _ in range(300):
            btn._material.tick(1 / 60)
            if btn._material.hover.is_settled():
                break

        assert btn._material.glow_intensity <= 0.01
        assert btn._shadow.isEnabled() is False
    finally:
        btn.deleteLater()


def test_idle_rendering_matches_old_always_enabled_effect(qapp):
    """The actual regression check: a disabled shadow must composite to the
    same pixels as the old always-enabled/blur=0/transparent-color effect,
    once the button is parented against a real background (matches real
    usage — every AnimatedButton in the app has a real parent)."""
    from de4py.ui.widgets.core_animations import AnimatedButton

    def grab_parented(configure_button):
        parent = QWidget()
        parent.resize(160, 60)
        parent.setAutoFillBackground(True)
        pal = parent.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(30, 32, 38))
        parent.setPalette(pal)

        btn = AnimatedButton("Click me", parent)
        btn.move(10, 10)
        btn.resize(140, 40)
        configure_button(btn)

        parent.show()
        qapp.processEvents()
        img = parent.grab().toImage()
        parent.close()
        parent.deleteLater()
        return img

    def force_old_always_enabled_idle_state(b):
        b._shadow.setEnabled(True)
        b._shadow.setBlurRadius(0)
        b._shadow.setOffset(0, 2)
        b._shadow.setColor(QColor(0, 0, 0, 0))

    img_new = grab_parented(lambda b: None)
    img_old = grab_parented(force_old_always_enabled_idle_state)

    assert img_new.size() == img_old.size()
    w, h = img_new.width(), img_new.height()

    n_diff = 0
    first_diff = None
    for y in range(h):
        for x in range(w):
            c_new = img_new.pixelColor(x, y).getRgb()
            c_old = img_old.pixelColor(x, y).getRgb()
            if c_new != c_old:
                n_diff += 1
                if first_diff is None:
                    first_diff = (x, y, c_new, c_old)

    assert n_diff == 0, f"{n_diff}/{w * h} pixels differ; first at {first_diff}"
