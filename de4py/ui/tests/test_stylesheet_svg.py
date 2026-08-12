# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""Regression tests for the QSS check.svg injection.

Covers the bug where load_stylesheet substituted {CHECK_SVG} with a
file:/// URL. QSS url() hands that string to the icon factory as a
filename; on Windows the URL is not an absolute path, so Qt resolved it
against the CWD and produced paths like
".../de4py/file:/C:/.../check.svg" (visible as qt.svg load errors on
every checked QCheckBox — e.g. the settings page).
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _check_svg_url(qss):
    """Extract the url(...) value used by QCheckBox::indicator:checked."""
    match = re.search(r"QCheckBox::indicator:checked\s*\{[^}]*image:\s*url\(([^)]*)\)", qss)
    return match.group(1).strip() if match else None


def test_stylesheet_replaces_check_svg_with_plain_path(qapp):
    """The {CHECK_SVG} placeholder must become an absolute path, not a URL."""
    from de4py.main import load_stylesheet

    qss = load_stylesheet(qapp)

    assert qss, "stylesheet should load from dark_theme.qss"
    assert "{CHECK_SVG}" not in qss, "placeholder was never substituted"

    url = _check_svg_url(qss)
    assert url, "QCheckBox::indicator:checked must reference the checkmark"
    assert not url.startswith("file:"), (
        f"file:/// URLs are treated as CWD-relative filenames by QSS url(); "
        f"got {url!r}"
    )
    assert url.replace("/", os.sep).startswith(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_check_svg_url_loads_into_icon(qapp):
    """The substituted path must actually load as an SVG icon."""
    from de4py.main import load_stylesheet

    qss = load_stylesheet(qapp)
    url = _check_svg_url(qss)
    assert url, "no checkmark url found in stylesheet"

    icon = QIcon(url)
    assert not icon.isNull(), f"check.svg failed to load from {url!r}"
