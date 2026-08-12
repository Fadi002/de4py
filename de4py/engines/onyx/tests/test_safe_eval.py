# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import ast

import pytest

from de4py.engines.onyx.safe_eval import safe_eval_source, safe_eval, safe_eval_scalar


def ev(src, env=None):
    return safe_eval_source(src, env)


# ── folding the shapes the corpus actually uses ──────────────────────────────

@pytest.mark.parametrize("src,expected", [
    ("1 + 2 * 3", 7),
    ("'ab' + 'cd'", "abcd"),
    ("'abc'[::-1]", "cba"),
    ("chr(72) + chr(105)", "Hi"),
    ("''.join(chr(c) for c in [104, 105])", "hi"),
    ("bytes([104, 105]).decode()", "hi"),
    ("''.join(map(chr, [104, 105]))", "hi"),
    ("'%c%s' % (65, 'BC')", "ABC"),
    ("len('hello')", 5),
    ("int('ff', 16)", 255),
    ("'a-b-c'.split('-')", ["a", "b", "c"]),
    ("[x ^ 7 for x in [1, 2, 3]]", [6, 5, 4]),
    ("(lambda x: x * 2)(21)", 42),
    ("(lambda a, b: a + b)(1, 2)", 3),
    ("f'{1 + 1}x'", "2x"),
    ("'ab'.upper()", "AB"),
    ("sum([1, 2, 3])", 6),
    ("(1, 2, 3)[1]", 2),
    ("{'k': 'v'}['k']", "v"),
    ("True and 'yes'", "yes"),
    ("3 if 1 < 2 else 4", 3),
])
def test_folds_expected(src, expected):
    ok, value = ev(src)
    assert ok, f"failed to evaluate {src!r}"
    assert value == expected


def test_base64_chain():
    ok, value = ev("base64.b64decode('SGVsbG8=').decode()")
    assert ok and value == "Hello"


def test_zlib_chain():
    import base64 as b64
    import zlib
    blob = b64.b64encode(zlib.compress(b"print(1)")).decode()
    ok, value = ev(f"zlib.decompress(base64.b64decode('{blob}')).decode()")
    assert ok and value == "print(1)"


def test_int_dunder_xor_unbound():
    """The `int.__xor__(a, b)` idiom used by the II/ll-name family."""
    ok, value = ev("int.__xor__(88, 7)")
    assert ok and value == 88 ^ 7


def test_bound_dunder_name():
    """`(5).__mod__.__name__[2:-2]` -> 'mod', used to build attribute names."""
    ok, value = ev("(5).__mod__.__name__[2:-2]")
    assert ok and value == "mod"


def test_int_to_bytes_decode():
    ok, value = ev("(189261444376825831517285514).to_bytes(12, 'big')")
    assert ok
    assert isinstance(value, bytes)


def test_env_lookup():
    ok, value = ev("a + b", {"a": 2, "b": 3})
    assert ok and value == 5


def test_scalar_filter_rejects_containers():
    ok, _ = safe_eval_scalar(ast.parse("[1, 2]", mode="eval").body)
    assert not ok
    ok, value = safe_eval_scalar(ast.parse("'x'", mode="eval").body)
    assert ok and value == "x"


# ── the sandbox must hold ────────────────────────────────────────────────────

@pytest.mark.parametrize("src", [
    # classic subclass-walk escape
    "().__class__.__base__.__subclasses__()",
    "''.__class__.__mro__[1].__subclasses__()",
    "(1).__class__.__bases__",
    "[].__class__.__base__",
    # direct dangerous builtins
    "__import__('os')",
    "eval('1')",
    "exec('1')",
    "compile('1', '<s>', 'eval')",
    "open('x')",
    "globals()",
    "locals()",
    "vars()",
    "dir()",
    "setattr(str, 'x', 1)",
    "type(1)",
    "id(1)",
    "input()",
    "print('x')",
    # module reach-through
    "base64.__dict__",
    "base64.__loader__",
    "zlib.__class__",
    # attribute walks on allowed values
    "'x'.join.__globals__",
    "'x'.encode.__self__",
    "(lambda: 1).__code__",
    # dunder attribute we do not model
    "''.__reduce__()",
    "''.__getattribute__('join')",
    # a lambda handed to a higher-order builtin is still interpreted, so the
    # escape family must stay closed when it is reached through map/sorted
    "list(map(lambda x: __import__('os'), [1]))",
    "list(map(lambda x: eval('1'), [1]))",
    "list(map(lambda x: open('x'), [1]))",
    "list(map(lambda x: globals(), [1]))",
    "list(map(lambda f: f.__globals__, [lambda: 1]))",
    "sorted([1], key=lambda x: ().__class__.__base__.__subclasses__())",
    # the type *name* is modelled, but a type object must never be produced
    "type(1)",
    "type",
    "type(1).__bases__",
    "type(1).__mro__",
    "type(1).mro()",
    "(type(1), 2)",
    "type(1) == 1",
])
def test_escape_attempts_refused(src):
    ok, value = ev(src)
    assert not ok, f"sandbox let {src!r} through -> {value!r}"


@pytest.mark.parametrize("src,expected", [
    ("type(9).__name__", "int"),
    ("type([]).__name__", "list"),
    ("type('a') == type('b')", True),
    ("type(1) == type('a')", False),
    ("type(1) != type('a')", True),
])
def test_type_kind_tests_are_modelled(src, expected):
    """Samples branch on a value's kind; the name answers that without a type object."""
    ok, value = ev(src)
    assert ok, f"{src!r} should fold"
    assert value == expected


@pytest.mark.parametrize("src,expected", [
    ("(0).__class__('87', 16)", 135),
    ("b''.__class__([104, 105])", b"hi"),
    ("''.__class__([104, 105])", "[104, 105]"),
])
def test_dunder_class_spells_a_known_builtin(src, expected):
    """
    ``(0).__class__(...)`` is a common evasion of writing ``int`` literally.
    Every entry in ``_CLASS_ACCESSIBLE`` is already reachable via
    ``PURE_BUILTINS`` under its real name, so resolving ``.__class__`` on one
    of those values grants no capability beyond what a bare ``int``/``bytes``/
    etc. call already grants - it only lets the callee come from a value
    instead of a literal name.
    """
    ok, value = ev(src)
    assert ok, f"{src!r} should fold"
    assert value == expected


@pytest.mark.parametrize("src", [
    # `.__class__` alone is now permitted for known-safe types, but every
    # further hop toward the metaclass walk must still dead-end - this is
    # the actual security boundary, not the attribute access itself.
    "(0).__class__.__base__",
    "(0).__class__.__bases__",
    "(0).__class__.__mro__",
    "(0).__class__.__subclasses__",
    "(0).__class__.__subclasses__()",
    "''.__class__.__base__.__subclasses__()",
    "[].__class__.__class__",
    # a type not in the accessible allowlist must not expose .__class__ either
    "(lambda: 1).__class__",
    "type(1).__class__",
])
def test_dunder_class_chain_still_dead_ends(src):
    ok, value = ev(src)
    assert not ok, f"sandbox let {src!r} through -> {value!r}"


@pytest.mark.parametrize("src,expected", [
    ("getattr(str, 'join')('-', ['a', 'b'])", "a-b"),
    ("getattr('hello', 'upper')()", "HELLO"),
    ("getattr(__import__('base64'), 'b64decode')(b'aGk=')", b"hi"),
    ("getattr(__import__('builtins'), 'ord')('A')", 65),
])
def test_getattr_matches_dot_access(src, expected):
    """
    ``getattr(x, name)`` must resolve exactly like ``x.name`` for any
    already-permitted ``x`` - a stdlib-module stub, a plain value, or the
    builtins stub - since it is the same attribute access, only spelled as a
    call so a sample can compute the name dynamically.
    """
    ok, value = ev(src)
    assert ok, f"{src!r} should fold"
    assert value == expected


@pytest.mark.parametrize("src,expected", [
    ("__import__('json').loads('[1, 2, 3]')", [1, 2, 3]),
    ("__import__('json').dumps([1, 2])", "[1, 2]"),
    ("json.loads('{\"a\": 1}')", {"a": 1}),
])
def test_json_module_is_allowed(src, expected):
    """
    ``json`` is a pure codec exactly like ``base64``/``zlib`` - a custom-VM
    sample commonly ships its bytecode array as
    ``json.loads(zlib.decompress(...))``, and without ``json`` in the
    allowlist that whole decode chain (and the VM payload behind it) is
    unreachable even though every other step in the chain already folds.
    """
    ok, value = ev(src)
    assert ok, f"{src!r} should fold"
    assert value == expected


@pytest.mark.parametrize("src", [
    # getattr(x, name) must refuse exactly what x.name already refuses -
    # neither more (it is not a second escape route) nor less.
    "getattr((0).__class__, '__base__')",
    "getattr('', '__reduce__')",
    "getattr('', '__class__').__base__",
    "getattr(str, '__mro__')",
])
def test_getattr_dunder_chain_still_dead_ends(src):
    ok, value = ev(src)
    assert not ok, f"sandbox let {src!r} through -> {value!r}"


@pytest.mark.parametrize("src,expected", [
    ("__import__('builtins').len", len),
    ("__import__('builtins').chr(65)", "A"),
    ("getattr(__import__('builtins'), 'ord')('A')", 65),
])
def test_import_builtins_reaches_pure_builtins_table(src, expected):
    """
    ``__import__('builtins')`` reaches the exact same ``PURE_BUILTINS`` table
    ``getattr(__builtins__, name)`` already exposes - a sample that spells the
    identity through ``__import__`` instead of the literal ``__builtins__``
    name (common when the obfuscator itself computes both strings) must fold
    the same way.
    """
    ok, value = ev(src)
    assert ok, f"{src!r} should fold"
    assert value == expected


@pytest.mark.parametrize("src", [
    # `builtins` is reachable, but only for names PURE_BUILTINS already
    # trusts - `eval`/`exec`/`compile`/`__import__` itself must never resolve
    # through it, or the whole sandbox boundary collapses to a rename.
    "__import__('builtins').eval",
    "__import__('builtins').exec",
    "__import__('builtins').compile",
    "__import__('builtins').__import__",
    "__import__('builtins').open",
    "getattr(__import__('builtins'), 'eval')",
    "__import__('os')",
    "__import__('sys')",
    "__import__('subprocess')",
])
def test_import_builtins_still_refuses_dangerous_names(src):
    ok, value = ev(src)
    assert not ok, f"sandbox let {src!r} through -> {value!r}"


@pytest.mark.parametrize("src,expected", [
    ("list(map(lambda x: x + 1, range(4)))", [1, 2, 3, 4]),
    ("list(filter(lambda x: x > 1, range(4)))", [2, 3]),
    ("sorted([3, 1, 2], key=lambda x: -x)", [3, 2, 1]),
])
def test_closures_reach_higher_order_builtins(src, expected):
    """An interpreter that cannot fold `map(lambda ...)` cannot read a register file."""
    ok, value = ev(src)
    assert ok, f"{src!r} should fold"
    assert value == expected


def test_no_statements():
    """Only expressions are evaluable; statement text must not slip in."""
    ok, _ = ev("import os")
    assert not ok


def test_unbound_name_is_refused():
    ok, _ = ev("some_undefined_global")
    assert not ok


# ── budgets ──────────────────────────────────────────────────────────────────

def test_pow_bomb_refused():
    ok, _ = ev("9 ** 999999999")
    assert not ok


def test_string_repeat_bomb_refused():
    ok, _ = ev("'a' * 999999999")
    assert not ok


def test_comprehension_bound():
    ok, _ = ev("[x for x in range(10000000)]")
    assert not ok


def test_recursive_lambda_bounded():
    """A self-applying lambda must hit the depth cap, not the host stack."""
    ok, _ = ev("(lambda f: f(f))(lambda f: f(f))")
    assert not ok


def test_large_but_legal_input_still_works():
    ok, value = ev("'ab' * 1000")
    assert ok and len(value) == 2000
