# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import ast
import logging
import re
import sys
import threading
import gc
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional
from colorama import Fore, Style

from de4py.engines.onyx.framework.context import PassConfig, PassContext
from de4py.engines.onyx.framework.events import render_explain
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

logger = logging.getLogger(__name__)

_STAGE_THREAD_STACK_BYTES = 64 * 1024 * 1024
_STAGE_TIMEOUT_SECONDS = 60
# Lambda-obfuscated samples nest thousands of levels deep; every recursive
# walker (unparse, transformers, deepcopy) needs matching headroom. Python
# 3.11+ allocates frames on the heap, so this costs C-stack nothing.
_STAGE_RECURSION_LIMIT = 1_000_000


def _default_ai_enabled() -> bool:
    try:
        from de4py.config.config import settings
        return bool(settings.ai_enabled)
    except Exception:
        return False


def _default_ai_feature(key: str) -> bool:
    try:
        from de4py.config.config import settings
        return bool(getattr(settings, key, False))
    except Exception:
        return False


def _resolve_ai_config():
    try:
        from de4py.ai.client import resolve_ai_config
        return resolve_ai_config()
    except Exception:
        return None


def _run_source_transform_in_thread(name: str, fn: Callable[[str], str], source: str) -> str:
    # AST passes recurse once per nesting level; heavily obfuscated input blows the
    # default 8MB stack long before Python's recursion limit is reached, so each
    # transform runs on a thread with a much larger stack.
    result = {}

    def worker():
        try:
            sys.setrecursionlimit(_STAGE_RECURSION_LIMIT)
            result["value"] = fn(source)
        except Exception as exc:
            result["error"] = exc

    try:
        previous_stack = threading.stack_size(_STAGE_THREAD_STACK_BYTES)
    except (ValueError, RuntimeError):
        previous_stack = None

    try:
        thread = threading.Thread(target=worker, name=f"onyx-{name}", daemon=True)
        thread.start()
        thread.join(_STAGE_TIMEOUT_SECONDS)
        if thread.is_alive():
            raise TimeoutError(f"stage '{name}' exceeded {_STAGE_TIMEOUT_SECONDS}s")
    finally:
        if previous_stack is not None:
            threading.stack_size(previous_stack)

    if "error" in result:
        raise result["error"]
    return result["value"]


@dataclass
class PipelineResult:
    original: str = ""
    cleaned: str = ""
    log: List[str] = field(default_factory=list)
    triage: Optional[TriageResult] = None
    validation: Optional[ValidationResult] = None
    ai_summary: str = ""
    explain_text: str = ""
    stats: dict = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.validation is not None and self.validation.syntax_ok


class Pipeline:
    def __init__(
        self,
        use_llm:       Optional[bool] = None,
        llm_model:     Optional[str]  = None,
        annotate:      Optional[bool] = None,
        llm_threshold: float          = 7.0,
        ai_config:     Optional[Any]  = None,
        ai_explain:    Optional[bool] = None,
        ai_simplify:   Optional[bool] = None,
        engine_options: Optional[dict] = None,
    ):
        if use_llm is None:
            use_llm = _default_ai_enabled()
        self.use_llm       = use_llm
        self.annotate      = annotate if annotate is not None else _default_ai_feature("ai_annotate")
        self.ai_explain    = ai_explain if ai_explain is not None else _default_ai_feature("ai_explain")
        self.ai_simplify   = ai_simplify if ai_simplify is not None else _default_ai_feature("ai_simplify")
        self.llm_threshold = llm_threshold

        if self.use_llm:
            cfg = ai_config or _resolve_ai_config()
            if cfg is not None and llm_model:
                cfg.model = llm_model
            self.llm = LLMRenamer(cfg)
        else:
            self.llm = None
        self.engine_config = PassConfig.from_options(engine_options)

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
        self.validator = Validator()

        self._stages = [
            ("proxy_cleaner",  self.proxy.deobfuscate),
            ("string_decoder", self.decoder.decode_all),
            ("ast_cleaner",    self.cleaner.clean),
            ("match_sm",       self.match_sm.deobfuscate),
            ("lambda_norm",    self.lambda_n.deobfuscate),
            ("flow_deobf",     self.flow.deobfuscate),
            ("ast_cleaner2",   self.cleaner.clean),
        ]

    def _run_guarded(self, name: str, fn, source: str, log: List[str]) -> str:
        """Deep-recursion transforms must never run on the caller's small
        stack: a hostile tree can overflow it natively and kill the whole
        host process. Everything recursive goes through the big-stack
        watchdog thread instead."""
        prev = source
        try:
            candidate = _run_source_transform_in_thread(name, fn, source)
        except Exception as e:
            log.append(f"{name}_failed:{e}")
            return prev
        if candidate != prev:
            log.append(name)
            _log(f"[Pipeline] {name}: {_diff(prev, candidate)}")
        return candidate

    def _run_framework_pass(self, source: str, result: PipelineResult,
                            log: List[str]) -> str:
        """Two sequential passes with independent stage threads:
        1. Structural (unbind + deflate) unlocks the tree
        2. Simplification (iife, junk, flow, copy-prop, wrappers)

        Each pass gets its own deadline so slow rules in one pass
        can't starve the other."""
        import ast as _ast
        from de4py.engines.onyx.framework.governor import run_governor
        from de4py.engines.onyx.framework.rules import RuleRegistry
        from de4py.engines.onyx.transforms.junk_statements import JunkStatementsRule
        from de4py.engines.onyx.transforms.flow_junk import default_flow_rules
        from de4py.engines.onyx.transforms.copy_propagation import (
            LocalCopyPropagationRule,
        )
        from de4py.engines.onyx.transforms.inline_wrappers import (
            default_wrapper_rules,
        )
        from de4py.engines.onyx.transforms.lambda_reduce import (
            default_lambda_rules,
        )
        from de4py.engines.onyx.transforms.builtin_alias import (
            BuiltinAliasResolveRule,
        )
        from de4py.engines.onyx.transforms.getattr_resolve import (
            GetattrResolveRule,
        )
        from de4py.engines.onyx.transforms.identity_ops import (
            default_identity_rules,
        )
        from de4py.engines.onyx.transforms.ycombinator import (
            FixpointRenameRule,
        )
        from de4py.engines.onyx.transforms.proxy_kill import (
            default_proxy_rules,
        )
        from de4py.engines.onyx.transforms.primitive_rename import (
            PrimitiveRenameRule,
        )
        from de4py.engines.onyx.transforms.ring_peel import (
            CpsFunctionDeflateRule,
            CpsUnbindRule,
        )

        try:
            frame_tree = _ast.parse(source)
        except SyntaxError:
            return source
        fw_ctx = PassContext(source=source, tree=frame_tree,
                             config=self.engine_config)

        structural = RuleRegistry()
        structural.register(CpsUnbindRule(), CpsFunctionDeflateRule())

        simplification = RuleRegistry()
        simplification.register(*default_lambda_rules())
        simplification.register(JunkStatementsRule())
        simplification.register(*default_flow_rules())
        simplification.register(LocalCopyPropagationRule())
        simplification.register(BuiltinAliasResolveRule())
        simplification.register(*default_wrapper_rules())
        simplification.register(*default_proxy_rules())
        simplification.register(*default_identity_rules())
        simplification.register(GetattrResolveRule())
        simplification.register(PrimitiveRenameRule())
        simplification.register(FixpointRenameRule())

        def _gov(reg, text):
            dl = max(10.0, float(_STAGE_TIMEOUT_SECONDS) - 15.0)
            run_governor(fw_ctx, reg, deadline_s=dl)
            return _ast.unparse(fw_ctx.tree)

        prev = source
        for label, reg in (("structural", structural),
                           ("simplification", simplification)):
            _log(f"[Pipeline] Framework {label} pass...")
            pass_input = prev
            try:
                candidate = _run_source_transform_in_thread(
                    f"fw_{label}", lambda txt, r=reg: _gov(r, txt), prev)
            except Exception as e:
                log.append(f"{label}_failed:{e}")
                continue
            if candidate != pass_input:
                n_events = len(fw_ctx.events)
                _log(f"[Pipeline] Framework {label}: "
                     f"{_diff(pass_input, candidate)} "
                     f"({n_events} events)")
                prev = candidate
                log.append(label)

        if self.engine_config.explain and fw_ctx.events:
            block = render_explain(fw_ctx.events)
            result.explain_text = ((result.explain_text + "\n" + block)
                                   .strip("\n"))
        if self.engine_config.stats:
            for key, value in fw_ctx.stats.items():
                result.stats[key] = result.stats.get(key, 0) + value
        return prev


    def run(self, source: str, filename: str = "file.py") -> PipelineResult:
        result = PipelineResult(original=source)
        log = result.log
        current = source

        if filename.endswith((".pyc", ".exe")):
            _log(f"[Pipeline] Skipping {filename} (binary/bytecode not "
                 f"supported yet)")
            log.append("skipped_binary")
            result.cleaned = source
            return result

        if filename.endswith(".pyc"):
            _log("[Pipeline] Decompiling .pyc...")
            try:
                current = self.decompiler.decompile(filename)
                log.append("decompiler")
            except Exception as e:
                log.append(f"decompiler_failed:{e}")

        _log("[Pipeline] Triage...")
        try:
            triage = _run_source_transform_in_thread(
                "triage", lambda src: self.triage.analyze(src, filename), current)
        except Exception as e:
            _log(f"[Pipeline] Triage crashed: {e} — using defaults")
            triage = TriageResult(score=5.0, route="rule_rename",
                                  flags=[f"triage_crash:{e}"])
        result.triage = triage
        log.append(f"triage:score={triage.score:.1f}:route={triage.route}")
        _log(f"[Pipeline] Score={triage.score:.1f}/10.0  Route={triage.route}")

        def try_vm_lift(stage: str, source: str) -> str:
            """
            Lift any VM present, reporting what happened.

            This runs both before and inside the convergence loop because an
            interpreter is often one layer down: the outer source is a decode
            stub, and the VM only becomes visible once the string decoder has
            unpacked it.
            """
            try:
                if not self.vm_lifter.has_vm_class(source):
                    return source
            except Exception:
                return source
            _log("[Pipeline] VM bytecode detected — lifting...")
            try:
                lifted = self._run_guarded(stage, lambda src: (
                    self.vm_lifter.deobfuscate(src)), source, log)
            except Exception as exc:
                log.append(f"{stage}_failed:{exc}")
                _log(f"[Pipeline] VM lifter error: {exc}")
                return source
            if lifted != source:
                log.append(stage)
                _log(f"[Pipeline] VM lift: {_diff(source, lifted)}")
            return lifted

        current = try_vm_lift("vm_lifter", current)

        if self.engine_config.enabled:
            # Rules first, while obfuscator junk is still in its original
            # shape. Oversized raw sources skip this early pass; the
            # post-convergence run handles their cleaned form.
            if len(current) <= self.engine_config.max_rules_source:
                current = self._run_framework_pass(current, result, log)

        _log("[Pipeline] Pre-pass: state machine linearization...")
        prev = current
        try:
            current = _run_source_transform_in_thread(
                "match_sm_prepass", self.match_sm.deobfuscate, current)
        except Exception as e:
            current = prev
            log.append(f"match_sm_prepass_failed:{e}")
        else:
            if current != prev:
                log.append("match_sm_prepass")
                _log(f"[Pipeline] SM pre-pass: {_diff(prev, current)}")

        _log("[Pipeline] Starting convergence loop...")
        for pass_num in range(1, 10):
            changed = False
            for name, fn in self._stages:
                prev = current
                try:
                    current = _run_source_transform_in_thread(name, fn, current)
                except Exception as e:
                    current = prev
                    log.append(f"{name}_failed:{e}")
                    _log(f"[Pipeline]  Pass {pass_num} {name} error: {e}")
                else:
                    if current != prev:
                        log.append(f"pass{pass_num}:{name}")
                        changed = True
                        _log(f"[Pipeline]  Pass {pass_num} {name}: {_diff(prev, current)}")

            # A decoded layer can expose an interpreter that was not visible in
            # the previous pass, so retry the lift once the stages have settled.
            prev = current
            current = try_vm_lift(f"pass{pass_num}:vm_lifter", current)
            if current != prev:
                changed = True

            if not changed:
                _log(f"[Pipeline] Converged at pass {pass_num}")
                break

        if self.engine_config.enabled:
            current = self._run_framework_pass(current, result, log)

        gc.collect()

        if triage.route in ("rule_rename", "llm_rename"):
            current = self._run_guarded(
                "rule_renamer", lambda src: self.renamer.rename(src), current, log)

        if (self.use_llm and self.llm is not None
                and triage.route == "llm_rename"
                and triage.score >= self.llm_threshold):
            def _llm_rename(src_text: str) -> str:
                out = self.llm.process_file(src_text, annotate=self.annotate)
                return out if isinstance(out, str) else src_text

            current = self._run_guarded("llm_renamer", _llm_rename, current, log)

        prev = current
        try:
            current = _run_source_transform_in_thread(
                "ast_cleaner_final", self.cleaner.clean, current)
            if current != prev:
                log.append("ast_cleaner_final")
        except Exception:
            current = prev

        _log("[Pipeline] Formatting...")
        prev = current
        try:
            current = self.formatter.format(current)
            if current != prev:
                log.append("formatter")
        except Exception as e:
            current = prev
            log.append(f"formatter_failed:{e}")

        if self.use_llm and self.ai_simplify and self.llm is not None:
            prev = current

            def _llm_simplify(src_text: str) -> str:
                out = self.llm.simplify(src_text)
                return out if isinstance(out, str) else src_text

            simplified = self._run_guarded("llm_simplify", _llm_simplify,
                                           current, log)
            if simplified != prev:
                current = simplified
                log.append("llm_simplify")
                _log("[Pipeline] LLM simplification applied")
                try:
                    current = self.formatter.format(current)
                except Exception:
                    current = simplified

        _log("[Pipeline] Validating...")
        validation = self.validator.validate(source, current)

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

                def _fix(src_text: str) -> str:
                    fixed = self.llm.fix_syntax(src_text, validation.error)
                    return fixed if isinstance(fixed, str) else src_text

                try:
                    fixed = _run_source_transform_in_thread("llm_fix_syntax",
                                                            _fix, current)
                except Exception as e:
                    log.append(f"llm_fix_syntax_failed:{e}")
                    fixed = None
                if (fixed and fixed != current
                        and self.validator.check_syntax_only(fixed)[0]):
                    _log("[Pipeline] LLM syntax fix succeeded!")
                    current = fixed
                    validation = self.validator.validate(source, current)
                    log.append("syntax_fixed_by_llm")
                else:
                    _log("[Pipeline] LLM syntax fix failed.")
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

        if (self.use_llm and self.ai_explain and self.llm is not None
                and validation.syntax_ok):
            _log("[Pipeline] Generating AI analysis...")
            try:
                result.ai_summary = self.llm.explain(current) or ""
                if result.ai_summary:
                    log.append("llm_explain")
                    _log("[Pipeline] AI analysis generated")
            except Exception as e:
                log.append(f"llm_explain_failed:{e}")

        result.cleaned = current
        return result


def _log(msg: str) -> None:
    lowered = msg.lower()
    if "warning:" not in lowered and any(k in lowered for k in ("error:", "failed", "crashed")):
        print(f"{Fore.LIGHTRED_EX}{msg}{Style.RESET_ALL}")
        logger.error(f"{Fore.LIGHTRED_EX}{msg}{Style.RESET_ALL}")
        return

    if "warning:" in lowered:
        color = Fore.YELLOW
    elif any(k in lowered for k in ("passed", "succeeded", "complete")):
        color = Fore.LIGHTGREEN_EX
    elif "pass" in lowered and "pre-pass" not in lowered:
        color = Fore.CYAN
    elif "triage" in lowered or "route=" in lowered:
        color = Fore.LIGHTMAGENTA_EX
    else:
        color = Fore.LIGHTBLACK_EX
    print(f"{color}{msg}{Style.RESET_ALL}")
    logger.info(f"{color}{msg}{Style.RESET_ALL}")


def _diff(before: str, after: str) -> str:
    delta = len(before) - len(after)
    percent = abs(delta) / max(len(before), 1) * 100
    return f"{'-' if delta > 0 else '+'}{abs(delta)} chars ({percent:.1f}%)"


def _ast_rep_err(s: str) -> Optional[SyntaxError]:
    try:
        ast.parse(s)
        return None
    except SyntaxError as e:
        return e


def _ast_rep_fix_line_continuation(s: str, _e: SyntaxError) -> str:
    return re.sub(r'\\\s+\n', '\\\n', s)


def _ast_rep_insert_pass(s: str, e: SyntaxError) -> str:
    if not e.msg or 'expected an indented block' not in e.msg:
        return s
    m = re.search(r'on line (\d+)', e.msg)
    header_lineno = int(m.group(1)) if m else max(1, (e.lineno or 2) - 1)
    lines = s.splitlines(keepends=True)
    idx = header_lineno - 1
    if idx < 0 or idx >= len(lines):
        return s
    h = lines[idx]
    indent = len(h) - len(h.lstrip())
    return ''.join(lines[:idx + 1] + [' ' * (indent + 4) + 'pass\n'] + lines[idx + 1:])


def _ast_rep_fix_ast_bodies(s: str, _e: SyntaxError) -> str:
    try:
        tree = ast.parse(s)
    except SyntaxError:
        return s
    changed = False
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                                 ast.If, ast.While, ast.For, ast.With, ast.Try,
                                 ast.ExceptHandler)):
            continue
        if isinstance(node.body, list) and not node.body:
            node.body.append(ast.Pass())
            changed = True
    if not changed:
        return s
    try:
        ast.fix_missing_locations(tree)
        return ast.unparse(tree)
    except Exception:
        return s


def _ast_rep_strip_line(s: str, e: SyntaxError) -> str:
    lines = s.splitlines(keepends=True)
    idx = (e.lineno or 1) - 1
    if 0 <= idx < len(lines):
        candidate = ''.join(lines[:idx] + lines[idx + 1:])
        if _ast_rep_err(candidate) is None:
            return candidate
    return s


def _ast_rep_truncate(s: str, _e: SyntaxError) -> str:
    lines = s.splitlines(keepends=True)
    for end in range(len(lines), max(0, len(lines) - 40), -1):
        candidate = ''.join(lines[:end])
        if _ast_rep_err(candidate) is None:
            return candidate
    return s


_AST_REPAIRS = (
    _ast_rep_fix_line_continuation,
    _ast_rep_insert_pass,
    _ast_rep_fix_ast_bodies,
    _ast_rep_strip_line,
    _ast_rep_truncate,
)


def _ast_structural_repair(source: str) -> str:
    """Best-effort repair of syntax errors introduced by the transform passes."""
    result = source
    for _ in range(10):
        error = _ast_rep_err(result)
        if error is None:
            return result
        for repair in _AST_REPAIRS:
            repaired = repair(result, error)
            if repaired != result:
                result = repaired
                break
        else:
            break

    return result if _ast_rep_err(result) is None else source
