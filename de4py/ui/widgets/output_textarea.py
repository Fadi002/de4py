# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QApplication, QLineEdit, QGraphicsDropShadowEffect
)
from PySide6.QtCore import (
    Qt, Signal, QRegularExpression, QPropertyAnimation,
    QEasingCurve, Property, QRectF, QTimer, QEvent
)
from PySide6.QtGui import (
    QShortcut, QKeySequence, QSyntaxHighlighter,
    QTextCharFormat, QColor, QFont, QPainter, QPen, QPixmap
)
from PySide6.QtSvg import QSvgRenderer

from de4py.lang import tr
from de4py.lang.keys import MSG_COPIED, BTN_COPY_OUTPUT, LBL_OUTPUT


class PythonHighlighter(QSyntaxHighlighter):
    KEYWORDS = (
        "and", "as", "assert", "async", "await", "break", "class",
        "continue", "del", "elif", "else", "except", "finally",
        "for", "from", "global", "if", "import", "in", "is", "lambda",
        "nonlocal", "not", "or", "pass", "raise", "return", "try",
        "while", "with", "yield", "None", "True", "False",
    )

    BUILTINS = (
        "print", "len", "range", "str", "int", "float", "list", "dict",
        "set", "tuple", "type", "super", "open", "input", "isinstance",
        "enumerate", "zip", "map", "filter", "sum", "min", "max", "any",
        "all", "sorted",
    )

    def __init__(self, document):
        super().__init__(document)

        self.rules = []
        self._multiline_string_format = self._format("#f1fa8c")

        self._setup_rules()

    @staticmethod
    def _format(
        color: str,
        bold: bool = False,
        italic: bool = False,
    ) -> QTextCharFormat:
        fmt = QTextCharFormat()

        fmt.setForeground(QColor(color))
        fmt.setFontItalic(italic)

        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)

        return fmt

    def _add_rule(
        self,
        pattern: str,
        text_format: QTextCharFormat,
    ):
        self.rules.append(
            (
                QRegularExpression(pattern),
                text_format,
            )
        )

    def _setup_rules(self):
        keyword_format = self._format("#ff79c6", bold=True)

        for word in self.KEYWORDS:
            self._add_rule(
                fr"\b{word}\b",
                keyword_format,
            )

        builtin_format = self._format("#8be9fd")

        for word in self.BUILTINS:
            self._add_rule(
                fr"\b{word}\b",
                builtin_format,
            )


        self._add_rule(
            r"(?<=\bclass\s)[A-Z]\w*",
            self._format("#50fa7b", bold=True),
        )

        self._add_rule(
            r"\bdef\b",
            self._format("#ff79c6", bold=True),
        )

        self._add_rule(
            r"(?<=\bdef\s)\w+",
            self._format("#8be9fd"),
        )

        self._add_rule(
            r"@[A-Za-z_]\w*",
            self._format("#ffb86c"),
        )

        self._add_rule(
            r"\bself\b",
            self._format("#ffb86c", italic=True),
        )

        self._add_rule(
            r"\b[A-Z][A-Za-z0-9_]*(?=\()",
            self._format("#50fa7b"),
        )

        self._add_rule(
            r"\b\d+(\.\d+)?\b",
            self._format("#bd93f9"),
        )

        self._add_rule(
            r"#.*",
            self._format("#6272a4", italic=True),
        )

        string_format = self._format("#f1fa8c")

        self._add_rule(
            r'"[^"\\]*(\\.[^"\\]*)*"',
            string_format,
        )

        self._add_rule(
            r"'[^'\\]*(\\.[^'\\]*)*'",
            string_format,
        )

        self._add_rule(
            r"\b(True|False|None)\b",
            self._format("#bd93f9", bold=True),
        )

    def highlightBlock(self, text: str):
        for pattern, text_format in self.rules:
            iterator = pattern.globalMatch(text)

            while iterator.hasNext():
                match = iterator.next()

                self.setFormat(
                    match.capturedStart(),
                    match.capturedLength(),
                    text_format,
                )

        self._highlight_multiline_strings(text)

    def _highlight_multiline_strings(self, text: str):
        triple_double = QRegularExpression('"""')
        triple_single = QRegularExpression("'''")

        self._match_multiline(
            text,
            triple_double,
            self._multiline_string_format,
        )

        self._match_multiline(
            text,
            triple_single,
            self._multiline_string_format,
        )

    def _match_multiline(
        self,
        text: str,
        delimiter: QRegularExpression,
        text_format: QTextCharFormat,
    ):
        start = 0

        if self.previousBlockState() != 1:
            match = delimiter.match(text)
            start = match.capturedStart()

        while start >= 0:
            end_match = delimiter.match(text, start + 3)
            end = end_match.capturedStart()

            if end >= 0:
                length = end - start + 3
                self.setCurrentBlockState(0)
            else:
                self.setCurrentBlockState(1)
                length = len(text) - start

            self.setFormat(start, length, text_format)

            match = delimiter.match(text, start + length)
            start = match.capturedStart()


_RESOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resources")
_ICON_PIXMAP_CACHE: dict[str, QPixmap] = {}


def _tinted_icon(name: str, color: QColor, size: int = 16) -> QPixmap:
    key = f"{name}:{color.name()}"
    if key in _ICON_PIXMAP_CACHE:
        return _ICON_PIXMAP_CACHE[key]
    path = os.path.join(_RESOURCES_DIR, f"{name}.svg")
    if not os.path.exists(path):
        return QPixmap(size, size)
    renderer = QSvgRenderer(path)
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(p)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(pix.rect(), color)
    p.end()
    _ICON_PIXMAP_CACHE[key] = pix
    return pix


class _NavCapsule(QWidget):
    prev_clicked = Signal()
    next_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(56, 28)
        self.setObjectName("NavCapsule")
        self.setMouseTracking(True)
        self._hovered = False
        self._pressed_btn = None
        self._opacity = 0.6

        self._bg_idle = QColor(255, 255, 255, 13)
        self._bg_hover = QColor(255, 255, 255, 20)
        self._accent = QColor(2, 135, 207)
        self._border_idle = QColor(self._accent)
        self._border_hover = QColor(self._accent)
        self._divider = QColor(self._accent)
        self._ic_idle = QColor(139, 148, 158)
        self._ic_pressed = QColor(255, 255, 255)

    def _color_prop(name):
        def getter(self):
            return getattr(self, name)
        def setter(self, c):
            setattr(self, name, c)
            self.update()
        return Property(QColor, getter, setter)

    bgIdle = _color_prop("_bg_idle")
    bgHover = _color_prop("_bg_hover")
    accent = _color_prop("_accent")
    borderIdle = _color_prop("_border_idle")
    borderHover = _color_prop("_border_hover")
    divider = _color_prop("_divider")
    iconIdle = _color_prop("_ic_idle")
    iconPressed = _color_prop("_ic_pressed")
    del _color_prop

    def set_opacity(self, val: float):
        self._opacity = val
        self.update()

    def get_opacity(self) -> float:
        return self._opacity

    opacity = Property(float, get_opacity, set_opacity)

    def _which_at(self, pos) -> str:
        return "prev" if pos.x() < self.width() / 2 else "next"

    def _tinted_accent(self, alpha):
        c = QColor(self._accent)
        c.setAlpha(alpha)
        return c

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self._opacity)

        rect = QRectF(self.rect())

        bg = self._bg_hover if self._hovered else self._bg_idle
        border = self._tinted_accent(76 if self._hovered else 38)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 6, 6)

        painter.setPen(QPen(border, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)

        mid = self.width() // 2
        painter.setPen(QPen(self._tinted_accent(25), 1))
        painter.drawLine(mid, 6, mid, self.height() - 6)

        ic_up = self._ic_pressed if self._pressed_btn == "prev" else self._ic_idle
        ic_dn = self._ic_pressed if self._pressed_btn == "next" else self._ic_idle
        icon_y = (self.height() - 14) // 2
        painter.drawPixmap(10, icon_y, _tinted_icon("chevron-up", ic_up, 14))
        painter.drawPixmap(mid + 10, icon_y, _tinted_icon("chevron-down", ic_dn, 14))

        painter.end()

    def mouseMoveEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self._pressed_btn = None
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed_btn = self._which_at(event.position())
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._pressed_btn:
            clicked = self._which_at(event.position())
            if clicked == self._pressed_btn:
                (self.prev_clicked if clicked == "prev" else self.next_clicked).emit()
        self._pressed_btn = None
        self.update()


class _ClearButton(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self.setObjectName("SearchClearBtn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._opacity = 0.0
        self._hovered = False

        self._hover_bg = QColor(255, 80, 80, 38)
        self._icon = QColor(139, 148, 158)
        self._icon_hover = QColor(255, 255, 255)

    def set_opacity(self, val: float):
        self._opacity = val
        self.update()

    def get_opacity(self) -> float:
        return self._opacity

    opacity = Property(float, get_opacity, set_opacity)

    def _get_hover_bg(self):
        return self._hover_bg

    def _set_hover_bg(self, c):
        self._hover_bg = c
        self.update()

    hoverBg = Property(QColor, _get_hover_bg, _set_hover_bg)

    def _get_icon(self):
        return self._icon

    def _set_icon(self, c):
        self._icon = c
        self.update()

    icon = Property(QColor, _get_icon, _set_icon)

    def _get_icon_hover(self):
        return self._icon_hover

    def _set_icon_hover(self, c):
        self._icon_hover = c
        self.update()

    iconHover = Property(QColor, _get_icon_hover, _set_icon_hover)

    def paintEvent(self, event):
        if self._opacity < 0.01:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self._opacity)

        if self._hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._hover_bg)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(2, 2, -2, -2), 6, 6)

        ic = self._icon_hover if self._hovered else self._icon
        painter.drawPixmap(6, 6, _tinted_icon("x", ic, 16))
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._opacity > 0.1:
            self.clicked.emit()

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

class SearchBar(QWidget):
    closed = Signal()
    find_next = Signal()
    find_prev = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFixedHeight(40)
        self.setMinimumWidth(280)
        self.setMaximumWidth(480)
        self.setObjectName("SearchBar")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._hovered = False
        self._focused = False

        self._pill_bg_idle = QColor(24, 28, 36, 242)
        self._pill_bg_hover = QColor(30, 36, 46, 242)
        self._pill_bg_focus = QColor(30, 36, 46, 255)
        self._pill_border_idle = QColor(2, 135, 207, 76)
        self._pill_border_hover = QColor(2, 135, 207, 127)
        self._pill_border_focus = QColor(2, 135, 207, 255)
        self._accent = QColor(2, 135, 207)
        self._ring = QColor(self._accent)
        self._ring_explicit = False
        self._text_muted = QColor(139, 148, 158)

        self._bg_color = QColor(self._pill_bg_idle)
        self._border_color = QColor(self._pill_border_idle)
        self._focus_ring_alpha = 0.0
        self._icon_opacity = 0.5
        self._clear_opacity = 1.0
        self._nav_opacity = 0.6

        self._setup_ui()
        self._setup_animations()
        self._setup_shadow()

        self.input.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.input:
            if event.type() == QEvent.Type.FocusIn:
                self._focused = True
                self._animate_to_state()
            elif event.type() == QEvent.Type.FocusOut:
                self._focused = False
                self._animate_to_state()
        return super().eventFilter(obj, event)

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(44, 0, 12, 0)
        layout.setSpacing(10)

        self.input = QLineEdit()
        self.input.setObjectName("SearchInput")
        self.input.setFrame(False)
        self.input.setPlaceholderText("Search in text...")
        self.input.setFixedHeight(28)
        self.input.setStyleSheet(
            "QLineEdit {"
            "  background: transparent;"
            "  border: none;"
            "  padding: 0;"
            "  min-height: 0;"
            "  color: #ffffff;"
            "  font-size: 14px;"
            "  font-weight: 500;"
            "  selection-background-color: #0287CF;"
            "}"
            "QLineEdit:focus {"
            "  background: transparent;"
            "  border: none;"
            "}"
            "QLineEdit:hover {"
            "  background: transparent;"
            "  border: none;"
            "}"
        )
        self.input.returnPressed.connect(self.find_next.emit)

        self.count_label = QLabel("")
        self.count_label.setObjectName("SearchCounter")
        self.count_label.setFixedWidth(52)
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.nav_capsule = _NavCapsule()
        self.nav_capsule.prev_clicked.connect(self.find_prev.emit)
        self.nav_capsule.next_clicked.connect(self.find_next.emit)

        self.clear_btn = _ClearButton()
        self.clear_btn.set_opacity(1.0)
        self.clear_btn.clicked.connect(self.closed.emit)

        layout.addWidget(self.input, 1)
        layout.addWidget(self.count_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.nav_capsule, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.clear_btn, 0, Qt.AlignmentFlag.AlignVCenter)

    def _setup_animations(self):
        self._bg_anim = QPropertyAnimation(self, b"bg_color")
        self._bg_anim.setDuration(120)
        self._bg_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._border_anim = QPropertyAnimation(self, b"border_color")
        self._border_anim.setDuration(120)
        self._border_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._ring_anim = QPropertyAnimation(self, b"focus_ring_alpha")
        self._ring_anim.setDuration(180)
        self._ring_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._icon_anim = QPropertyAnimation(self, b"icon_opacity")
        self._icon_anim.setDuration(150)
        self._icon_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._clear_anim = QPropertyAnimation(self, b"clear_opacity")
        self._clear_anim.setDuration(150)
        self._clear_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._nav_anim = QPropertyAnimation(self, b"nav_opacity")
        self._nav_anim.setDuration(150)
        self._nav_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _setup_shadow(self):
        self._shadow = QGraphicsDropShadowEffect()
        self._shadow.setBlurRadius(24)
        self._shadow.setOffset(0, 6)
        self._shadow.setColor(QColor(0, 0, 0, 90))
        self.setGraphicsEffect(self._shadow)

    def _set_shadow_focus(self, focused: bool):
        if focused:
            self._shadow.setBlurRadius(28)
            self._shadow.setOffset(0, 8)
            c = QColor(self._accent)
            c.setAlpha(50)
            self._shadow.setColor(c)
        else:
            self._shadow.setBlurRadius(24)
            self._shadow.setOffset(0, 6)
            self._shadow.setColor(QColor(0, 0, 0, 90))

    def _start(self, anim, start, end):
        anim.stop()
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.start()

    def _animate_to_state(self):
        if self._focused:
            bg = QColor(self._pill_bg_focus)
            border = QColor(self._pill_border_focus)
            ring = 1.0
            icon = 0.9
            nav = 0.85
            self._set_shadow_focus(True)
        elif self._hovered:
            bg = QColor(self._pill_bg_hover)
            border = QColor(self._pill_border_hover)
            ring = 0.0
            icon = 0.7
            nav = 0.75
            self._set_shadow_focus(False)
        else:
            bg = QColor(self._pill_bg_idle)
            border = QColor(self._pill_border_idle)
            ring = 0.0
            icon = 0.5
            nav = 0.6
            self._set_shadow_focus(False)

        self._start(self._bg_anim, self._bg_color, bg)
        self._start(self._border_anim, self._border_color, border)
        self._start(self._ring_anim, self._focus_ring_alpha, ring)
        self._start(self._icon_anim, self._icon_opacity, icon)
        self._start(self._nav_anim, self._nav_opacity, nav)

    def _color_prop(name):
        def getter(self):
            return getattr(self, name)
        def setter(self, c):
            setattr(self, name, c)
            self.update()
        return Property(QColor, getter, setter)

    pillBgIdle = _color_prop("_pill_bg_idle")
    pillBgHover = _color_prop("_pill_bg_hover")
    pillBgFocus = _color_prop("_pill_bg_focus")
    pillBorderIdle = _color_prop("_pill_border_idle")
    pillBorderHover = _color_prop("_pill_border_hover")
    pillBorderFocus = _color_prop("_pill_border_focus")
    accent = _color_prop("_accent")
    textMuted = _color_prop("_text_muted")
    del _color_prop

    def _get_ring(self):
        return self._ring

    def _set_ring(self, c):
        self._ring = QColor(c)
        self._ring_explicit = True
        self.update()

    ring = Property(QColor, _get_ring, _set_ring)

    def _get_bg_color(self):
        return self._bg_color

    def _set_bg_color(self, c):
        self._bg_color = c
        self.update()

    bg_color = Property(QColor, _get_bg_color, _set_bg_color)

    def _get_border_color(self):
        return self._border_color

    def _set_border_color(self, c):
        self._border_color = c
        self.update()

    border_color = Property(QColor, _get_border_color, _set_border_color)

    def _get_focus_ring_alpha(self):
        return self._focus_ring_alpha

    def _set_focus_ring_alpha(self, v):
        self._focus_ring_alpha = v
        self.update()

    focus_ring_alpha = Property(float, _get_focus_ring_alpha, _set_focus_ring_alpha)

    def _get_icon_opacity(self):
        return self._icon_opacity

    def _set_icon_opacity(self, v):
        self._icon_opacity = v
        self.update()

    icon_opacity = Property(float, _get_icon_opacity, _set_icon_opacity)

    def _get_clear_opacity(self):
        return self._clear_opacity

    def _set_clear_opacity(self, v):
        self._clear_opacity = v
        self.clear_btn.set_opacity(v)
        self.update()

    clear_opacity = Property(float, _get_clear_opacity, _set_clear_opacity)

    def _get_nav_opacity(self):
        return self._nav_opacity

    def _set_nav_opacity(self, v):
        self._nav_opacity = v
        self.nav_capsule.set_opacity(v)
        self.update()

    nav_opacity = Property(float, _get_nav_opacity, _set_nav_opacity)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        r = 8.0

        if self._focus_ring_alpha > 0.01:
            ring_source = self._ring if self._ring_explicit else self._accent

            ring_rect = rect.adjusted(-3, -3, 3, 3)
            ring_c = QColor(ring_source)
            ring_c.setAlphaF(self._focus_ring_alpha * 0.25)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(ring_c)
            painter.drawRoundedRect(ring_rect, r + 3, r + 3)

            ring_rect2 = rect.adjusted(-1.5, -1.5, 1.5, 1.5)
            ring_c2 = QColor(ring_source)
            ring_c2.setAlphaF(self._focus_ring_alpha * 0.12)
            painter.setBrush(ring_c2)
            painter.drawRoundedRect(ring_rect2, r + 1.5, r + 1.5)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._bg_color)
        painter.drawRoundedRect(rect, r, r)

        top_line = QColor(255, 255, 255, 12)
        if self._hovered:
            top_line = QColor(255, 255, 255, 18)
        if self._focused:
            top_line = QColor(255, 255, 255, 22)
        painter.setPen(QPen(top_line, 1))
        painter.drawLine(r + 1, 1, rect.width() - r - 1, 1)

        painter.setPen(QPen(self._border_color, 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), r, r)

        ic = QColor(self._accent if self._focused else self._text_muted)
        ic.setAlphaF(self._icon_opacity)
        painter.setOpacity(1.0)
        icon_y = (self.height() - 16) // 2
        painter.drawPixmap(16, icon_y, _tinted_icon("search", ic, 16))

        painter.end()

    def enterEvent(self, event):
        self._hovered = True
        self._animate_to_state()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._animate_to_state()
        super().leaveEvent(event)

    def focusInEvent(self, event):
        self._focused = True
        self._animate_to_state()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self._focused = False
        self._animate_to_state()
        super().focusOutEvent(event)



    def set_count(self, count: int, total: int):
        error = total == 0 and count == 0 and bool(self.input.text())
        self.count_label.setText("0 / 0" if error else f"{count} / {total}" if total > 0 else "")
        if error:
            self.count_label.setStyleSheet("color: #ff6464; font-size: 12px; font-weight: 500;")
        else:
            self.count_label.setStyleSheet("color: #8b949e; font-size: 12px; font-weight: 500;")



class OutputTextArea(QWidget):
    def __init__(self, title: str = None, show_copy: bool = True, parent=None):
        super().__init__(parent)
        self._title = title
        self._has_copy = show_copy
        self._setup_ui()
        self._setup_search()
        self.highlighter = PythonHighlighter(self.text_edit.document())

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(5)

        header_layout = QHBoxLayout()
        title = self._title if self._title is not None else tr(LBL_OUTPUT)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("OutputTitle")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        if self._has_copy:
            self.copy_btn = QPushButton(tr(BTN_COPY_OUTPUT))
            self.copy_btn.clicked.connect(self._copy_to_clipboard)
            header_layout.addWidget(self.copy_btn)

        self.main_layout.addLayout(header_layout)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.main_layout.addWidget(self.text_edit)

        self.search_bar = SearchBar(self)
        self.search_bar.hide()
        self.search_bar.input.textChanged.connect(self._on_search_text_changed)
        self.search_bar.closed.connect(self._hide_search)
        self.search_bar.find_next.connect(self._find_next)
        self.search_bar.find_prev.connect(self._find_prev)

    def _setup_search(self):
        self.search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self.search_shortcut.activated.connect(self._toggle_search)

        self.esc_shortcut = QShortcut(QKeySequence("Esc"), self)
        self.esc_shortcut.activated.connect(self._hide_search)

        self._search_matches = []
        self._search_index = -1

    def _toggle_search(self):
        if self.search_bar.isVisible():
            self._hide_search()
        else:
            self.search_bar.show()
            self.search_bar.raise_()
            QTimer.singleShot(0, self._position_search_bar)
            self.search_bar.input.setFocus()
            text = self.search_bar.input.text()
            if text:
                self._on_search_text_changed(text)

    def _position_search_bar(self):
        vp = self.text_edit.viewport()
        vp_w = vp.width()
        vp_pos = vp.mapTo(self, vp.rect().topLeft())

        bar_w = min(480, max(280, vp_w - 24))
        self.search_bar.setFixedWidth(bar_w)

        x = vp_pos.x() + max(12, (vp_w - bar_w) // 2)
        y = vp_pos.y() + 12
        self.search_bar.move(x, y)
        self.search_bar.raise_()

    def _hide_search(self):
        self.search_bar.hide()
        self.search_bar.count_label.setText("")
        self.search_bar.count_label.setStyleSheet("")
        self._search_matches = []
        self._search_index = -1
        self.text_edit.setFocus()
        self.text_edit.setExtraSelections([])

    def _on_search_text_changed(self, text):
        self._search_matches = []
        self._search_index = -1

        if not text:
            self.text_edit.setExtraSelections([])
            self.search_bar.set_count(0, 0)
            return

        cursor = self.text_edit.document().find(text)
        while not cursor.isNull():
            self._search_matches.append((cursor.selectionStart(), cursor.selectionEnd()))
            cursor = self.text_edit.document().find(text, cursor)

        if self._search_matches:
            self._search_index = 0
            self._scroll_to_match()
        else:
            self.search_bar.set_count(0, 0)

        self._highlight_matches()

    def _find_next(self):
        if not self._search_matches:
            return
        self._search_index = (self._search_index + 1) % len(self._search_matches)
        self._scroll_to_match()
        self._highlight_matches()

    def _find_prev(self):
        if not self._search_matches:
            return
        self._search_index = (self._search_index - 1) % len(self._search_matches)
        self._scroll_to_match()
        self._highlight_matches()

    def _scroll_to_match(self):
        if not self._search_matches or self._search_index < 0:
            return
        start, end = self._search_matches[self._search_index]
        cursor = self.text_edit.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, cursor.MoveMode.KeepAnchor)
        self.text_edit.setTextCursor(cursor)
        self.search_bar.set_count(self._search_index + 1, len(self._search_matches))

    def _highlight_matches(self):
        text = self.search_bar.input.text()
        if not text or not self._search_matches:
            self.text_edit.setExtraSelections([])
            return

        extra_selections = []
        current_start, current_end = self._search_matches[self._search_index] if self._search_index >= 0 else (None, None)

        for start, end in self._search_matches:
            selection = QTextEdit.ExtraSelection()
            if start == current_start and end == current_end:
                selection.format.setBackground(QColor(255, 166, 0, 180))
                selection.format.setForeground(QColor(255, 255, 255))
            else:
                selection.format.setBackground(QColor(88, 166, 255, 60))
                selection.format.setForeground(QColor(255, 255, 255))

            cursor = self.text_edit.textCursor()
            cursor.setPosition(start)
            cursor.setPosition(end, cursor.MoveMode.KeepAnchor)
            selection.cursor = cursor
            extra_selections.append(selection)

        self.text_edit.setExtraSelections(extra_selections)

    def _copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text_edit.toPlainText())
        main_window = self.window()
        if hasattr(main_window, 'show_notification'):
            main_window.show_notification("success", tr(MSG_COPIED))

    def set_text(self, text: str):
        self.text_edit.setPlainText(text)

    def append_text(self, text: str):
        self.text_edit.append(text)

    def clear(self):
        self.text_edit.clear()

    def get_text(self) -> str:
        return self.text_edit.toPlainText()

    def retranslate_ui(self):
        if self._title is None:
            self.title_label.setText(tr(LBL_OUTPUT))

        if self._has_copy:
            self.copy_btn.setText(tr(BTN_COPY_OUTPUT))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.search_bar.isVisible():
            self._position_search_bar()