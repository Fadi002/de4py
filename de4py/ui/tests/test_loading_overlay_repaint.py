# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""Regression tests for LoadingOverlay's steady-state spin cost.

Covers a past perf bug: the spinner timer called bare self.update() every
16ms for the entire lifetime of any operation showing the overlay — a
full-window repaint (blurred background pixmap + backdrop fill + conical
gradient) for what is visually just a small rotating ring. The fix scopes
_tick()'s update() to the spinner's bounding rect once the overlay is fully
visible, and disables the QGraphicsOpacityEffect once the fade-in settles
(a disabled-but-still-attached effect, toggled the same way as
AnimatedButton's shadow, correctly honors a small update() rect — an
enabled one forces a full-widget repaint on its first paint after being
(re-)attached, though not on every subsequent one).

Both changes were verified against the real backing store via
screen.grabWindow() rather than QWidget.grab()/.repaint() — both of the
latter force a fresh full render regardless of what update() was called
with, so they cannot see a partial-repaint regression (a stale, un-erased
trail of the spinner's previous position) at all."""

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


def _settled_overlay(qapp, size=(300, 200)):
    from de4py.ui.widgets.loading_overlay import LoadingOverlay

    parent = QWidget()
    parent.resize(*size)
    parent.setAutoFillBackground(True)
    pal = parent.palette()
    pal.setColor(QPalette.ColorRole.Window, QColor(18, 19, 23))
    parent.setPalette(pal)
    parent.show()
    qapp.processEvents()

    overlay = LoadingOverlay(parent)
    overlay._lock_events = True
    overlay.setGeometry(parent.rect())
    overlay._backdrop_alpha = 160.0
    overlay._opacity_effect.setOpacity(1.0)
    overlay._opacity_effect.setEnabled(False)  # simulates a settled fade-in
    overlay.show()
    qapp.processEvents()
    overlay._spin_timer.stop()  # only the test's explicit _tick() calls move the angle
    return parent, overlay


def _grab_backing_store(widget):
    win = widget.window()
    screen = win.screen() or QApplication.primaryScreen()
    return screen.grabWindow(int(win.winId())).toImage()


def test_spin_tick_uses_a_bounded_rect_not_the_full_widget(qapp):
    parent, overlay = _settled_overlay(qapp)
    try:
        bounds = overlay._spinner_bounds()
        full = overlay.rect()
        assert bounds.width() < full.width()
        assert bounds.height() < full.height()
        assert full.contains(bounds), "spinner bounds must stay within the widget"
    finally:
        parent.close()


def test_opacity_effect_disabled_while_settled_reenabled_on_fade(qapp):
    parent, overlay = _settled_overlay(qapp)
    try:
        assert overlay._opacity_effect.isEnabled() is False

        overlay.fade_out()
        assert overlay._opacity_effect.isEnabled() is True
    finally:
        parent.close()


def test_settled_disabled_effect_renders_identically_to_enabled(qapp):
    """opacity=1.0 is the identity multiplier for QGraphicsOpacityEffect, so
    disabling it while settled must not change a single pixel — unlike
    AnimatedButton's QGraphicsDropShadowEffect, which measurably did."""
    from de4py.ui.widgets.loading_overlay import LoadingOverlay

    def grab(enabled):
        parent = QWidget()
        parent.resize(300, 200)
        parent.setAutoFillBackground(True)
        pal = parent.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(18, 19, 23))
        parent.setPalette(pal)
        parent.show()
        qapp.processEvents()

        overlay = LoadingOverlay(parent)
        overlay._lock_events = True
        overlay.setGeometry(parent.rect())
        overlay._backdrop_alpha = 160.0
        overlay._opacity_effect.setOpacity(1.0)
        overlay._opacity_effect.setEnabled(enabled)
        overlay._angle = 47.0
        overlay.show()
        qapp.processEvents()
        overlay._spin_timer.stop()
        overlay.update(overlay.rect())
        qapp.processEvents()

        img = _grab_backing_store(parent)
        parent.close()
        parent.deleteLater()
        qapp.processEvents()
        return img

    img_enabled = grab(True)
    img_disabled = grab(False)

    assert img_enabled.size() == img_disabled.size()
    w, h = img_enabled.width(), img_enabled.height()
    n_diff = sum(
        1
        for y in range(h)
        for x in range(w)
        if img_enabled.pixelColor(x, y).getRgb() != img_disabled.pixelColor(x, y).getRgb()
    )
    assert n_diff == 0


def test_partial_repaint_leaves_no_stale_spinner_trail(qapp):
    """The real regression check: a single _tick() (real code path, scoped
    update()) must produce a backing store identical to what a full repaint
    at the same angle would show — an undersized bounds rect would leave the
    previous frame's ring/head-dot un-erased instead."""
    angles_to_check = [0.0, 47.0, 90.0, 133.0, 180.0, 226.0, 270.0, 314.0, 354.0]

    for start_angle in angles_to_check:
        parent, overlay = _settled_overlay(qapp)
        overlay._angle = start_angle

        overlay._tick()
        qapp.processEvents()
        partial_img = _grab_backing_store(parent)

        overlay.update(overlay.rect())
        qapp.processEvents()
        full_img = _grab_backing_store(parent)

        assert partial_img.size() == full_img.size()
        w, h = partial_img.width(), partial_img.height()
        n_diff = sum(
            1
            for y in range(h)
            for x in range(w)
            if partial_img.pixelColor(x, y).getRgb() != full_img.pixelColor(x, y).getRgb()
        )
        assert n_diff == 0, f"stale pixels at start_angle={start_angle}: {n_diff} differ"

        parent.close()
        parent.deleteLater()
        qapp.processEvents()
