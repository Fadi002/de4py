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
import subprocess
import shutil
import sys
import psutil
import threading
import gc
from dataclasses import dataclass, field
from typing import Callable, List, Optional
from colorama import Fore, Style

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

_CACHED_LLM_CONFIG: Optional[dict] = None

_STAGE_THREAD_STACK_BYTES = 64 * 1024 * 1024


def _run_source_transform_in_thread(name: str, fn: Callable[[str], str], source: str) -> str:
    # AST passes recurse once per nesting level; heavily obfuscated input blows the
    # default 8MB stack long before Python's recursion limit is reached, so each
    # transform runs on a thread with a much larger stack.
    result = {}

    def worker():
        try:
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
        thread.join()
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
            t, r, v = (self.llm_config[k] for k in ("tier", "ram_gb", "vram_gb"))
            logger.info("[Pipeline] HW Tier: %s (RAM:%sGB VRAM:%sGB)", t, r, v)
            if self.llm_config["num_gpu"] == 0:
                logger.info("[Pipeline] CPU-only mode (num_gpu=0)")

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

        self._stages = [
            ("proxy_cleaner",  self.proxy.deobfuscate),
            ("string_decoder", self.decoder.decode_all),
            ("ast_cleaner",    self.cleaner.clean),
            ("match_sm",       self.match_sm.deobfuscate),
            ("lambda_norm",    self.lambda_n.deobfuscate),
            ("flow_deobf",     self.flow.deobfuscate),
            ("ast_cleaner2",   self.cleaner.clean),
        ]

    def _get_llm_config(self) -> dict:
        global _CACHED_LLM_CONFIG
        if _CACHED_LLM_CONFIG is not None:
            return _CACHED_LLM_CONFIG

        ram_gb = round(psutil.virtual_memory().total / (1024**3))
        vram_gb = 0
        try:
            if shutil.which("nvidia-smi"):
                creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                out = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                    text=True, creationflags=creationflags
                )
                lines = [l.strip() for l in out.split("\n") if l.strip().isdigit()]
                if lines: vram_gb = round(int(lines[0])/1024)
        except Exception:
            pass

        if vram_gb < 2 or ram_gb < 8:
            tier, ctx, batch = "Low", 512, 128
        elif vram_gb < 4 or ram_gb < 16:
            tier, ctx, batch = "Mid", 1024, 256
        else:
            tier, ctx, batch = "High", 4096, 512

        _CACHED_LLM_CONFIG = {
            "tier": tier, "ram_gb": ram_gb, "vram_gb": vram_gb,
            "num_ctx": ctx, "num_batch": batch, "num_gpu": 0 if vram_gb < 4 else -1
        }
        return _CACHED_LLM_CONFIG

    def run(self, source: str, filename: str = "file.py") -> PipelineResult:
        result = PipelineResult(original=source)
        log = result.log
        current = source

        if filename.endswith(".pyc"):
            _log("[Pipeline] Decompiling .pyc...")
            try:
                current = self.decompiler.decompile(filename)
                log.append("decompiler")
            except Exception as e:
                log.append(f"decompiler_failed:{e}")

        _log("[Pipeline] Triage...")
        try:
            triage = self.triage.analyze(current, filename)
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
                lifted = self.vm_lifter.deobfuscate(source)
            except Exception as exc:
                log.append(f"{stage}_failed:{exc}")
                _log(f"[Pipeline] VM lifter error: {exc}")
                return source
            if lifted != source:
                log.append(stage)
                _log(f"[Pipeline] VM lift: {_diff(source, lifted)}")
            return lifted

        current = try_vm_lift("vm_lifter", current)

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

        gc.collect()

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
        return result


def _log(msg: str) -> None:
    lowered = msg.lower()
    if "warning:" not in lowered and any(k in lowered for k in ("error:", "failed", "crashed")):
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
