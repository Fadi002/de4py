# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import ast
import pickle

import pytest

from de4py.engines.onyx.vm import (
    PayloadExtractor,
    VMDiscovery,
    VOp,
    build_cfg,
    decode,
    lift_program,
)
from de4py.engines.onyx.vm_lifter import VMLifter

# A stack VM in the shape the corpus uses: 2-byte instructions, match dispatch,
# pickled (bytecode, consts, names) payload.
VM_SOURCE = '''
import pickle

vglobals = vars(__builtins__)

class VM:
    def __init__(self, instructions):
        self.bytecode, self.consts, self.names = pickle.loads(instructions)

    def __call__(self, *args):
        stack = []
        pop = stack.pop
        push = stack.append
        cx = 0
        vlocals = vars(__builtins__)
        for i in range(len(args)):
            vlocals[self.names[i]] = args[i]
        while cx < len(self.bytecode):
            opc = self.bytecode[cx]
            opa = self.bytecode[cx + 1]
            match(opc):
                case 1:
                    const = self.consts[opa]
                    push(const)
                case 2:
                    const = pop()
                    name = self.names[opa]
                    vlocals[name] = const
                case 3:
                    name = self.names[opa]
                    push(vlocals[name])
                case 4:
                    const = pop()
                    name = self.names[opa]
                    vglobals[name] = const
                case 5:
                    name = self.names[opa]
                    push(vglobals[name])
                case 6:
                    b = pop()
                    a = pop()
                    push(a + b)
                case 8:
                    b = pop()
                    a = pop()
                    push(a * b)
                case 19:
                    args = []
                    for _ in range(opa):
                        args.insert(0, pop())
                    function = pop()
                    push(function(*args))
                case 20:
                    bytecode = pop()
                    name = self.names[opa]
                    vglobals[name] = VM(bytecode)
                case 21:
                    return pop()
                case 22:
                    name = self.names[opa]
                    vglobals[name] = __import__(name)
                case 23:
                    b = pop()
                    a = pop()
                    match opa:
                        case 1:
                            push(a == b)
                        case 3:
                            push(a < b)
                case 24:
                    if not pop():
                        cx = opa
                        continue
                case 25:
                    cx = opa
                    continue
                case 29:
                    values = []
                    for _ in range(opa):
                        values.insert(0, pop())
                    push(tuple(values))
                case 30:
                    values = []
                    for _ in range(opa):
                        values.insert(0, pop())
                    push(values)
                case 32:
                    slice_value = pop()
                    push(pop()[slice_value])
            cx += 2

vm = VM({payload})
vm()
'''


def make_source(bytecode, consts, names):
    payload = pickle.dumps([bytecode, consts, names])
    return VM_SOURCE.replace("{payload}", repr(payload))


@pytest.fixture
def model():
    tree = ast.parse(make_source([21, 0], [None], []))
    models = VMDiscovery().discover(tree)
    assert models, "discovery found no VM"
    return models[0]


# ── discovery + semantics ────────────────────────────────────────────────────

def test_discovers_vm(model):
    assert model.class_name == "VM"
    assert model.instruction_width == 2
    assert model.operand_count == 1


@pytest.mark.parametrize("opcode,expected", [
    (1, VOp.LOAD_CONST),
    (2, VOp.STORE_LOCAL),
    (3, VOp.LOAD_LOCAL),
    (4, VOp.STORE_GLOBAL),
    (5, VOp.LOAD_GLOBAL),
    (6, VOp.BINARY),
    (8, VOp.BINARY),
    (19, VOp.CALL),
    (20, VOp.MAKE_VM),
    (21, VOp.RETURN),
    (22, VOp.IMPORT),
    (23, VOp.COMPARE),
    (24, VOp.JUMP_IF_FALSE),
    (25, VOp.JUMP),
    (29, VOp.BUILD_TUPLE),
    (30, VOp.BUILD_LIST),
    (32, VOp.SUBSCRIPT),
])
def test_opcode_semantics(model, opcode, expected):
    """
    These four are the ones a substring classifier gets wrong:
    19 contains ``*args`` so it reads as a multiply, 20 contains ``vglobals``
    so it reads as a global store, and 30/32 swap with each other.
    """
    assert model.opcodes[opcode].op is expected


def test_operand_roles(model):
    assert model.opcodes[1].operand_role == "const"
    assert model.opcodes[3].operand_role == "name"
    assert model.opcodes[19].operand_role == "count"
    assert model.opcodes[24].operand_role == "target"
    assert model.opcodes[23].operand_role == "selector"


def test_binary_symbols_recovered(model):
    assert model.opcodes[6].symbol == "+"
    assert model.opcodes[8].symbol == "*"


def test_compare_table_recovered(model):
    assert model.opcodes[23].compare_table == {1: "==", 3: "<"}


def test_full_coverage(model):
    assert model.coverage() == 1.0


# ── decoding + CFG ───────────────────────────────────────────────────────────

def test_decode_width(model):
    instrs = decode([1, 0, 21, 0], model)
    assert [i.opcode for i in instrs] == [1, 21]
    assert [i.offset for i in instrs] == [0, 2]


def test_cfg_splits_on_branch(model):
    #  0: LOAD_CONST   2: JUMP_IF_FALSE 6   4: LOAD_CONST   6: RETURN
    instrs = decode([1, 0, 24, 6, 1, 1, 21, 0], model)
    blocks = build_cfg(instrs, model.instruction_width)
    assert 0 in blocks and 4 in blocks and 6 in blocks
    assert blocks[0].kind == "branch"
    assert set(blocks[0].successors) == {4, 6}


# ── end-to-end lifting ───────────────────────────────────────────────────────

def lift(bytecode, consts, names):
    src = make_source(bytecode, consts, names)
    tree = ast.parse(src)
    model = VMDiscovery().discover(tree)[0]
    extractor = PayloadExtractor(model)
    payload, name, arity = extractor.find_payloads(tree)[0]
    program = extractor.build(payload, name, arity)
    return lift_program(program, model)


def test_lifts_call_not_multiply():
    """A discarded-result call must survive as a statement, not vanish."""
    out = lift([5, 0, 1, 0, 19, 1], [], ["print"])
    assert "print()" in out.replace(" ", "") or "print(" in out
    assert "*" not in out


def test_lifts_assignment_and_return():
    out = lift([1, 0, 2, 0, 3, 0, 21, 0], [42], ["value"])
    assert "value = 42" in out
    assert "return value" in out


def test_lifts_binary_expression():
    out = lift([1, 0, 1, 1, 6, 0, 2, 0, 21, 0], [1, 2], ["total"])
    assert "total = (1 + 2)" in out


def test_output_is_valid_python():
    out = lift([1, 0, 2, 0, 3, 0, 21, 0], ["x"], ["value"])
    ast.parse(out)


def test_discarded_call_emitted_before_next_statement():
    """Ordering matters: the bare call precedes the assignment that follows."""
    code = [5, 0, 1, 0, 19, 1,          # print('a')  -> result discarded
            1, 1, 2, 1]                 # value = 'b'
    out = lift(code, ["a", "b"], ["print", "value"])
    lines = [l.strip() for l in out.splitlines() if l.strip() and not l.startswith("def")]
    assert lines.index("print('a')") < lines.index("value = 'b'")


# ── adapter behaviour ────────────────────────────────────────────────────────

def test_has_vm_class_detects_dispatcher():
    assert VMLifter().has_vm_class(make_source([21, 0], [None], []))


def test_has_vm_class_ignores_plain_code():
    assert not VMLifter().has_vm_class("def f():\n    return 1\n")


def test_deobfuscate_reports_opcode_map():
    out = VMLifter().deobfuscate(make_source([1, 0, 2, 0, 21, 0], [7], ["value"]))
    assert "Devirtualized: VM" in out
    assert "load_const" in out
    ast.parse(out)


def test_deobfuscate_preserves_source_when_nothing_lifts():
    src = "x = 1\nprint(x)\n"
    assert VMLifter().deobfuscate(src) == src


def test_malicious_payload_is_refused():
    """A pickle naming a callable must not be reconstructed."""
    from de4py.engines.onyx.vm.bytecode import safe_loads

    class Evil:
        def __reduce__(self):
            return (eval, ("1+1",))

    with pytest.raises(Exception):
        safe_loads(pickle.dumps(Evil()))
