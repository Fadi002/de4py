# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Main deobfuscation pipeline that orchestrates various static and LLM-based
deobfuscation stages in a convergence loop.
"""

import subprocess
import shutil
import psutil
import textwrap
from typing import Optional

from de4py.engines.onyx.triage import TriageEngine, TriageResult
from de4py.engines.onyx.decompiler import Decompiler
from de4py.engines.onyx.string_decoder import StringDecoder
from de4py.engines.onyx.ast_cleaner import ASTCleaner
from de4py.engines.onyx.flow_deobfuscator import FlowDeobfuscator
from de4py.engines.onyx.match_case_deobfuscator import MatchCaseDeobfuscator
from de4py.engines.onyx.lambda_normalizer import LambdaChainDeobfuscator
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

        self.llm_config = self._get_llm_config()
        if self.use_llm:
            tier, ram_gb, vram_gb = (self.llm_config[k] for k in ("tier","ram_gb","vram_gb"))
            print(f"[Pipeline] HW Tier: {tier} (RAM:{ram_gb}GB VRAM:{vram_gb}GB)")
            if self.llm_config["num_gpu"] == 0:
                print("[Pipeline] CPU-only mode (num_gpu=0)")

        self.triage    = TriageEngine()
        self.decompiler= Decompiler()
        self.decoder   = StringDecoder()
        self.cleaner   = ASTCleaner()
        self.flow      = FlowDeobfuscator()
        self.match_sm  = MatchCaseDeobfuscator()
        self.lambda_n  = LambdaChainDeobfuscator()
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
        ram_gb  = round(psutil.virtual_memory().total / (1024 ** 3))
        vram_gb = 0
        try:
            if shutil.which("nvidia-smi"):
                out = subprocess.check_output(
                    ["nvidia-smi","--query-gpu=memory.total","--format=csv,noheader,nounits"],
                    text=True)
                lines = [l.strip() for l in out.split("\n") if l.strip().isdigit()]
                if lines: vram_gb = round(int(lines[0]) / 1024)
        except Exception:
            pass
        if vram_gb < 2 or ram_gb < 8:   tier, ctx, batch = "Low",  512,  128
        elif vram_gb < 4 or ram_gb < 16: tier, ctx, batch = "Mid",  1024, 256
        else:                             tier, ctx, batch = "High", 4096, 512
        return {"tier":tier,"ram_gb":ram_gb,"vram_gb":vram_gb,
                "num_ctx":ctx,"num_batch":batch,"num_gpu":0 if vram_gb<4 else -1}

    def run(self, source: str, filename: str = "file.py") -> PipelineResult:
        result          = PipelineResult()
        result.original = source
        current         = source
        log             = []

        # --- 0: Decompile .pyc ------------------------------------------------
        if filename.endswith(".pyc"):
            print("[Pipeline] Decompiling .pyc...")
            try:
                current = self.decompiler.decompile(filename)
                log.append("decompiler")
            except Exception as e:
                log.append(f"decompiler_failed:{e}")

        # --- 1: Triage --------------------------------------------------------
        print("[Pipeline] Triage...")
        triage = self.triage.analyze(current, filename)
        result.triage = triage
        log.append(f"triage:score={triage.score:.1f}:route={triage.route}")
        print(f"[Pipeline] Score={triage.score:.1f}/10.0 Route={triage.route}")

        # --- 2: VM Lifter -----------------------------------------------------
        if self.vm_lifter._has_vm_class_source(current):
            print("[Pipeline] VM bytecode detected — lifting...")
            prev = current
            try:
                lifted = self.vm_lifter.deobfuscate(current)
                if lifted != prev:
                    current = lifted
                    log.append("vm_lifter")
                    print(f"[Pipeline] VM lift: {_diff(prev, current)}")
            except Exception as e:
                log.append(f"vm_lifter_failed:{e}")
                print(f"[Pipeline] VM lifter error: {e}")

        # --- 3: Multi-pass convergence loop -----------------------------------
        print("[Pipeline] Starting convergence loop...")
        for pass_num in range(1, 9):
            changed = False

            for name, fn in [
                ("string_decoder",  lambda s: self.decoder.decode_all(s)),
                ("ast_cleaner",     lambda s: self.cleaner.clean(s)),
                ("lambda_norm",     lambda s: self.lambda_n.deobfuscate(s)),
                ("match_sm",        lambda s: self.match_sm.deobfuscate(s)),
                ("flow_deobf",      lambda s: self.flow.deobfuscate(s)),
            ]:
                prev = current
                try:
                    current = fn(current)
                    if current != prev:
                        log.append(f"pass{pass_num}:{name}")
                        changed = True
                        print(f"[Pipeline]  Pass {pass_num} {name}: {_diff(prev, current)}")
                except Exception as e:
                    current = prev
                    log.append(f"{name}_failed:{e}")

            if not changed:
                print(f"[Pipeline] Converged at pass {pass_num}")
                break

        # --- 4: Rule rename ---------------------------------------------------
        if triage.route in ("rule_rename", "llm_rename"):
            prev = current
            try:
                current = self.renamer.rename(current)
                if current != prev:
                    log.append("rule_renamer")
                    print(f"[Pipeline] Rule rename: {_diff(prev, current)}")
            except Exception as e:
                current = prev
                log.append(f"rule_renamer_failed:{e}")

        # --- 5: LLM rename ----------------------------------------------------
        if (self.use_llm and self.llm is not None
                and triage.route == "llm_rename"
                and triage.score >= self.llm_threshold):
            prev = current
            try:
                current = self.llm.process_file(current, annotate=self.annotate)
                if current != prev:
                    log.append("llm_renamer")
            except Exception as e:
                current = prev
                log.append(f"llm_renamer_failed:{e}")

        # --- 6: Final AST clean -----------------------------------------------
        prev = current
        try:
            current = self.cleaner.clean(current)
            if current != prev:
                log.append("ast_cleaner_final")
        except Exception:
            current = prev

        # --- 7: Format --------------------------------------------------------
        print("[Pipeline] Formatting...")
        prev = current
        try:
            current = self.formatter.format(current)
            if current != prev: log.append("formatter")
        except Exception as e:
            current = prev
            log.append(f"formatter_failed:{e}")

        # --- 8: Validate ------------------------------------------------------
        print("[Pipeline] Validating...")
        validation = self.validator.validate(source, current)
        
        if not validation.syntax_ok and self.use_llm and self.llm is not None:
            print(f"[Pipeline] FAILED: {validation.error}")
            print("[Pipeline] Attempting LLM syntax correction...")
            fixed = self.llm.fix_syntax(current, validation.error)
            if fixed and self.validator.check_syntax_only(fixed)[0]:
                print("[Pipeline] Correction successful!")
                current = fixed
                validation = self.validator.validate(source, current)
                log.append("syntax_fixed_by_llm")
            else:
                print("[Pipeline] Correction failed.")

        result.validation = validation
        
        if not validation.syntax_ok:
            log.append("validation_failed:kept_broken")
            print("[Pipeline] WARNING: Syntax error remains. Returning broken code.")
        else:
            print("[Pipeline] PASSED")
            for w in (validation.warnings or []):
                print(f"[Pipeline]  Warning: {w}")

        result.cleaned = current
        result.log     = log
        return result


def _diff(before: str, after: str) -> str:
    """Calculate character difference and reduction percentage."""
    d = len(before) - len(after)
    p = abs(d) / max(len(before), 1) * 100
    return f"{'↓' if d>0 else '↑'}{abs(d)} chars ({p:.1f}%)"
