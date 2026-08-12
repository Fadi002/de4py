# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""Regression tests for overlay visuals.

Covers two past bugs:

1. The PyShell "Force Show Console" ModalOverlay frame drifted ~40px below
   center because paintEvent physically moved a layout-managed widget.
2. The PyLingual TOSDialog frame stayed at (0, 0) because resizing a
   translucent widget during showEvent never re-activated its layout.
3. GlassBlurCache served stale blurs across screen changes because its key
   ignored which screen was visible.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QWidget


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _clean_blur_cache():
    """The blur cache is a shared class-level dict — always restore it so a
    failing test can't pollute the rest of the suite."""
    from de4py.ui.widgets.glass_utils import GlassBlurCache
    yield
    GlassBlurCache._cache.clear()


def _pump(app, seconds=0.25):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.005)


def _center_offset(widget):
    frame = widget.modal_frame
    frame_cy = frame.y() + frame.height() // 2
    overlay_cy = widget.height() // 2
    return frame_cy - overlay_cy


def test_modal_overlay_frame_stays_centered_after_fade_in(qapp):
    """The PyShell show-console modal must settle dead-center — the frame
    must never be nudged off the layout position during the animation."""
    from de4py.ui.widgets.modal_overlay import ModalOverlay

    parent = QWidget()
    parent.resize(1100, 700)
    parent.show()
    qapp.processEvents()

    modal = ModalOverlay("Force Show Console", "Target pid:", "unhide console", parent)
    modal.fade_in()
    _pump(qapp, 0.5)

    assert modal.isVisible()
    assert abs(_center_offset(modal)) <= 2, (
        f"modal frame off-center by {_center_offset(modal)}px "
        f"(frame={modal.modal_frame.geometry()})"
    )

    # Fade out and reopen — the same must hold on a second show.
    modal.fade_out()
    _pump(qapp, 0.5)
    modal.fade_in()
    _pump(qapp, 0.5)
    assert abs(_center_offset(modal)) <= 2

    parent.close()


def test_tos_dialog_frame_stays_centered_after_fade_in(qapp):
    """The PyLingual TOS dialog must center its 500x400 frame even though the
    overlay is translucent and resized during showEvent."""
    from de4py.ui.widgets.pylingual_widgets import TOSConfig, TOSDialog

    parent = QWidget()
    parent.resize(1100, 700)
    parent.show()
    qapp.processEvents()

    tos = TOSDialog(TOSConfig(), parent=parent)
    # QGraphicsOpacityEffect defaults to 0.7 — the widget must start fully
    # transparent so fade_in actually fades from 0.
    assert tos.effect.opacity() == 0.0
    tos.fade_in()
    _pump(qapp, 0.5)

    assert tos.isVisible()
    assert abs(_center_offset(tos)) <= 2, (
        f"TOS frame off-center by {_center_offset(tos)}px "
        f"(frame={tos.modal_frame.geometry()})"
    )
    parent.close()


def test_modal_overlay_renders_visibly(qapp):
    """After fade-in the modal must actually be painted (opacity ~1, backdrop
    dimming present) — guards against the springs never being driven."""
    from de4py.ui.widgets.modal_overlay import ModalOverlay

    parent = QWidget()
    parent.resize(1100, 700)
    parent.show()
    qapp.processEvents()

    modal = ModalOverlay("Force Show Console", "Target pid:", "unhide console", parent)
    modal.fade_in()
    # Springs take ~1.25s to settle — pump generously to avoid timing flake.
    _pump(qapp, 1.5)

    assert modal._opacity_effect.opacity() > 0.9
    assert modal._backdrop_alpha > 50

    parent.close()


def test_glass_blur_cache_invalidated_on_navigation(qapp):
    """Navigating between screens must invalidate the blur cache so overlays
    never reuse a blur captured on a different screen."""
    from de4py.ui.main_window import MainWindow
    from de4py.ui.motion.manager import MotionManager
    from de4py.ui.widgets.glass_utils import GlassBlurCache

    mw = MainWindow()
    try:
        mw.resize(1100, 700)
        mw.show()
        _pump(qapp, 0.5)

        # Open the PyShell modal -> blur of the PyShell screen is cached.
        mw.navigate_to_pyshell()
        _pump(qapp, 0.5)
        pyshell = mw.pyshell_screen
        pyshell._exec_command("ShowConsole")
        _pump(qapp, 0.5)
        assert len(GlassBlurCache._cache) >= 1
        assert GlassBlurCache.is_current(mw)

        # Navigate away -> the cached blur must be dropped.
        mw._navigate_to("pylingual")
        _pump(qapp, 0.5)
        assert not GlassBlurCache.is_current(mw), "stale blur survived navigation"
    finally:
        MotionManager.stop_simulation()
        mw.close()


def test_ai_consent_overlay_centers_after_fade_in(qapp):
    """The AI consent overlay (same machinery as the show-console modal) must
    settle dead-center and stay there across a reopen."""
    from de4py.ui.widgets.ai_consent_overlay import AIConsentOverlay

    parent = QWidget()
    parent.resize(1100, 700)
    parent.show()
    qapp.processEvents()

    overlay = AIConsentOverlay(parent)
    overlay.show_consent("Code will be sent to OpenRouter for analysis.",
                         allow_decline=True)
    overlay.fade_in()
    _pump(qapp, 0.5)
    assert overlay.isVisible()
    assert abs(_center_offset(overlay)) <= 2, (
        f"consent overlay off-center by {_center_offset(overlay)}px"
    )

    overlay.fade_out()
    _pump(qapp, 0.5)
    overlay.fade_in()
    _pump(qapp, 0.5)
    assert abs(_center_offset(overlay)) <= 2
    parent.close()


def test_deobfuscator_cloud_consent_requires_modal(qapp, monkeypatch):
    """An unacknowledged cloud provider must block the run and raise the
    overlay; accepting persists the consent so the next call proceeds."""
    from de4py.config.config import settings
    from de4py.ui.screens.deobfuscator_screen import DeobfuscatorScreen

    old_provider, old_consent = settings.ai_provider, settings.ai_consent
    try:
        settings.ai_provider = "openai"
        settings.ai_consent = {}
        monkeypatch.setattr("de4py.ai.providers.is_local_provider",
                            lambda p: False)
        # _on_consent_accepted calls settings.save() — never touch the real
        # config.json from a test.
        monkeypatch.setattr(settings, "save", lambda: None)

        screen = DeobfuscatorScreen()
        screen.resize(1100, 700)
        screen.show()
        qapp.processEvents()

        screen.ai_enable_checkbox.setChecked(True)
        qapp.processEvents()
        assert screen._maybe_require_consent() is False
        overlay = screen._consent_overlay
        assert overlay is not None and overlay.isVisible()
        assert abs(_center_offset(overlay)) <= 2

        screen._on_consent_accepted()
        _pump(qapp, 0.5)
        assert settings.ai_consent.get("openai") is True
        assert screen._maybe_require_consent() is True
        screen.close()
    finally:
        settings.ai_provider = old_provider
        settings.ai_consent = old_consent


def test_deobfuscator_consent_decline_disables_ai(qapp, monkeypatch):
    """Declining the consent overlay turns AI back off instead of running
    with the user's unacknowledged cloud provider."""
    from de4py.config.config import settings
    from de4py.ui.screens.deobfuscator_screen import DeobfuscatorScreen

    old_provider, old_consent = settings.ai_provider, settings.ai_consent
    try:
        settings.ai_provider = "gemini"
        settings.ai_consent = {}
        monkeypatch.setattr("de4py.ai.providers.is_local_provider",
                            lambda p: False)
        monkeypatch.setattr(settings, "save", lambda: None)

        screen = DeobfuscatorScreen()
        screen.show()
        qapp.processEvents()
        screen.ai_enable_checkbox.setChecked(True)
        qapp.processEvents()
        assert screen._consent_overlay is not None

        screen._on_consent_declined()
        _pump(qapp, 0.5)
        assert screen.ai_enable_checkbox.isChecked() is False
        assert screen._consent_provider is None
        screen.close()
    finally:
        settings.ai_provider = old_provider
        settings.ai_consent = old_consent


def test_glass_blur_cache_capture_respects_force_refresh(qapp):
    """force_refresh=True must bypass the cache (used to prove the key does
    not capture screen identity)."""
    from de4py.ui.widgets.glass_utils import GlassBlurCache

    GlassBlurCache._cache.clear()
    parent = QWidget()
    parent.resize(800, 500)
    parent.show()
    qapp.processEvents()

    first = GlassBlurCache.capture(parent, blur_radius=28, downsample_divisor=2)
    assert first is not None
    assert GlassBlurCache.is_current(parent)

    forced = GlassBlurCache.capture(
        parent, blur_radius=28, downsample_divisor=2, force_refresh=True
    )
    assert forced is not None

    GlassBlurCache._cache.clear()
    parent.close()
