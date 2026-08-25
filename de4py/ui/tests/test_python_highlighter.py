# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""Regression tests for PythonHighlighter.

Covers a past perf bug: KEYWORDS and BUILTINS were each matched by one
QRegularExpression per word (59 separate globalMatch() passes per
highlightBlock() call) instead of one alternation regex per group. The
collapse must not change a single highlighted character — rule order matters
here because later rules overwrite earlier ones on overlapping spans (e.g.
"True"/"False"/"None" get re-colored purple-bold by a rule that runs after
the keyword rule, and keywords inside a "# comment" must stay comment-colored
rather than keyword-colored).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


SNIPPET = (
    "class Foo:\n"
    "    @staticmethod\n"
    "    def bar(self):\n"
    "        # a comment with if and pass inside\n"
    "        x = 42\n"
    "        y = \"a string\"\n"
    "        print(len(y))\n"
    "        return True and self.bar\n"
)


def _highlighted_document(text):
    from PySide6.QtGui import QTextDocument
    from de4py.ui.widgets.output_textarea import PythonHighlighter

    doc = QTextDocument()
    highlighter = PythonHighlighter(doc)
    doc.setPlainText(text)
    highlighter.rehighlight()
    return doc, highlighter


def _fmt_at(doc, source_text, substr, occurrence=0):
    """PythonHighlighter.setFormat() writes to the block's QTextLayout
    additional-formats list (paint-time overlay) — QTextCursor.charFormat()
    reads the stored character format instead and always sees the default,
    so lookups must walk block.layout().formats() directly. The FormatRange's
    .format is only valid while the layout it came from is still alive, so
    extract plain values before returning rather than the format object
    itself."""
    idx = -1
    for _ in range(occurrence + 1):
        idx = source_text.index(substr, idx + 1)
    block = doc.findBlock(idx)
    offset = idx - block.position()
    layout = block.layout()
    for fr in layout.formats():
        if fr.start <= offset < fr.start + fr.length:
            fmt = fr.format
            return (fmt.foreground().color().name(), fmt.fontWeight(), fmt.fontItalic())
    raise ValueError(f"no format range covers offset {offset} in block {block.text()!r}")


def test_keyword_and_builtin_rules_use_one_alternation_each(qapp):
    """Regression guard: rule count must not scale with word-list size —
    one rule per KEYWORDS/BUILTINS word was the actual bottleneck."""
    from de4py.ui.widgets.output_textarea import PythonHighlighter

    doc, highlighter = _highlighted_document("pass\n")
    assert len(highlighter.rules) < len(PythonHighlighter.KEYWORDS) + len(PythonHighlighter.BUILTINS)


def test_keyword_and_builtin_colors(qapp):
    doc, _ = _highlighted_document(SNIPPET)

    color, weight, _ = _fmt_at(doc, SNIPPET, "class")
    assert color == "#ff79c6"
    assert weight == QFont.Weight.Bold

    color, _, _ = _fmt_at(doc, SNIPPET, "def")
    assert color == "#ff79c6"

    color, _, _ = _fmt_at(doc, SNIPPET, "return")
    assert color == "#ff79c6"

    color, _, _ = _fmt_at(doc, SNIPPET, "print")
    assert color == "#8be9fd"

    color, _, _ = _fmt_at(doc, SNIPPET, "len")
    assert color == "#8be9fd"


def test_class_name_def_name_decorator_self(qapp):
    doc, _ = _highlighted_document(SNIPPET)

    color, _, _ = _fmt_at(doc, SNIPPET, "Foo")
    assert color == "#50fa7b"

    color, _, _ = _fmt_at(doc, SNIPPET, "@staticmethod")
    assert color == "#ffb86c"

    color, _, _ = _fmt_at(doc, SNIPPET, "bar")
    assert color == "#8be9fd"

    color, _, italic = _fmt_at(doc, SNIPPET, "self")
    assert color == "#ffb86c"
    assert italic is True


def test_number_string_comment(qapp):
    doc, _ = _highlighted_document(SNIPPET)

    color, _, _ = _fmt_at(doc, SNIPPET, "42")
    assert color == "#bd93f9"

    color, _, _ = _fmt_at(doc, SNIPPET, '"a string"')
    assert color == "#f1fa8c"

    color, _, italic = _fmt_at(doc, SNIPPET, " if ")
    assert color == "#6272a4"
    assert italic is True


def test_true_false_none_override_wins_over_keyword_rule(qapp):
    """"True" is in KEYWORDS (pink) but a later dedicated rule re-colors
    True/False/None purple-bold. The collapsed keyword rule must stay in
    its original list position so this overwrite order survives."""
    doc, _ = _highlighted_document(SNIPPET)

    color, weight, _ = _fmt_at(doc, SNIPPET, "True")
    assert color == "#bd93f9"
    assert weight == QFont.Weight.Bold


def test_keyword_inside_comment_stays_comment_colored(qapp):
    """"if" and "pass" appear inside a comment; the comment rule runs after
    the keyword rule and must win, or the collapse changed overwrite order."""
    doc, _ = _highlighted_document(SNIPPET)

    color, _, _ = _fmt_at(doc, SNIPPET, "pass", occurrence=0)
    assert color == "#6272a4"


def test_highlighting_survives_a_real_multi_thousand_line_file(qapp):
    """Stress test on a real, already-checked-in source file — must complete
    without raising and must still produce a sane number of format runs."""
    from de4py.ui.widgets.output_textarea import PythonHighlighter

    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    stress_path = os.path.join(repo_root, "de4py", "engines", "onyx", "safe_eval.py")
    with open(stress_path, "r", encoding="utf-8") as f:
        text = f.read()
    assert text.count("\n") > 500

    doc, highlighter = _highlighted_document(text)

    total_runs = 0
    block = doc.firstBlock()
    while block.isValid():
        layout = block.layout()
        if layout is not None:
            total_runs += len(layout.formats())
        block = block.next()
    assert total_runs > 0
