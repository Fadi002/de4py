# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Ground-truth and sub-axis scoring for the Onyx corpus gauntlet.

"Onyx didn't crash" / "produced smaller output" are not success criteria. This module scores
against what the sample actually was before obfuscation (when known) or against decomposable
recovery sub-axes (when it isn't).
"""

import ast
import difflib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from de4py.engines.onyx.rule_renamer import is_mangled

FailureClass = str

ENGINE_BUG               : FailureClass = "ENGINE_BUG"
UNSUPPORTED_OBFUSCATION  : FailureClass = "UNSUPPORTED_OBFUSCATION"
REQUIRES_DYNAMIC_ANALYSIS: FailureClass = "REQUIRES_DYNAMIC_ANALYSIS"
CORRUPTED_SAMPLE         : FailureClass = "CORRUPTED_SAMPLE"
PYTHON_VERSION_LIMITATION: FailureClass = "PYTHON_VERSION_LIMITATION"
NEEDS_TRIAGE             : FailureClass = "NEEDS_TRIAGE"

_BASE64_BLOB_RE = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")
_BYTE_ESCAPE_RE = re.compile(r"\\x[0-9a-fA-F]{2}")
_JUMP_BACK_RE   = re.compile(r"#\s*jump back to block")
_VM_HEADER_RE   = re.compile(r"(\d+)/(\d+)\s+opcodes recovered|(\d+)%\s+recovered")
_NO_DECOMPILER_RE = re.compile(r"no decompiler backend available")


@dataclass
class GroundTruthScore:
    name: str
    structural_similarity: float
    literal_recall: float
    behavioral_match: Optional[bool]
    composite: float
    blocked_on_decompiler: bool = False
    notes: List[str] = field(default_factory=list)


@dataclass
class SubAxisScore:
    name: str
    payload_decoded: Optional[bool]
    vm_opcode_recovery: Optional[float]
    dispatcher_states_resolved: Optional[float]
    identifiers_demangled: Optional[float]
    parses: bool
    composite: float
    unscored: bool = False
    notes: List[str] = field(default_factory=list)


def _canonical_dump(source: str) -> Optional[List[str]]:
    """AST dump with identifiers replaced by position-of-first-appearance tokens.

    Preserves literal values (the actual recovered content) and structural shape, but is
    insensitive to legitimate renaming - Onyx recovering `Cyron__v876` as `state` (or leaving it
    as `Cyron__v876`) should not itself count against structural similarity.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    name_map: Dict[str, str] = {}

    def canon(name: str) -> str:
        if name not in name_map:
            name_map[name] = f"ID{len(name_map)}"
        return name_map[name]

    lines: List[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_Name(self, node):
            lines.append(f"Name:{canon(node.id)}")
            self.generic_visit(node)

        def visit_arg(self, node):
            lines.append(f"arg:{canon(node.arg)}")
            self.generic_visit(node)

        def visit_FunctionDef(self, node):
            lines.append(f"FunctionDef:{canon(node.name)}")
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node):
            lines.append(f"AsyncFunctionDef:{canon(node.name)}")
            self.generic_visit(node)

        def visit_ClassDef(self, node):
            lines.append(f"ClassDef:{canon(node.name)}")
            self.generic_visit(node)

        def visit_Attribute(self, node):
            lines.append(f"Attribute:{node.attr}")
            self.generic_visit(node)

        def visit_Constant(self, node):
            lines.append(f"Constant:{node.value!r}")

        def generic_visit(self, node):
            lines.append(type(node).__name__)
            super().generic_visit(node)

    Visitor().visit(tree)
    return lines


def _literals(source: str) -> List[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
            if isinstance(node.value, str) and len(node.value) >= 2:
                out.append(node.value)
            elif isinstance(node.value, bytes) and len(node.value) >= 2:
                out.append(node.value.decode("latin-1"))
    return out


def score_ground_truth(
    name: str,
    original_source: str,
    recovered_source: str,
    behavioral_result: Optional[bool] = None,
) -> GroundTruthScore:
    notes: List[str] = []

    orig_dump = _canonical_dump(original_source)
    rec_dump = _canonical_dump(recovered_source)

    if orig_dump is None:
        notes.append("original source failed to parse - ground truth pair is broken")
        structural = 0.0
    elif rec_dump is None:
        notes.append("recovered output does not parse")
        structural = 0.0
    else:
        structural = difflib.SequenceMatcher(a=orig_dump, b=rec_dump).ratio()

    orig_literals = _literals(original_source)
    if not orig_literals:
        literal_recall = 1.0
    else:
        found = sum(1 for lit in orig_literals if lit in recovered_source)
        literal_recall = found / len(orig_literals)
        if literal_recall < 1.0:
            notes.append(f"{len(orig_literals) - found}/{len(orig_literals)} original literals missing from recovered output")

    parts = [structural, literal_recall]
    if behavioral_result is not None:
        parts.append(1.0 if behavioral_result else 0.0)
        if not behavioral_result:
            notes.append("behavioral diff mismatch")

    composite = sum(parts) / len(parts) * 100.0

    blocked_on_decompiler = bool(_NO_DECOMPILER_RE.search(recovered_source))
    if blocked_on_decompiler:
        notes.append("blocked on a marshaled code object with no decompiler backend available")

    return GroundTruthScore(
        name=name,
        structural_similarity=round(structural * 100.0, 1),
        literal_recall=round(literal_recall * 100.0, 1),
        behavioral_match=behavioral_result,
        composite=round(composite, 1),
        blocked_on_decompiler=blocked_on_decompiler,
        notes=notes,
    )


def _blob_density(source: str) -> int:
    return len(_BASE64_BLOB_RE.findall(source)) + len(_BYTE_ESCAPE_RE.findall(source))


def _mangled_identifiers(source: str) -> List[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
    return [n for n in names if is_mangled(n)]


def score_wild_sample(
    name: str,
    original_source: str,
    recovered_source: str,
    vm_lifter_log: str = "",
) -> SubAxisScore:
    notes: List[str] = []

    parses = False
    try:
        ast.parse(recovered_source)
        parses = True
    except SyntaxError as e:
        notes.append(f"recovered output does not parse: {e}")

    before_density = _blob_density(original_source)
    after_density = _blob_density(recovered_source)
    payload_decoded: Optional[bool] = None
    if before_density > 0:
        payload_decoded = after_density < before_density
        if not payload_decoded:
            notes.append(f"encoded-blob density unchanged ({before_density} -> {after_density})")

    vm_opcode_recovery: Optional[float] = None
    m = _VM_HEADER_RE.search(vm_lifter_log or recovered_source)
    if m:
        if m.group(1) and m.group(2):
            vm_opcode_recovery = round(100.0 * int(m.group(1)) / max(1, int(m.group(2))), 1)
        elif m.group(3):
            vm_opcode_recovery = float(m.group(3))

    dispatcher_states_resolved: Optional[float] = None
    before_jumps = len(_JUMP_BACK_RE.findall(original_source))
    after_jumps = len(_JUMP_BACK_RE.findall(recovered_source))
    if before_jumps > 0 or "match " in original_source or re.search(r"while\s+\w+\s*!=", original_source):
        # Only meaningful when the sample looks dispatcher-shaped; otherwise leave unset.
        if after_jumps > 0:
            dispatcher_states_resolved = 0.0
            notes.append(f"{after_jumps} unresolved dispatcher jump(s) remain")
        elif before_jumps > 0:
            dispatcher_states_resolved = 100.0

    before_mangled = _mangled_identifiers(original_source)
    identifiers_demangled: Optional[float] = None
    if before_mangled:
        try:
            rec_names = {n.id for n in ast.walk(ast.parse(recovered_source)) if isinstance(n, ast.Name)}
        except SyntaxError:
            rec_names = set()
        still_mangled = [n for n in before_mangled if n in rec_names]
        identifiers_demangled = round(100.0 * (1 - len(still_mangled) / len(before_mangled)), 1)

    blocked_on_decompiler = bool(_NO_DECOMPILER_RE.search(recovered_source))
    if blocked_on_decompiler:
        notes.append("blocked on a marshaled code object with no decompiler backend available")

    # A sample where the only signal is "it still parses" is unmeasured, not
    # perfect - defaulting that to 100 is exactly the false-positive shape the
    # task's own anti-cheat rule warns about ("Onyx didn't crash" != success).
    scored_axes = [v for v in (
        (100.0 if payload_decoded else 0.0) if payload_decoded is not None else None,
        vm_opcode_recovery,
        dispatcher_states_resolved,
        identifiers_demangled,
    ) if v is not None]

    unscored = not scored_axes and not blocked_on_decompiler
    if blocked_on_decompiler:
        composite = 0.0
    elif not parses:
        composite = 0.0
    elif scored_axes:
        composite = round(sum(scored_axes) / len(scored_axes), 1)
    else:
        composite = 0.0  # unscored; see `unscored` flag, not a real measurement

    return SubAxisScore(
        name=name,
        payload_decoded=payload_decoded,
        vm_opcode_recovery=vm_opcode_recovery,
        dispatcher_states_resolved=dispatcher_states_resolved,
        identifiers_demangled=identifiers_demangled,
        parses=parses,
        composite=composite,
        unscored=unscored,
        notes=notes,
    )


def classify_failure(
    composite_score: float,
    parses: bool,
    is_encrypted_loader: bool = False,
    exception: Optional[str] = None,
    blocked_on_decompiler: bool = False,
) -> FailureClass:
    if is_encrypted_loader:
        return REQUIRES_DYNAMIC_ANALYSIS
    if exception:
        return ENGINE_BUG
    if blocked_on_decompiler:
        return PYTHON_VERSION_LIMITATION
    if not parses:
        return ENGINE_BUG
    if composite_score >= 90.0:
        return ""
    return NEEDS_TRIAGE
