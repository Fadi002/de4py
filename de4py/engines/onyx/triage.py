# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import re
import ast
import tokenize
import io
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional


# --- Constants ----------------------------------------------------------------

MAX_TRIAGE_CHARS = 4000


# --- Data model ---------------------------------------------------------------

@dataclass
class TriageResult:
    score:               float = 0.0
    flags:               List[str] = field(default_factory=list)
    is_pyc:              bool  = False
    has_eval_layers:     bool  = False
    estimated_functions: int   = 0
    route:               str   = "static_only"

    def __str__(self):
        return (
            f"score={self.score:.1f} route={self.route} "
            f"flags=[{', '.join(self.flags)}] "
            f"functions={self.estimated_functions}"
        )


# --- Signatures ---------------------------------------------------------------

# (score_weight, regex_pattern)
OBFUSCATION_SIGNATURES: Dict[str, Tuple[float, str]] = {
    # String encoding techniques
    "eval_exec":             (3.0, r'\b(eval|exec)\s*\('),
    "base64_decode":         (2.0, r'base64\.b(?:64|32|85|16)decode|__import__\s*\(\s*[\'"]base64'),
    "hex_strings":           (1.5, r'\\x[0-9a-fA-F]{2}'),
    "chr_chains":            (2.5, r'chr\s*\(\s*\d+\s*\)\s*\+\s*chr'),
    "chr_join":              (2.0, r'["\']["\']\.join\s*\(\s*(?:map\s*\(\s*chr|chr\s*\(|\[?\s*chr)'),
    "rotated_str":           (1.5, r'codecs\.decode.*rot|\.encode\(.*rot_13'),
    "compressed":            (3.0, r'zlib\.decompress|lzma\.decompress|bz2\.decompress'),
    "marshal_load":          (3.5, r'marshal\.loads?\s*\('),
    "bytes_fromhex":         (1.5, r'bytes\.fromhex\s*\('),
    "bytearray_decode":      (1.5, r'bytearray\s*\(\s*(?:b["\']|\[)'),
    "xor_decode":            (2.0, r'\bfor\s+\w+\s+in\s+\w+\s*\]\s*\)|\^\s*\d+'),
    "reversed_string":       (1.0, r'["\'].*["\']\[::-1\]|reversed\s*\(\s*["\']'),
    "unicode_escape":        (1.5, r'\\u[0-9a-fA-F]{4}'),
    "encode_decode":         (1.0, r'\.encode\s*\([^)]*\)\.decode\s*\('),

    # Variable/name mangling
    "mangled_vars":          (2.0, r'\b[OIl1]{4,}\b'),
    "short_vars":            (1.5, r'\b[a-z]{1,2}\d{0,2}\s*='),
    "underscore_prefix":     (1.0, r'\b_{3,}\w+\b'),
    "mixed_case_mangling":   (1.0, r'\b[A-Z][a-z][A-Z][a-z][A-Z]'),   # AbCdE style

    # Control flow techniques
    "flow_flatten":          (3.0, r'while\s+(True|1)\s*:'),
    "state_machine":         (2.5, r'__state\s*=|_state\s*=\s*\d'),
    "lambda_abuse":          (1.5, r'lambda\s+\w+\s*:\s*lambda'),
    "getattr_chain":         (2.0, r'getattr\s*\(.*getattr'),
    "getattr_string":        (1.5, r'getattr\s*\(\s*\w+\s*,\s*["\']'),
    "dispatch_table":        (2.0, r'\{\s*\d+\s*:\s*(?:lambda|\w+)\s*(?:,|\})'),
    "opaque_predicates":     (1.5, r'if\s+(?:True|False|1\s*==\s*1|0\s*==\s*0|not\s+False)\s*:'),
    "bogus_try_except":      (1.0, r'try\s*:[\s\S]{0,200}?except\s*:\s*pass'),

    # Dynamic execution
    "dynamic_import":        (2.0, r'__import__\s*\(|importlib\.import_module'),
    "compile_exec":          (3.0, r'compile\s*\(.*exec'),
    "code_type":             (3.5, r'types\.CodeType\s*\(|code\.co_'),
    "sys_modules_hijack":    (3.0, r'sys\.modules\['),
    "builtins_override":     (2.5, r'__builtins__\s*=\s*\{|builtins\.__dict__'),
    "dunder_import":         (2.0, r'__builtins__\[["\']__import__'),

    # Anti-analysis
    "debugger_detect":       (2.0, r'gettrace\s*\(\)|settrace\s*\(|ptrace'),
    "vm_detect":             (1.5, r'VirtualBox|VMware|QEMU|HyperV'),
    "time_based_check":      (1.5, r'time\s*\.\s*(?:time|monotonic|perf_counter)\s*\(\).*?<\s*\d'),
    "random_sleep":          (1.0, r'sleep\s*\(\s*random'),
    "environment_check":     (1.0, r'os\.environ\.get\s*\(\s*["\'](?:VIRTUAL|SANDBOX|ANALYSIS)'),

    # String-split obfuscation
    "string_split_join":     (2.0, r'"[^"]{1,3}"\s*\.\s*join\s*\(\s*"[^"]+"\s*\.\s*split'),
    "string_format_obf":     (1.5, r'"%[sd]"\s*%\s*(?:chr\s*\(|\w+\s*\+)'),
}


# --- Engine -------------------------------------------------------------------

class TriageEngine:

    def analyze(self, source: str, filename: str = "") -> TriageResult:
        result = TriageResult()

        # Detect compiled bytecode
        if filename.endswith(".pyc") or self._is_pyc_bytes(source):
            result.is_pyc   = True
            result.score    = 5.0
            result.flags.append("pyc_bytecode")
            result.route    = "rule_rename"
            return result

        # Apply signature patterns
        for name, (weight, pattern) in OBFUSCATION_SIGNATURES.items():
            if re.search(pattern, source, re.MULTILINE | re.DOTALL):
                result.flags.append(name)
                result.score = min(10.0, result.score + weight)
                print(f"[Triage] Found indicator: {name} (+{weight})")

        # Eval nesting depth
        eval_depth = self._count_eval_nesting(source)
        if eval_depth >= 2:
            result.has_eval_layers = True
            bonus = min(2.0, eval_depth * 0.5)
            result.score = min(10.0, result.score + bonus)
            result.flags.append(f"eval_layers_{eval_depth}")

        # Identifier entropy
        entropy_score = self._identifier_entropy(source)
        result.score  = min(10.0, result.score + entropy_score)
        if entropy_score > 0.5:
            result.flags.append(f"identifier_entropy_{entropy_score:.1f}")

        # Line length heuristic: single very long lines are a red flag
        max_line = self._max_line_length(source)
        if max_line > 1000:
            bonus = min(2.0, (max_line - 1000) / 1000)
            result.score = min(10.0, result.score + bonus)
            result.flags.append(f"long_line_{max_line}")

        # Import density: a 500+ line file with ≤2 imports is suspicious
        import_density_score = self._import_density_score(source)
        if import_density_score > 0:
            result.score = min(10.0, result.score + import_density_score)
            result.flags.append(f"low_import_density")

        # Count functions for engine workload estimation
        result.estimated_functions = self._count_functions(source)

        # Routing decision
        if result.score < 4.0:
            result.route = "static_only"
        elif result.score < 7.0:
            result.route = "rule_rename"
        else:
            result.route = "llm_rename"

        return result

    # --- Private helpers ------------------------------------------------------

    def _is_pyc_bytes(self, source: str) -> bool:
        if not source:
            return False
        try:
            b = source.encode('latin-1')[:4]
            return b[:2] in (b'\x55\x0d', b'\x0d\x0d', b'\x16\x0d', b'\x33\x0d',
                             b'\x42\x0d', b'\x61\x0d', b'\x6f\x0d')
        except Exception:
            return False

    def _count_eval_nesting(self, source: str) -> int:
        max_depth = 0
        depth     = 0
        for i, ch in enumerate(source):
            if source[i:i+4] in ('eval', 'exec'):
                depth     += 1
                max_depth  = max(max_depth, depth)
            elif ch in (')', ']'):
                depth = max(0, depth - 1)
        return max_depth

    def _identifier_entropy(self, source: str) -> float:
        """
        Score 0.0–2.0 based on what fraction of identifiers look mangled.
        Returns higher score for unusually short average identifier length.
        """
        PYTHON_KEYWORDS = {
            'if', 'else', 'elif', 'for', 'while', 'def', 'class', 'return',
            'import', 'from', 'as', 'with', 'try', 'except', 'finally',
            'raise', 'pass', 'break', 'continue', 'yield', 'lambda',
            'True', 'False', 'None', 'and', 'or', 'not', 'in', 'is',
            'del', 'global', 'nonlocal', 'assert', 'async', 'await',
        }
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
        except tokenize.TokenError:
            return 1.0

        names = [
            t.string for t in tokens
            if t.type == tokenize.NAME and t.string not in PYTHON_KEYWORDS
        ]
        if not names:
            return 0.0

        def looks_mangled(name: str) -> bool:
            if len(name) <= 2:
                return True
            if re.match(r'^[a-z][0-9]+$', name):
                return True
            if re.match(r'^[OIl1]{3,}$', name):
                return True
            if re.match(r'^_{3,}', name):
                return True
            if re.match(r'^[A-Z][a-z][A-Z][a-z]+$', name):
                return True
            return False

        gibberish_count = sum(1 for n in names if looks_mangled(n))
        ratio           = gibberish_count / len(names)

        # Bonus: penalise very short average identifier length
        avg_len         = sum(len(n) for n in names) / len(names)
        length_penalty  = max(0.0, (4.0 - avg_len) * 0.2) if avg_len < 4.0 else 0.0

        return round(min(2.0, ratio * 2.0 + length_penalty), 2)

    def _max_line_length(self, source: str) -> int:
        return max((len(line) for line in source.splitlines()), default=0)

    def _import_density_score(self, source: str) -> float:
        """
        A large file with suspiciously few imports gets a score boost.
        """
        lines = source.splitlines()
        if len(lines) < 300:
            return 0.0

        import_lines = sum(
            1 for line in lines
            if re.match(r'^\s*(import|from)\s+\w', line)
        )

        if import_lines <= 1:
            return 1.0
        if import_lines <= 3:
            return 0.5
        return 0.0

    def _count_functions(self, source: str) -> int:
        try:
            tree = ast.parse(source)
            return sum(
                1 for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
        except SyntaxError:
            return 0
