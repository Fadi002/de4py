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
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Tuple


MAX_TRIAGE_CHARS = 4000

_PYTHON_KEYWORDS: frozenset = frozenset({
    'if', 'else', 'elif', 'for', 'while', 'def', 'class', 'return',
    'import', 'from', 'as', 'with', 'try', 'except', 'finally',
    'raise', 'pass', 'break', 'continue', 'yield', 'lambda',
    'True', 'False', 'None', 'and', 'or', 'not', 'in', 'is',
    'del', 'global', 'nonlocal', 'assert', 'async', 'await',
})

_RE_MANGLED_SHORT   = re.compile(r'^[a-z][0-9]+$')
_RE_MANGLED_OIL     = re.compile(r'^[OIl1]{3,}$')
_RE_MANGLED_UNDER   = re.compile(r'^_{3,}')
_RE_MANGLED_CAMEL   = re.compile(r'^[A-Z][a-z][A-Z][a-z]+$')
_RE_IMPORT_LINE     = re.compile(r'^\s*(import|from)\s+\w')
_RE_EVAL_EXEC       = re.compile(r'\b(?:eval|exec)\b')


def _looks_mangled(name: str) -> bool:
    if len(name) <= 2:
        return True
    if _RE_MANGLED_SHORT.match(name):
        return True
    if _RE_MANGLED_OIL.match(name):
        return True
    if _RE_MANGLED_UNDER.match(name):
        return True
    if _RE_MANGLED_CAMEL.match(name):
        return True
    return False


OBFUSCATION_SIGNATURES: Dict[str, Tuple[float, re.Pattern]] = {
    "iife_lambda":            (2.5, re.compile(r'\(\s*lambda\b[^()]*\)\s*\(')),
    "lambda_seq_vars":        (2.0, re.compile(r'\b_\d{1,4}\b')),
    "join_reversed":          (1.5, re.compile(r"''\s*\.\s*join\s*\(\s*reversed\s*\(")),
    "nested_compress":        (2.0, re.compile(r'decompress\s*\([^;]{0,120}?decompress\s*\(')),
    "reversed_b64":           (2.0, re.compile(r'b64decode\s*\([^)]{0,60}\[::-1\]\s*\)')),
    "proxy_return_def":       (1.0, re.compile(r'def\s+\w+\s*\([^)]*\)\s*:\s*return\s+\w+\(')),
    "b64_direct":             (2.0, re.compile(r'\bb64decode\s*\(|\bb85decode\s*\(')),
    "chr_ord_arithmetic":     (2.5, re.compile(r'chr\s*\(\s*ord\s*\(')),
    "int_xor_decode":         (2.5, re.compile(r'int\.__xor__\s*\(')),
    "globals_builtins":       (2.0, re.compile(r'globals\s*\(\s*\)')),
    "il_homoglyph_vars":      (1.5, re.compile(r'[Il]{5,}')),
    "eval_exec":              (3.0, re.compile(r'\b(eval|exec)\s*\(')),
    "base64_decode":          (2.0, re.compile(r'base64\.b(?:64|32|85|16)decode|__import__\s*\(\s*[\'"]base64')),
    "hex_strings":            (1.5, re.compile(r'\\x[0-9a-fA-F]{2}')),
    "chr_chains":             (2.5, re.compile(r'chr\s*\(\s*\d+\s*\)\s*\+\s*chr')),
    "chr_join":               (2.0, re.compile(r'["\']["\']\\.join\s*\(\s*(?:map\s*\(\s*chr|chr\s*\(|\[?\s*chr)')),
    "rotated_str":            (1.5, re.compile(r'codecs\.decode.{0,300}rot|\.encode\(.{0,300}rot_13')),
    "compressed":             (3.0, re.compile(r'zlib\.decompress|lzma\.decompress|bz2\.decompress')),
    "marshal_load":           (3.5, re.compile(r'marshal\.loads?\s*\(')),
    "bytes_fromhex":          (1.5, re.compile(r'bytes\.fromhex\s*\(')),
    "bytearray_decode":       (1.5, re.compile(r'bytearray\s*\(\s*(?:b["\']|\[)')),
    "xor_decode":             (2.0, re.compile(r'\bfor\s+\w+\s+in\s+\w+\s*\]\s*\)|\^\s*\d+')),
    # Bounded gaps: unbounded .* here backtracks quadratically on quote-heavy
    # filler and holds the GIL for minutes.
    "reversed_string":        (1.0, re.compile(r'["\'][^"\']{0,500}["\']\[::-1\]|reversed\s*\(\s*["\']')),
    "unicode_escape":         (1.5, re.compile(r'\\u[0-9a-fA-F]{4}')),
    "encode_decode":          (1.0, re.compile(r'\.encode\s*\([^)]*\)\.decode\s*\(')),
    "mangled_vars":           (2.0, re.compile(r'\b[OIl1]{4,}\b')),
    "short_vars":             (1.5, re.compile(r'\b[a-z]{1,2}\d{0,2}\s*=')),
    "underscore_prefix":      (1.0, re.compile(r'\b_{3,}\w+\b')),
    "mixed_case_mangling":    (1.0, re.compile(r'\b[A-Z][a-z][A-Z][a-z][A-Z]')),
    "flow_flatten":           (3.0, re.compile(r'while\s+(True|1)\s*:')),
    "state_machine":          (2.5, re.compile(r'__state\s*=|_state\s*=\s*\d')),
    "lambda_abuse":           (1.5, re.compile(r'lambda\s+\w+\s*:\s*lambda')),
    "getattr_chain":          (2.0, re.compile(r'getattr\s*\(.{0,300}getattr')),
    "getattr_string":         (1.5, re.compile(r'getattr\s*\(\s*\w+\s*,\s*["\']')),
    "dispatch_table":         (2.0, re.compile(r'\{\s*\d+\s*:\s*(?:lambda|\w+)\s*(?:,|\})')),
    "opaque_predicates":      (1.5, re.compile(r'if\s+(?:True|False|1\s*==\s*1|0\s*==\s*0|not\s+False)\s*:')),
    "bogus_try_except":       (1.0, re.compile(r'try\s*:[\s\S]{0,200}?except\s*:\s*pass')),
    "dynamic_import":         (2.0, re.compile(r'__import__\s*\(|importlib\.import_module')),
    "compile_exec":           (3.0, re.compile(r'compile\s*\(.{0,300}exec')),
    "code_type":              (3.5, re.compile(r'types\.CodeType\s*\(|code\.co_')),
    "sys_modules_hijack":     (3.0, re.compile(r'sys\.modules\[')),
    "builtins_override":      (2.5, re.compile(r'__builtins__\s*=\s*\{|builtins\.__dict__')),
    "dunder_import":          (2.0, re.compile(r'__builtins__\[["\']__import__')),
    "debugger_detect":        (2.0, re.compile(r'gettrace\s*\(\)|settrace\s*\(|ptrace')),
    "vm_detect":              (1.5, re.compile(r'VirtualBox|VMware|QEMU|HyperV')),
    "time_based_check":       (1.5, re.compile(r'time\s*\.\s*(?:time|monotonic|perf_counter)\s*\(\).{0,300}?<\s*\d')),
    "random_sleep":           (1.0, re.compile(r'sleep\s*\(\s*random')),
    "environment_check":      (1.0, re.compile(r'os\.environ\.get\s*\(\s*["\'](?:VIRTUAL|SANDBOX|ANALYSIS)')),
    "string_split_join":      (2.0, re.compile(r'"[^"]{1,3}"\s*\.\s*join\s*\(\s*"[^"]+"\s*\.\s*split')),
    "string_format_obf":      (1.5, re.compile(r'"%[sd]"\s*%\s*(?:chr\s*\(|\w+\s*\+)')),
    "bytearray_xor":          (2.0, re.compile(r'bytearray\s*\([^)]{0,200}\)\s*\[|bytes\s*\(\s*\[[^\]]{0,200}\^\s*\d+[^\]]{0,60}\]')),
    "hex_exec":               (2.5, re.compile(r'(?:exec|eval)\s*\(\s*bytes\s*\.\s*fromhex')),
    "compile_decode":         (3.0, re.compile(r'compile\s*\([^)]{0,120}(?:decode|decompress|b64decode)[^)]{0,60}\)')),
    "junk_try_except":        (1.5, re.compile(r'(?:try\s*:[\s\S]{0,200}?except\s*:?\s*pass\s*){3,}')),
    "globals_builtins_access": (2.5, re.compile(r"globals\s*\(\s*\)\s*\[\s*[\"']__builtins__[\"']\s*\]")),
    "unicode_escape_ident":   (2.0, re.compile(r'\\u[0-9a-fA-F]{4}(?:\\u[0-9a-fA-F]{4}){2,}')),
    "marshal_exec":           (3.5, re.compile(r'marshal\.loads?\s*\([^)]{0,120}\)\s*[\)\[]*\s*(?:exec|eval)?', re.I)),
    "reverse_assign":         (1.0, re.compile(r'\w+\s*=\s*\w+\s*\[\s*:\s*:\s*-1\s*\]')),
    "encrypted_loader":       (4.0, re.compile(r'(?:ancrypt|pyarmor|sourcedefender|pyminifier)\s*\.\s*(?:load|run|exec|decrypt)\s*\(\s*__file__\s*\)|co_encrypt')),
}



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


class TriageEngine:

    def analyze(self, source: str, filename: str = "") -> TriageResult:
        result = TriageResult()

        if filename.endswith(".pyc") or self._is_pyc_bytes(source):
            result.is_pyc   = True
            result.score    = 5.0
            result.flags.append("pyc_bytecode")
            result.route    = "rule_rename"
            return result

        for name, (weight, pattern) in OBFUSCATION_SIGNATURES.items():
            # `Pattern.search(s, pos, endpos)` takes a start offset, not flags:
            # passing re.MULTILINE|re.DOTALL here made every signature begin
            # scanning at character 24, silently missing markers near the top of
            # the file. Flags belong on the pattern, which already carries them.
            if pattern.search(source):
                result.flags.append(name)
                result.score = min(10.0, result.score + weight)
                logging.debug("Found indicator: %s (+%s)", name, weight)

        eval_depth = self._count_eval_nesting(source)
        if eval_depth >= 2:
            result.has_eval_layers = True
            bonus = min(2.0, eval_depth * 0.5)
            result.score = min(10.0, result.score + bonus)
            result.flags.append(f"eval_layers_{eval_depth}")

        entropy_score = self._identifier_entropy(source)
        result.score  = min(10.0, result.score + entropy_score)
        if entropy_score > 0.5:
            result.flags.append(f"identifier_entropy_{entropy_score:.1f}")

        max_line = self._max_line_length(source)
        if max_line > 1000:
            bonus = min(2.0, (max_line - 1000) / 1000)
            result.score = min(10.0, result.score + bonus)
            result.flags.append(f"long_line_{max_line}")

        import_density_score = self._import_density_score(source)
        if import_density_score > 0:
            result.score = min(10.0, result.score + import_density_score)
            result.flags.append("low_import_density")

        result.estimated_functions = self._count_functions(source)

        if result.score < 4.0:
            result.route = "static_only"
        elif result.score < 7.0:
            result.route = "rule_rename"
        else:
            result.route = "llm_rename"

        return result

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
        matches = _RE_EVAL_EXEC.findall(source)
        return len(matches)

    def _identifier_entropy(self, source: str) -> float:
        """
        Score 0.0–2.0 based on what fraction of identifiers look mangled.
        Returns higher score for unusually short average identifier length.
        """
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
        except tokenize.TokenError:
            return 1.0

        names = [
            t.string for t in tokens
            if t.type == tokenize.NAME and t.string not in _PYTHON_KEYWORDS
        ]
        if not names:
            return 0.0

        gibberish_count = sum(1 for n in names if _looks_mangled(n))
        ratio           = gibberish_count / len(names)

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
            if _RE_IMPORT_LINE.match(line)
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
