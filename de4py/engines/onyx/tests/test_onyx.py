# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import ast
import os

import pytest

from de4py.engines.onyx.pipeline import Pipeline


def _run_pipeline(src, mode="aggressive"):
    r = Pipeline(use_llm=False, engine_options={
        "enabled": True, "mode": mode}).run(src, filename="test.py")
    return r.cleaned


class TestSandbox:
    def test_no_exec_escape(self):
        from de4py.engines.onyx.safe_eval import safe_eval_source
        ok, _ = safe_eval_source("__import__('os').system('echo pwned')")
        assert not ok

    def test_no_dunder_access(self):
        from de4py.engines.onyx.safe_eval import safe_eval_source
        ok, _ = safe_eval_source("().__class__.__bases__[0].__subclasses__()")
        assert not ok

    def test_open_not_available(self):
        from de4py.engines.onyx.safe_eval import safe_eval_source
        ok, _ = safe_eval_source("open('/etc/passwd')")
        assert not ok

    def test_pure_expr_evaluates(self):
        from de4py.engines.onyx.safe_eval import safe_eval_source
        ok, val = safe_eval_source("1 + 2")
        assert ok and val == 3


class TestPipeline:
    def test_plain_code_unchanged(self):
        src = "x = 1\nprint(x)\n"
        out = _run_pipeline(src)
        assert len(out) > 0
        ast.parse(out)

    def test_obfuscated_code_processed(self):
        src = "_t = 'hello'\n_t2 = _t.upper()\nprint(_t2)\n"
        out = _run_pipeline(src)
        assert len(out) > 0

    def test_output_is_valid_python(self):
        src = "x = 1\ny = x * 2 + 0\nif True:\n    print(y)\n"
        out = _run_pipeline(src)
        ast.parse(out)


class TestRegression:
    def test_identity_ops_folded(self):
        out = _run_pipeline("y = x + 0\nz = y * 1\n")
        assert "+ 0" not in out and "* 1" not in out

    def test_dead_code_after_return(self):
        out = _run_pipeline("def f():\n    return 1\n    print('dead')\n")
        assert "'dead'" not in out

    def test_lambda_shell_reduced(self):
        out = _run_pipeline("x = (lambda a: a + 1)(5)\nprint(x)\n")
        assert "(lambda" not in out or "lambda a" not in out

    def test_string_decode_b64(self):
        out = _run_pipeline(
            "import base64\ns = base64.b64decode('aGVsbG8=').decode()\n")
        assert "b64decode" not in out or "aGVsbG8" not in out
