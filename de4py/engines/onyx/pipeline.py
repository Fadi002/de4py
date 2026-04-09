# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Main deobfuscation pipeline — Onyx engine.
"""

import subprocess
import shutil
import sys
import time
import psutil
import threading
import gc
from typing import Optional, Callable

from de4py.engines.onyx.triage import TriageEngine, TriageResult
from de4py.engines.onyx.decompiler import Decompiler
from de4py.engines.onyx.string_decoder import StringDecoder
from de4py.engines.onyx.ast_cleaner import ASTCleaner
from de4py.engines.onyx.flow_deobfuscator import FlowDeobfuscator
from de4py.engines.onyx.match_case_deobfuscator import MatchCaseDeobfuscator
from de4py.engines.onyx.lambda_normalizer import LambdaChainDeobfuscator
from de4py.engines.onyx.proxy_cleaner import ProxyCleaner
from de4py.engines.onyx.vm_lifter import VMLifter
from de4py.engines.onyx.rule_renamer import RuleRenamer
from de4py.engines.onyx.formatter import Formatter
from de4py.engines.onyx.llm_renamer import LLMRenamer
from de4py.engines.onyx.validator import Validator, ValidationResult


class PipelineResult:
    def __init__(self):
        self.original:   str = ""
        self.cleaned:    str = ""
        self.log:        list = []
        self.triage:     Optional[TriageResult] = None
        self.validation: Optional[ValidationResult] = None

    @property
    def success(self) -> bool:
        return self.validation is not None and self.validation.syntax_ok


class Pipeline:
    def __init__(
        self,
        use_llm:       bool  = True,
        llm_model:     str   = "qwen2.5-coder:1.5b",
        annotate:      bool  = False,
        llm_threshold: float = 7.0,
    ):
        self.use_llm       = use_llm
        self.annotate      = annotate
        self.llm_threshold = llm_threshold
        self.llm_config    = self._get_llm_config()

        if self.use_llm:
            t, r, v = (self.llm_config[k] for k in ("tier","ram_gb","vram_gb"))
            print(f"[Pipeline] HW Tier: {t} (RAM:{r}GB VRAM:{v}GB)")
            if self.llm_config["num_gpu"] == 0:
                print("[Pipeline] CPU-only mode (num_gpu=0)")

        self.triage    = TriageEngine()
        self.decompiler= Decompiler()
        self.decoder   = StringDecoder()
        self.cleaner   = ASTCleaner()
        self.flow      = FlowDeobfuscator()
        self.match_sm  = MatchCaseDeobfuscator()
        self.lambda_n  = LambdaChainDeobfuscator()
        self.proxy     = ProxyCleaner()
        self.vm_lifter = VMLifter()
        self.renamer   = RuleRenamer()
        self.formatter = Formatter()
        self.llm       = LLMRenamer(
            model     = llm_model,
            num_ctx   = self.llm_config["num_ctx"],
            num_batch = self.llm_config["num_batch"],
            num_gpu   = self.llm_config["num_gpu"],
        ) if use_llm else None
        self.validator = Validator()

    def _get_llm_config(self) -> dict:
        ram_gb = round(psutil.virtual_memory().total / (1024**3))
        vram_gb = 0
        try:
            if shutil.which("nvidia-smi"):
                out = subprocess.check_output(
                    ["nvidia-smi","--query-gpu=memory.total","--format=csv,noheader,nounits"],text=True)
                lines = [l.strip() for l in out.split("\n") if l.strip().isdigit()]
                if lines: vram_gb = round(int(lines[0])/1024)
        except Exception:
            pass
        if   vram_gb < 2 or ram_gb < 8:   tier,ctx,batch = "Low",  512, 128
        elif vram_gb < 4 or ram_gb < 16:  tier,ctx,batch = "Mid",  1024,256
        else:                              tier,ctx,batch = "High", 4096,512
        return {"tier":tier,"ram_gb":ram_gb,"vram_gb":vram_gb,
                "num_ctx":ctx,"num_batch":batch,"num_gpu":0 if vram_gb<4 else -1}

    def run(self, source: str, filename: str = "file.py") -> PipelineResult:
        result          = PipelineResult()
        result.original = source
        current         = source
        log             = []
        return self._run_inner(result, current, log, source, filename)

    def _run_stage(self, name: str, fn: Callable[[str], str], source: str) -> str:
        if name not in _THREADED_STAGE_NAMES:
            return fn(source)
        return _run_source_transform_in_thread(name, fn, source)

    def _run_inner(self, result: 'PipelineResult', current: str, log: list,
                   source: str, filename: str) -> 'PipelineResult':

        # ── 0: Decompile .pyc ─────────────────────────────────────────────────
        if filename.endswith(".pyc"):
            _log("[Pipeline] Decompiling .pyc...")
            try:
                current = self.decompiler.decompile(filename)
                log.append("decompiler")
            except Exception as e:
                log.append(f"decompiler_failed:{e}")

        # ── 1: Triage ─────────────────────────────────────────────────────────
        _log("[Pipeline] Triage...")
        try:
            triage = self.triage.analyze(current, filename)
        except Exception as e:
            _log(f"[Pipeline] Triage crashed: {e} — using defaults")
            from de4py.engines.onyx.triage import TriageResult
            triage = TriageResult(score=5.0, route="rule_rename",
                                 flags=[f"triage_crash:{e}"])
        result.triage = triage
        log.append(f"triage:score={triage.score:.1f}:route={triage.route}")
        _log(f"[Pipeline] Score={triage.score:.1f}/10.0  Route={triage.route}")

        # ── 2: VM Lifter ──────────────────────────────────────────────────────
        try:
            has_vm = self.vm_lifter._has_vm_class_source(current)
        except Exception:
            has_vm = False
        if has_vm:
            print("[Pipeline] VM bytecode detected — lifting...")
            prev = current
            try:
                lifted = self.vm_lifter.deobfuscate(current)
            except Exception as e:
                log.append(f"vm_lifter_failed:{e}")
                _log(f"[Pipeline] VM lifter error: {e}")
            else:
                if lifted != prev:
                    current = lifted
                    log.append("vm_lifter")
                    _log(f"[Pipeline] VM lift: {_diff(prev, current)}")

        # ── 3: Pre-pass: state machine linearization on raw source ──────────────
        # MUST run before any alias/constant folding — flow_deobfuscator inlines
        # the state variable as a constant which prevents the simulator from tracing.
        print("[Pipeline] Pre-pass: state machine linearization...")
        prev = current
        try:
            current = self._run_stage("match_sm_prepass", self.match_sm.deobfuscate, current)
        except Exception as e:
            current = prev
            log.append(f"match_sm_prepass_failed:{e}")
        else:
            if current != prev:
                log.append("match_sm_prepass")
                _log(f"[Pipeline] SM pre-pass: {_diff(prev, current)}")

        # ── 4: Convergence loop ───────────────────────────────────────────────
        print("[Pipeline] Starting convergence loop...")
        for pass_num in range(1, 10):
            changed = False
            stages = [
                ("ast_cleaner",     lambda s: self.cleaner.clean(s)),   # state-machine linearize first
                ("match_sm",        lambda s: self.match_sm.deobfuscate(s)),
                ("proxy_cleaner",   lambda s: self.proxy.deobfuscate(s)),
                ("string_decoder",  lambda s: self.decoder.decode_all(s)),
                ("lambda_norm",     lambda s: self.lambda_n.deobfuscate(s)),
                ("flow_deobf",      lambda s: self.flow.deobfuscate(s)),
                ("ast_cleaner2",    lambda s: self.cleaner.clean(s)),   # clean up after flow
            ]
            for name, fn in stages:
                prev = current
                try:
                    current = self._run_stage(name, fn, current)
                except Exception as e:
                    current = prev
                    log.append(f"{name}_failed:{e}")
                    _log(f"[Pipeline]  Pass {pass_num} {name} error: {e}")
                else:
                    if current != prev:
                        log.append(f"pass{pass_num}:{name}")
                        changed = True
                        _log(f"[Pipeline]  Pass {pass_num} {name}: {_diff(prev, current)}")

            if not changed:
                _log(f"[Pipeline] Converged at pass {pass_num}")
                break

        # ── 5: Rule rename ────────────────────────────────────────────────────
        if triage.route in ("rule_rename", "llm_rename"):
            prev = current
            try:
                current = self.renamer.rename(current)
            except Exception as e:
                current = prev
                log.append(f"rule_renamer_failed:{e}")
            else:
                if current != prev:
                    log.append("rule_renamer")
                    _log(f"[Pipeline] Rule rename: {_diff(prev, current)}")

        # ── 6: LLM rename ─────────────────────────────────────────────────────
        if (self.use_llm and self.llm is not None
                and triage.route == "llm_rename"
                and triage.score >= self.llm_threshold):
            prev = current
            try:
                current = self.llm.process_file(current, annotate=self.annotate)
            except Exception as e:
                current = prev
                log.append(f"llm_renamer_failed:{e}")
            else:
                if current != prev:
                    log.append("llm_renamer")
                    _log("[Pipeline] LLM renaming complete")

        # ── 7: Final AST clean ────────────────────────────────────────────────
        prev = current
        try:
            current = self._run_stage("ast_cleaner_final", self.cleaner.clean, current)
            if current != prev:
                log.append("ast_cleaner_final")
        except Exception:
            current = prev

        # ── 8: Format ─────────────────────────────────────────────────────────
        _log("[Pipeline] Formatting...")
        prev = current
        try:
            current = self.formatter.format(current)
            if current != prev:
                log.append("formatter")
        except Exception as e:
            current = prev
            log.append(f"formatter_failed:{e}")

        # ── 9: Validate ───────────────────────────────────────────────────────
        _log("[Pipeline] Validating...")
        validation = self.validator.validate(source, current)

        # Syntax fix attempt — AST-based structural repair first, LLM as last resort
        if not validation.syntax_ok:
            _log(f"[Pipeline] Syntax error: {validation.error}")
            _log("[Pipeline] Attempting AST structural repair...")
            try:
                fixed = _ast_structural_repair(current)
            except Exception as e:
                _log(f"[Pipeline] AST repair crashed: {e}")
                fixed = None
            if fixed and self.validator.check_syntax_only(fixed)[0]:
                _log("[Pipeline] AST repair succeeded!")
                current = fixed
                validation = self.validator.validate(source, current)
                log.append("syntax_fixed_by_ast_repair")
            elif self.use_llm and self.llm is not None:
                _log("[Pipeline] AST repair insufficient — trying LLM syntax fix...")
                try:
                    fixed = self.llm.fix_syntax(current, validation.error)
                    if fixed and self.validator.check_syntax_only(fixed)[0]:
                        _log("[Pipeline] LLM syntax fix succeeded!")
                        current = fixed
                        validation = self.validator.validate(source, current)
                        log.append("syntax_fixed_by_llm")
                    else:
                        _log("[Pipeline] LLM syntax fix failed.")
                except Exception as e:
                    _log(f"[Pipeline] LLM syntax fix error: {e}")
            else:
                _log("[Pipeline] No syntax fix available.")

        result.validation = validation

        if not validation.syntax_ok:
            log.append("validation_failed:kept_broken")
            _log("[Pipeline] WARNING: Syntax error remains. Returning best-effort result.")
        else:
            _log("[Pipeline] PASSED")
            for w in (validation.warnings or []):
                _log(f"[Pipeline]  Warning: {w}")

        result.cleaned = current
        result.log     = log
        return result



class _StageThreadError(RuntimeError):
    """Raised when a threaded stage fails inside the worker thread."""


_THREADED_STAGE_NAMES = {
    "match_sm_prepass",
    "ast_cleaner",
    "match_sm",
    "proxy_cleaner",
    "string_decoder",
    "lambda_norm",
    "flow_deobf",
    "ast_cleaner2",
    "ast_cleaner_final",
}

_STAGE_THREAD_STACK_BYTES = 64 * 1024 * 1024


def _run_source_transform_in_thread(name: str, fn: Callable[[str], str], source: str) -> str:
    result_box = {"value": source, "error": None}

    def _worker() -> None:
        try:
            result_box["value"] = fn(source)
        except Exception as exc:
            result_box["error"] = exc

    old_stack = None
    stack_applied = False
    try:
        try:
            old_stack = threading.stack_size()
            threading.stack_size(_STAGE_THREAD_STACK_BYTES)
            stack_applied = True
        except (ValueError, RuntimeError):
            old_stack = None
            stack_applied = False

        thread = threading.Thread(target=_worker, name=f"onyx-{name}", daemon=True)
        thread.start()
        thread.join()

        if result_box["error"] is not None:
            raise _StageThreadError(f"{name} worker failed: {result_box['error']}")

        return result_box["value"]
    finally:
        if stack_applied and old_stack is not None:
            try:
                threading.stack_size(old_stack)
            except (ValueError, RuntimeError):
                pass
        gc.collect()


def _log(msg: str) -> None:
    """Print a log message, ignoring encoding errors on Windows consoles."""
    try:
        print(msg)
    except (UnicodeEncodeError, OSError):
        try:
            print(msg.encode('ascii', errors='replace').decode('ascii'))
        except Exception:
            pass


def _diff(before: str, after: str) -> str:
    try:
        d = len(before) - len(after)
        p = abs(d) / max(len(before), 1) * 100
        arrow = "-" if d > 0 else "+"
        return f"{arrow}{abs(d)} chars ({p:.1f}%)"
    except Exception:
        return "(diff unavailable)"


def _ast_structural_repair(source: str) -> str:
    """
    Repair syntax errors caused by deobfuscation transforms.
    Primary fix: 'expected an indented block after X on line N' -> insert pass.
    Falls back to: AST empty-body insertion, bad-line strip, truncation.
    """
    import ast as _ast, re as _re

    def _ok(s):
        try: _ast.parse(s); return True
        except SyntaxError: return False

    def _err(s):
        try: _ast.parse(s); return None
        except SyntaxError as e: return e

    def _insert_pass(s, e):
        if not e.msg or 'expected an indented block' not in e.msg:
            return s
        m = _re.search(r'on line (\d+)', e.msg)
        header_lineno = int(m.group(1)) if m else max(1, (e.lineno or 2) - 1)
        lines = s.splitlines(keepends=True)
        idx = header_lineno - 1
        if idx < 0 or idx >= len(lines):
            return s
        h = lines[idx]
        indent = len(h) - len(h.lstrip())
        new_lines = lines[:idx + 1] + [' ' * (indent + 4) + 'pass\n'] + lines[idx + 1:]
        return ''.join(new_lines)

    def _fix_ast_bodies(s):
        try: tree = _ast.parse(s)
        except SyntaxError: return s
        changed = False
        for node in _ast.walk(tree):
            for field in ('body', 'orelse', 'finalbody'):
                val = getattr(node, field, None)
                if isinstance(val, list) and not val:
                    if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef,
                                         _ast.ClassDef, _ast.If, _ast.While,
                                         _ast.For, _ast.With, _ast.Try,
                                         _ast.ExceptHandler)) and field == 'body':
                        val.append(_ast.Pass())
                        changed = True
        if not changed:
            return s
        try:
            _ast.fix_missing_locations(tree)
            return _ast.unparse(tree)
        except Exception:
            return s

    def _strip_line(s, e):
        lines = s.splitlines(keepends=True)
        idx = (e.lineno or 1) - 1
        if 0 <= idx < len(lines):
            c = ''.join(lines[:idx] + lines[idx + 1:])
            if _ok(c): return c
        return s

    def _truncate(s):
        lines = s.splitlines(keepends=True)
        for end in range(len(lines), max(0, len(lines) - 40), -1):
            c = ''.join(lines[:end])
            if _ok(c): return c
        return s

    result = source
    for _ in range(10):
        if _ok(result):
            return result
        e = _err(result)
        prev = result
        result = _insert_pass(result, e)
        if result != prev: continue
        result = _fix_ast_bodies(result)
        if result != prev: continue
        result = _strip_line(result, e)
        if result != prev: continue
        result = _truncate(result)
        if result != prev: continue
        break

    return result if _ok(result) else source
