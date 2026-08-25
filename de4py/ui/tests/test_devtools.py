# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""Regression tests for the rebuilt devtools module.

Covers the honest paint-rate tracker, the repaint offender tracker, the
api_call feed signal, and panel construction (exactly 4 tabs).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _pump(app, ms=50):
    import time
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


def test_qcolor_rgba_parses_alpha_suffix(qapp):
    from de4py.ui.constants import qcolor_rgba, COLOR_ACCENT_DIM, COLOR_TEXT_DIM

    amber = qcolor_rgba("#ffb02022")
    assert amber.name() == "#ffb020"
    assert amber.alpha() == 0x22

    dim = qcolor_rgba(COLOR_ACCENT_DIM)
    assert dim.name() == "#0287cf"
    assert dim.alpha() == 0x55

    text_dim = qcolor_rgba(COLOR_TEXT_DIM)
    assert text_dim.name() == "#ffffff"
    assert text_dim.alpha() == 0xAA

    plain = qcolor_rgba("#1c1c1c")
    assert plain.name() == "#1c1c1c"
    assert plain.alpha() == 255


def test_paint_rate_accumulates_ticks(qapp):
    from types import SimpleNamespace

    from de4py.ui.devtools.context import context
    from de4py.ui.devtools.metrics.paintrate import paint_rate

    prev = getattr(context, "devtools_panel", None)
    context.devtools_panel = SimpleNamespace(isVisible=lambda: True)
    try:
        paint_rate._frame_count = 0
        for _ in range(5):
            paint_rate.tick()
        paint_rate._report()
        assert paint_rate.rate == 5
        assert paint_rate.samples[-1] == 5
    finally:
        context.devtools_panel = prev


def test_paint_rate_samples_capped(qapp):
    from types import SimpleNamespace

    from de4py.ui.devtools.context import context
    from de4py.ui.devtools.metrics.paintrate import paint_rate

    prev = getattr(context, "devtools_panel", None)
    context.devtools_panel = SimpleNamespace(isVisible=lambda: True)
    try:
        paint_rate.samples.clear()
        for _ in range(35):
            paint_rate._report()
        assert len(paint_rate.samples) == 30
    finally:
        context.devtools_panel = prev


def test_repaint_tracker_top(qapp):
    from PySide6.QtWidgets import QLabel
    from de4py.ui.devtools.metrics.repaint import repaint_tracker

    w = QLabel("x")
    for _ in range(3):
        repaint_tracker.track(w)
    top = repaint_tracker.top(1)
    assert top and top[0][0] is w and top[0][1] >= 3


def test_bus_api_call_signal(qapp):
    from de4py.ui.devtools.event_bus import bus

    seen = []
    bus.api_call.connect(lambda method, endpoint: seen.append((method, endpoint)))
    bus.api_call.emit("GET", "/api/test")
    assert seen == [("GET", "/api/test")]


def test_panel_builds_four_tabs(qapp):
    from de4py.ui.devtools.panel import DeveloperPanel

    panel = DeveloperPanel()
    assert panel.tabs.count() == 4
    labels = [panel.tabs.tabText(i) for i in range(4)]
    assert labels == ["INSPECT", "PERF", "NETWORK", "LOGS"]
    panel.close()


def test_panel_shrinks_without_snapping_back(qapp):
    from de4py.ui.devtools.panel import DeveloperPanel

    panel = DeveloperPanel()
    try:
        panel.show()
        _pump(qapp)

        floor = panel.minimumSizeHint().width()
        assert floor < 350, f"panel minimum floor still {floor}px"

        panel.resize(280, 420)
        _pump(qapp)

        inspect = panel.tabs.widget(0)
        detail = inspect.detail
        assert detail.width() > 0
        assert detail.height() > 0
        assert inspect.detail_layout.minimumSize().width() <= detail.width() + 2, (
            "detail content must not overflow the pane"
        )
    finally:
        panel.close()


def test_inspect_detail_text_is_readable(qapp):
    from PySide6.QtGui import QColor

    from de4py.ui.constants import COLOR_ACCENT_DIM, COLOR_BG_DARK, COLOR_TEXT
    from de4py.ui.devtools.panel import DeveloperPanel

    def contrast(fg, bg):
        def lum(c):
            r, g, b = c.redF(), c.greenF(), c.blueF()

            def ch(v):
                return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

            return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)

        a, b = lum(fg), lum(bg)
        hi, lo = max(a, b), min(a, b)
        return (hi + 0.05) / (lo + 0.05)

    panel = DeveloperPanel()
    try:
        inspect = panel.tabs.widget(0)
        assert inspect._detail_values, "detail rows missing"
        bg = QColor(COLOR_BG_DARK)
        for value in inspect._detail_values:
            stylesheet = value.styleSheet()
            assert COLOR_ACCENT_DIM not in stylesheet, (
                "detail values must not use the dim accent (1.5:1 contrast)"
            )
            color = QColor(COLOR_TEXT)
            assert contrast(color, bg) >= 4.5
            assert stylesheet.startswith(f"color: {COLOR_TEXT}")
    finally:
        panel.close()


def test_panel_scrollbar_accent_tinted(qapp):
    from de4py.ui.devtools.panel import DeveloperPanel

    panel = DeveloperPanel()
    try:
        qss = panel.styleSheet()
        assert "rgba(2, 135, 207, 0.55)" in qss, "scrollbar handle must be accent-tinted"
        assert "QScrollBar:horizontal" in qss, "horizontal scrollbar styling missing"
        assert "QScrollBar::handle:vertical:hover" in qss
        assert "QScrollBar::handle:horizontal:hover" in qss
    finally:
        panel.close()


def test_inspector_live_edit_applies(qapp):
    from PySide6.QtWidgets import QLabel

    from de4py.ui.devtools.panel import DeveloperPanel

    panel = DeveloperPanel()
    try:
        inspect = panel.tabs.widget(0)
        target = QLabel("hello")
        target.setObjectName("target_label")
        inspect.show_widget_info(target)

        inspect.object_name.setText("renamed_label")
        inspect.text_edit.setText("changed text")
        _pump(qapp, 400)
        assert target.objectName() == "renamed_label"
        assert target.text() == "changed text"
    finally:
        panel.close()


def test_inspector_color_field_applies(qapp):
    from PySide6.QtWidgets import QLabel

    from de4py.ui.devtools.panel import DeveloperPanel

    panel = DeveloperPanel()
    try:
        inspect = panel.tabs.widget(0)
        target = QLabel("hello")
        target.setStyleSheet("font-weight: bold;")
        inspect.show_widget_info(target)

        inspect.color_edit.setText("#ff0000")
        _pump(qapp, 400)
        qss = target.styleSheet()
        assert "color: #ff0000" in qss
        assert "font-weight: bold" in qss
    finally:
        panel.close()


def test_inspector_live_edit_reset(qapp):
    from PySide6.QtWidgets import QLabel

    from de4py.ui.devtools.panel import DeveloperPanel

    panel = DeveloperPanel()
    try:
        inspect = panel.tabs.widget(0)
        target = QLabel("hello")
        target.setObjectName("target_label")
        inspect.show_widget_info(target)

        inspect.object_name.setText("renamed")
        inspect.qss_edit.setPlainText("color: #ff0000;")
        _pump(qapp, 400)
        assert target.objectName() == "renamed"

        inspect.btn_reset.click()
        _pump(qapp, 50)
        assert target.objectName() == "target_label"
        assert target.styleSheet() == ""
        assert target.text() == "hello"
    finally:
        panel.close()
