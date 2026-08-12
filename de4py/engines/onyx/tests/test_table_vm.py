# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Tests for table-dispatch register VMs.

The dispatcher is a rotated tuple of handler lambdas rather than a switch, so
an opcode's meaning is its position in that table. Everything the lifter needs —
the rotation, the instruction width, the register file, the operator behind a
comparison — is recovered from the sample, and these tests pin that: a variant
that renames every identifier or re-emits with different constants must still
lift, which is exactly what hardcoding would break.
"""

import ast
import builtins
import pathlib
import re
import symtable

import pytest

from de4py.engines.onyx.string_decoder import StringDecoder
from de4py.engines.onyx.vm.ir import VOp
from de4py.engines.onyx.vm.table_dispatch import (
    build_table_model,
    find_handler_table,
    recover_rotation,
)
from de4py.engines.onyx.vm_lifter import VMLifter

CORPUS = pathlib.Path(__file__).resolve().parents[4] / "build-logs"

TABLE_VM = '''
class Machine:
    def __init__(self, code, pool):
        self.code = code
        self.pool = pool
        self.regs = [0] * 8
        self.size, *self.rest = (4,)
        self.pending = []
        self.pc = 0
        self.table = (
            lambda a, b: [None for self.regs[a] in [self.regs[a] + self.regs[b]]],
            lambda a, b: [None for self.regs[a] in [self.regs[a] - self.regs[b]]],
            lambda a, b: [None for self.regs[a] in [self.decode(b)]],
            lambda a, b: [None for self.pending in [[a * 3]]],
            lambda a, b: (x for x in ()).throw(Halt(self.regs[a])),
            lambda a, b: [None for self.regs[a] in [self.regs[a] * self.regs[b]]],
            lambda a, b: [None for self.regs[a] in [self.regs[a] ^ self.regs[b]]],
        )

    def decode(self, index):
        return self.pool[index]

    def run(self):
        self.table = (lambda: self.table[-(-1 % self.size):]
                      + self.table[:-(-1 % self.size)])()
        self.pc, *rest = self.pending
        while self.pc < self.code.__len__():
            self.pending.append(self.pc + 3)
            self.table[self.code[self.pc]](self.code[self.pc + 1],
                                           self.code[self.pc + 2])
            self.pc, *rest = self.pending
'''


@pytest.fixture(scope="module")
def machine():
    tree = ast.parse(TABLE_VM)
    return next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))


# ── discovery ───────────────────────────────────────────────────────────────

def test_handler_table_is_found(machine):
    table = find_handler_table(machine)
    assert table is not None
    assert len(table.handlers) == 7
    assert table.params == ("a", "b")


def test_rotation_comes_from_the_sample(machine):
    """
    `-(-1 % 4)` is the sample's own arithmetic, not a constant we assume.

    The cut is -3, and slicing a 7-element table from -3 is a left rotation by
    4, so the recovered shift must account for the negative index rather than
    taking the expression's value at face value.
    """
    table = find_handler_table(machine)
    rotation = recover_rotation(machine, table, {"size": 4})
    assert rotation == 4

    original = list(range(7))
    assert original[-3:] + original[:-3] == original[4:] + original[:4]


def test_model_records_shape(machine):
    built = build_table_model(machine)
    assert built is not None
    model, table, site = built
    assert model.dispatch_kind == "table"
    assert model.machine == "register"
    assert model.instruction_width == 3
    assert model.operand_count == 2
    assert site.pc_carrier == "pending"


def test_opcodes_classify_by_effect(machine):
    """Meaning comes from what a handler does, never from its position alone."""
    model, table, _ = build_table_model(machine)
    ops = {spec.op for spec in model.opcodes.values()}
    assert VOp.BINARY in ops
    assert VOp.JUMP in ops
    assert VOp.RETURN in ops
    assert model.coverage() == 1.0


def test_jump_scale_is_recovered(machine):
    """`a * 3` states that targets are instruction indices, not byte offsets."""
    model, _, _ = build_table_model(machine)
    jumps = [s for s in model.opcodes.values() if s.op is VOp.JUMP]
    assert jumps and jumps[0].target_scale == 3


def test_plain_class_is_not_a_vm():
    tree = ast.parse("class A:\n    def f(self):\n        return 1\n")
    cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
    assert find_handler_table(cls) is None
    assert build_table_model(cls) is None


# ── comparison tables ───────────────────────────────────────────────────────

COMPARE_VM = TABLE_VM.replace(
    "lambda a, b: [None for self.regs[a] in [self.regs[a] ^ self.regs[b]]],",
    "lambda a, b: [None for self.regs[a] in "
    "[[self.regs[a] == self.regs[b], self.regs[a] != self.regs[b], "
    "self.regs[a] < self.regs[b], self.regs[a] > self.regs[b]][b]]],",
)


def test_comparison_table_recovers_every_operator():
    """One opcode covering all comparisons must not read as a subscript."""
    tree = ast.parse(COMPARE_VM)
    cls = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
    model, _, _ = build_table_model(cls)
    compares = [s for s in model.opcodes.values() if s.op is VOp.COMPARE]
    assert compares, "comparison table should classify as COMPARE"
    assert compares[0].compare_table == {0: "==", 1: "!=", 2: "<", 3: ">"}


# ── end to end ──────────────────────────────────────────────────────────────

@pytest.mark.skipif(not (CORPUS / "cyron.py").exists(), reason="corpus not present")
def test_cyron_devirtualizes_to_readable_python():
    """The whole point: a register VM lifts to source an analyst can read."""
    source = (CORPUS / "cyron.py").read_text(encoding="utf-8")
    decoded = StringDecoder().decode_all(source)

    lifter = VMLifter()
    assert lifter.has_vm_class(decoded)

    lifted = lifter.deobfuscate(decoded)
    assert lifted != decoded
    ast.parse(lifted)

    # Recovered library calls prove the pools decoded, not just the opcodes.
    for expected in ("AES.new", "PBKDF2", "unpad", "hashlib.sha256"):
        assert expected in lifted, f"{expected} missing from lift"

    # Constants must resolve through the pool rather than leak their index.
    assert "const_" not in lifted
    assert "<unknown>" not in lifted


def _unbound_free_names(source: str) -> set:
    """
    Names a function reads that resolve to nothing: not a local, not declared
    ``global``, not a builtin, not a dunder Python sets automatically.

    Uses :mod:`symtable` rather than hand-rolled AST walking so scope
    resolution matches what the real interpreter would do.
    """
    top = symtable.symtable(source, "<lifted>", "exec")
    unbound = set()
    for child in top.get_children():
        if child.get_type() != "function":
            continue
        for name in child.get_identifiers():
            symbol = child.lookup(name)
            if symbol.is_assigned() or symbol.is_parameter() or symbol.is_global():
                continue
            if hasattr(builtins, name):
                continue
            if name.startswith("__") and name.endswith("__"):
                continue
            unbound.add(name)
    return unbound


@pytest.mark.skipif(not (CORPUS / "cyron.py").exists(), reason="corpus not present")
def test_cyron_shared_registers_stay_defined():
    """
    Regression for a register-naming bug: sibling VM programs (main /
    main_fn0 / main_fn1) are methods of one interpreter instance and
    read/write the same register file through STORE_GLOBAL/LOAD_GLOBAL.
    Splitting them into independently-scoped Python functions must not
    silently drop a value one sibling sets for another to read, and the
    free-variable placeholders that mechanism introduces must never shadow a
    real Python builtin or dunder.
    """
    source = (CORPUS / "cyron.py").read_text(encoding="utf-8")
    decoded = StringDecoder().decode_all(source)
    lifted = VMLifter().deobfuscate(decoded)
    tree = ast.parse(lifted)

    assert not _unbound_free_names(lifted)

    module_assigned_none = {
        node.targets[0].id
        for node in tree.body
        if isinstance(node, ast.Assign) and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant) and node.value.value is None
    }
    shadowed = module_assigned_none & set(dir(builtins))
    assert not shadowed, f"builtin(s) shadowed by a free-variable placeholder: {shadowed}"

    # Random per-run identifiers rule out pinning a literal name; instead check
    # that some name the root program assigns is also read by a nested
    # sibling - proof a value crosses the function boundary at all, which is
    # exactly what independently-scoped functions would silently break.
    functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    nested = [f for f in functions if re.search(r"_fn\d+$", f.name)]
    root = [f for f in functions if f not in nested]
    assert nested and root

    root_writes = {n.id for f in root for n in ast.walk(f)
                   if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    nested_reads = {n.id for f in nested for n in ast.walk(f)
                    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    shared = root_writes & nested_reads
    assert shared, "no name the root program assigns is read by a nested sibling"
