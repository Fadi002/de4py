# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QApplication, QLineEdit
)
from PySide6.QtCore import Qt, Signal, QRegularExpression
from PySide6.QtGui import (
    QShortcut, QKeySequence, QTextDocument, QSyntaxHighlighter,
    QTextCharFormat, QColor, QFont
)

from de4py.lang import tr
from de4py.lang.keys import MSG_COPIED, BTN_COPY_OUTPUT, LBL_OUTPUT


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#ff79c6")) # Pink
        keyword_format.setFontWeight(QFont.Bold)
        keywords = [
            "and", "as", "assert", "async", "await", "break", "class",
            "continue", "def", "del", "elif", "else", "except", "finally",
            "for", "from", "global", "if", "import", "in", "is", "lambda",
            "nonlocal", "not", "or", "pass", "raise", "return", "try",
            "while", "with", "yield", "None", "True", "False"
        ]
        for word in keywords:
            pattern = QRegularExpression(fr"\b{word}\b")
            self.highlighting_rules.append((pattern, keyword_format))

        class_format = QTextCharFormat()
        class_format.setForeground(QColor("#50fa7b")) # Green
        class_format.setFontWeight(QFont.Bold)
        self.highlighting_rules.append((QRegularExpression(r"\bclass\s+\w+\b"), class_format))

        function_format = QTextCharFormat()
        function_format.setForeground(QColor("#50fa7b")) # Green
        self.highlighting_rules.append((QRegularExpression(r"\bdef\s+\w+\b"), function_format))

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6272a4")) # Muted Blue
        self.highlighting_rules.append((QRegularExpression(r"#.*"), comment_format))

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#f1fa8c")) # Yellow
        self.highlighting_rules.append((QRegularExpression(r"\".*?\""), string_format))
        self.highlighting_rules.append((QRegularExpression(r"'.*?'"), string_format))

        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#bd93f9")) # Purple
        self.highlighting_rules.append((QRegularExpression(r"\b[0-9]+\b"), number_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlighting_rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), format)


class SearchBar(QWidget):
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 2, 10, 2)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Search...")
        layout.addWidget(self.input)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedWidth(30)
        self.close_btn.clicked.connect(self.closed.emit)
        layout.addWidget(self.close_btn)


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

        self.search_bar = SearchBar()
        self.search_bar.hide()
        self.search_bar.input.textChanged.connect(self._on_search_text_changed)
        self.search_bar.closed.connect(self._toggle_search)
        self.main_layout.addWidget(self.search_bar)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.main_layout.addWidget(self.text_edit)

    def _setup_search(self):
        self.search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self.search_shortcut.activated.connect(self._toggle_search)

        self.esc_shortcut = QShortcut(QKeySequence("Esc"), self)
        self.esc_shortcut.activated.connect(self._hide_search)

    def _toggle_search(self):
        if self.search_bar.isVisible():
            self._hide_search()
        else:
            self.search_bar.show()
            self.search_bar.input.setFocus()

    def _hide_search(self):
        self.search_bar.hide()
        self.text_edit.setFocus()
        # Clear extra selections (highlights)
        self.text_edit.setExtraSelections([])

    def _on_search_text_changed(self, text):
        if not text:
            self.text_edit.setExtraSelections([])
            return

        extra_selections = []
        cursor = self.text_edit.document().find(text)

        # First match - scroll to it
        if not cursor.isNull():
            self.text_edit.setTextCursor(cursor)

        while not cursor.isNull():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(Qt.yellow)
            selection.format.setForeground(Qt.black)
            selection.cursor = cursor
            extra_selections.append(selection)
            cursor = self.text_edit.document().find(text, cursor)

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
        """Update strings on language change."""
        if self._title is None:
            self.title_label.setText(tr(LBL_OUTPUT))
        
        if self._has_copy:
            self.copy_btn.setText(tr(BTN_COPY_OUTPUT))
