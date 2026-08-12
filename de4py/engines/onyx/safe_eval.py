# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Bounded AST interpreter for constant-folding untrusted samples.

Every other Onyx pass that needs to know "what does this expression evaluate to"
routes through here instead of ``eval``/``exec``. The interpreter never hands a
sample a real frame: callables are only ever drawn from this module's own tables,
attribute access is allowlisted per concrete type, and any dunder name is refused
outright, which closes the ``().__class__.__base__.__subclasses__()`` family of
escapes that a blocklist sandbox leaves open.

Evaluation is metered. A budget bounds visited nodes, comprehension iterations,
call depth and result size, so a sample cannot wedge the pass with a decompression
bomb or unbounded recursion.
"""

import ast
import base64
import binascii
import codecs
import bz2
import hashlib
import json
import lzma
import string
import struct
import zlib

MAX_STEPS = 200_000
MAX_ITERATIONS = 100_000
MAX_CALL_DEPTH = 32
MAX_RESULT_BYTES = 8 * 1024 * 1024
MAX_SEQUENCE_LEN = 1_000_000


class SafeEvalError(Exception):
    """Raised internally when an expression is not safely evaluable."""


class _Budget:
    __slots__ = ("steps", "depth")

    def __init__(self):
        self.steps = 0
        self.depth = 0

    def step(self, cost: int = 1):
        self.steps += cost
        if self.steps > MAX_STEPS:
            raise SafeEvalError("step budget exhausted")


class ExecSink:
    """
    Stands in for ``exec``/``eval`` when folding a self-decoding payload.

    Binding one of these into the environment lets a decode loop run to completion
    under the interpreter while its "execute this now" call is captured as data.
    """

    __slots__ = ("captured",)

    def __init__(self):
        self.captured = []


class _Closure:
    """A lambda captured by the interpreter. Only this module can apply it."""

    __slots__ = ("node", "env")

    def __init__(self, node: ast.Lambda, env: dict):
        self.node = node
        self.env = env


def _check_size(value):
    if isinstance(value, (str, bytes, bytearray)) and len(value) > MAX_RESULT_BYTES:
        raise SafeEvalError("result too large")
    if isinstance(value, (list, tuple, set, frozenset, dict)) and len(value) > MAX_SEQUENCE_LEN:
        raise SafeEvalError("sequence too large")
    return value


def _guard_pow(base, exp, mod=None):
    if mod is None and isinstance(exp, int) and isinstance(base, int):
        if exp > 4096 or (abs(base) > 1 and exp * abs(base).bit_length() > 1_000_000):
            raise SafeEvalError("pow too large")
    return pow(base, exp, mod) if mod is not None else pow(base, exp)


def _is_type_call(node) -> bool:
    """``type(x)`` with exactly one positional argument."""
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "type" and len(node.args) == 1
            and not node.keywords
            and not any(isinstance(a, ast.Starred) for a in node.args))


def _guard_repeat(seq, count):
    if not isinstance(count, int):
        raise SafeEvalError("bad repeat count")
    if count > 0 and len(seq) * count > MAX_RESULT_BYTES:
        raise SafeEvalError("repeat too large")
    return seq * count


def _guard_iter(*args):
    """
    Single-argument ``iter(x)`` only. The two-argument form
    ``iter(callable, sentinel)`` calls ``callable`` repeatedly until it
    returns ``sentinel`` - an arbitrary, unbounded, attacker-controlled call
    loop - which is exactly the capability this sandbox exists to refuse.
    The one-argument form is always safe: it can only ever wrap a value this
    interpreter already produced (a list/tuple/str/dict/... built or decoded
    here), so the resulting iterator can only walk already-bounded data.
    """
    if len(args) != 1:
        raise SafeEvalError("iter() with a callable/sentinel is not allowed")
    return iter(args[0])


def _safe_decompress(fn):
    def wrapper(data, *args):
        result = fn(data)
        return _check_size(result)
    return wrapper


PURE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "ascii": ascii, "bin": bin,
    "bool": bool, "bytearray": bytearray, "bytes": bytes, "chr": chr,
    "complex": complex, "dict": dict, "divmod": divmod, "enumerate": enumerate,
    "filter": filter, "float": float, "format": format, "frozenset": frozenset,
    "hex": hex, "int": int, "iter": _guard_iter, "len": len, "list": list,
    "map": map, "max": max,
    "min": min, "next": next, "oct": oct, "ord": ord, "repr": repr,
    "reversed": reversed,
    "round": round, "set": set, "slice": slice, "sorted": sorted, "str": str,
    "sum": sum, "tuple": tuple, "zip": zip, "pow": _guard_pow,
    "range": range, "hash": hash, "sorted": sorted,
    "True": True, "False": False, "None": None,
}

_MODULE_FUNCS = {
    ("base64", "b64decode"): base64.b64decode,
    ("base64", "b64encode"): base64.b64encode,
    ("base64", "b85decode"): base64.b85decode,
    ("base64", "b85encode"): base64.b85encode,
    ("base64", "b32decode"): base64.b32decode,
    ("base64", "b32encode"): base64.b32encode,
    ("base64", "b16decode"): base64.b16decode,
    ("base64", "b16encode"): base64.b16encode,
    ("base64", "urlsafe_b64decode"): base64.urlsafe_b64decode,
    ("base64", "urlsafe_b64encode"): base64.urlsafe_b64encode,
    ("base64", "a85decode"): base64.a85decode,
    ("zlib", "decompress"): _safe_decompress(zlib.decompress),
    ("zlib", "compress"): zlib.compress,
    ("zlib", "crc32"): zlib.crc32,
    ("bz2", "decompress"): _safe_decompress(bz2.decompress),
    ("bz2", "compress"): bz2.compress,
    ("lzma", "decompress"): _safe_decompress(lzma.decompress),
    ("lzma", "compress"): lzma.compress,
    ("binascii", "unhexlify"): binascii.unhexlify,
    ("binascii", "hexlify"): binascii.hexlify,
    ("binascii", "a2b_base64"): binascii.a2b_base64,
    ("binascii", "b2a_base64"): binascii.b2a_base64,
    ("binascii", "crc32"): binascii.crc32,
    ("codecs", "decode"): codecs.decode,
    ("codecs", "encode"): codecs.encode,
    ("struct", "pack"): struct.pack,
    ("struct", "unpack"): struct.unpack,
    ("struct", "calcsize"): struct.calcsize,
    ("hashlib", "md5"): hashlib.md5,
    ("hashlib", "sha1"): hashlib.sha1,
    ("hashlib", "sha256"): hashlib.sha256,
    ("hashlib", "sha512"): hashlib.sha512,
    ("hashlib", "sha384"): hashlib.sha384,
    ("hashlib", "sha224"): hashlib.sha224,
    ("hashlib", "blake2b"): hashlib.blake2b,
    ("hashlib", "blake2s"): hashlib.blake2s,
    ("hashlib", "new"): hashlib.new,
    ("json", "loads"): json.loads,
    ("json", "dumps"): json.dumps,
    # `string`'s exposed surface is entirely read-only character-set
    # constants, not functions - obfuscators commonly reach `ascii_lowercase`
    # / `digits` / `punctuation` dynamically (`getattr(string_module, name)`)
    # to spell an alphabet without writing it literally.
    ("string", "ascii_letters"): string.ascii_letters,
    ("string", "ascii_lowercase"): string.ascii_lowercase,
    ("string", "ascii_uppercase"): string.ascii_uppercase,
    ("string", "digits"): string.digits,
    ("string", "hexdigits"): string.hexdigits,
    ("string", "octdigits"): string.octdigits,
    ("string", "punctuation"): string.punctuation,
    ("string", "printable"): string.printable,
    ("string", "whitespace"): string.whitespace,
}

SAFE_MODULES = frozenset(name for name, _ in _MODULE_FUNCS)


#: The literal-name path (``getattr(__builtins__, name)``) already resolves any
#: ``PURE_BUILTINS`` entry off the real ``__builtins__`` name; a sample that
#: instead computes the identity via ``__import__('builtins')`` reaches the
#: exact same, already-vetted table under a different spelling, so the
#: two paths are unified through ``_SafeModule`` rather than duplicated.
_BUILTINS_MODULE = "builtins"


class _ImportBuiltin:
    """
    Sentinel for the real ``__import__`` builtin as a *value*, not syntax.

    A packed sample commonly reaches ``__import__`` and ``getattr`` (below)
    through an indirection - ``__import__('builtins').getattr``,
    ``vars(__builtins__)['__import__']`` - rather than the bare name. Special-
    casing the two-argument call shape at every possible call site would mean
    duplicating the same recognition logic per spelling; resolving the name
    to one canonical sentinel here means every spelling that reaches it (name,
    attribute, dict subscript) is handled once, in :meth:`SafeEvaluator.apply`.
    """


class _GetattrBuiltin:
    """Sentinel for the real ``getattr`` builtin as a value. See :class:`_ImportBuiltin`."""


_IMPORT_BUILTIN = _ImportBuiltin()
_GETATTR_BUILTIN = _GetattrBuiltin()


class _SafeModule:
    """Stand-in for an importable module; resolves only allowlisted members."""

    __slots__ = ("name",)

    def __init__(self, name: str):
        self.name = name

    def lookup(self, attr: str):
        if self.name == _BUILTINS_MODULE:
            if attr in PURE_BUILTINS:
                return PURE_BUILTINS[attr]
            if attr == "__import__":
                return _IMPORT_BUILTIN
            if attr == "getattr":
                return _GETATTR_BUILTIN
            raise SafeEvalError(f"builtin not allowed: {attr}")
        fn = _MODULE_FUNCS.get((self.name, attr))
        if fn is None:
            raise SafeEvalError(f"module member not allowed: {self.name}.{attr}")
        return fn


_STR_METHODS = frozenset({
    "capitalize", "casefold", "center", "count", "encode", "endswith",
    "expandtabs", "find", "format", "index", "isalnum", "isalpha", "isascii",
    "isdecimal", "isdigit", "isidentifier", "islower", "isnumeric",
    "isprintable", "isspace", "istitle", "isupper", "join", "ljust", "lower",
    "lstrip", "partition", "removeprefix", "removesuffix", "replace", "rfind",
    "rindex", "rjust", "rpartition", "rsplit", "rstrip", "split", "splitlines",
    "startswith", "strip", "swapcase", "title", "upper", "zfill", "maketrans",
    "translate",
})

_BYTES_METHODS = frozenset({
    "capitalize", "center", "count", "decode", "endswith", "expandtabs",
    "find", "hex", "index", "isalnum", "isalpha", "isascii", "isdigit",
    "islower", "isspace", "istitle", "isupper", "join", "ljust", "lower",
    "lstrip", "partition", "removeprefix", "removesuffix", "replace", "rfind",
    "rindex", "rjust", "rpartition", "rsplit", "rstrip", "split", "splitlines",
    "startswith", "strip", "swapcase", "title", "upper", "zfill", "fromhex",
    "translate",
})

_INT_METHODS = frozenset({
    "bit_length", "bit_count", "to_bytes", "from_bytes", "conjugate",
    "as_integer_ratio",
})

# Mutators are allowed: every container the interpreter can reach was either
# built during this evaluation or handed in as literal data by a pass, so a
# mutation cannot reach host state.
_SEQ_METHODS = frozenset({
    "count", "index", "copy", "append", "extend", "insert", "remove", "pop",
    "clear", "reverse", "sort",
})
_DICT_METHODS = frozenset({
    "get", "keys", "values", "items", "copy", "update", "setdefault", "pop",
    "popitem", "clear",
})
_SET_METHODS = frozenset({
    "union", "intersection", "difference", "symmetric_difference",
    "issubset", "issuperset", "isdisjoint", "copy", "add", "discard",
    "remove", "update", "clear",
})
_HASH_METHODS = frozenset({"hexdigest", "digest", "copy", "update"})

_DUNDER_ARITH = {
    "__add__": lambda a, b: a + b,
    "__sub__": lambda a, b: a - b,
    "__mul__": lambda a, b: a * b,
    "__truediv__": lambda a, b: a / b,
    "__floordiv__": lambda a, b: a // b,
    "__mod__": lambda a, b: a % b,
    "__xor__": lambda a, b: a ^ b,
    "__and__": lambda a, b: a & b,
    "__or__": lambda a, b: a | b,
    "__lshift__": lambda a, b: a << b,
    "__rshift__": lambda a, b: a >> b,
    "__eq__": lambda a, b: a == b,
    "__ne__": lambda a, b: a != b,
    "__lt__": lambda a, b: a < b,
    "__le__": lambda a, b: a <= b,
    "__gt__": lambda a, b: a > b,
    "__ge__": lambda a, b: a >= b,
    "__contains__": lambda a, b: b in a,
    "__len__": lambda a: len(a),
    "__neg__": lambda a: -a,
    "__pos__": lambda a: +a,
    "__invert__": lambda a: ~a,
    "__abs__": lambda a: abs(a),
    "__str__": lambda a: str(a),
    "__repr__": lambda a: repr(a),
    "__int__": lambda a: int(a),
    "__float__": lambda a: float(a),
    "__bool__": lambda a: bool(a),
    "__hash__": lambda a: hash(a),
    "__getitem__": lambda a, b: a[b],
}

_TYPE_NAME_ATTR = "__name__"
_CLASS_ATTR = "__class__"

#: Types whose ``.__class__`` a packed sample may read to spell a builtin
#: indirectly (``(0).__class__('87', 16)`` instead of writing ``int``). Each
#: entry is already a trusted callable via ``PURE_BUILTINS``, so exposing it
#: here grants no new capability - it only lets the *type itself* come from
#: an already-safe value instead of a literal name. Critically this does not
#: reopen ``().__class__.__base__.__subclasses__()``: the blanket dunder
#: refusal below still blocks ``.__base__``/``.__mro__``/etc. on the type
#: object this returns, so the chain dead-ends after one hop.
_CLASS_ACCESSIBLE = (int, float, bool, str, bytes, bytearray, complex,
                     list, tuple, dict, set, frozenset)

_BINOPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: _guard_pow,
    ast.LShift: lambda a, b: a << b,
    ast.RShift: lambda a, b: a >> b,
    ast.BitOr: lambda a, b: a | b,
    ast.BitXor: lambda a, b: a ^ b,
    ast.BitAnd: lambda a, b: a & b,
    ast.MatMult: None,
}

_UNARYOPS = {
    ast.UAdd: lambda a: +a,
    ast.USub: lambda a: -a,
    ast.Not: lambda a: not a,
    ast.Invert: lambda a: ~a,
}

_CMPOPS = {
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
    ast.Is: lambda a, b: a is b,
    ast.IsNot: lambda a, b: a is not b,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


def _method_allowed(obj, attr: str) -> bool:
    if isinstance(obj, str):
        return attr in _STR_METHODS
    if isinstance(obj, bytearray):
        return attr in _BYTES_METHODS or attr in _SEQ_METHODS
    if isinstance(obj, bytes):
        return attr in _BYTES_METHODS
    if isinstance(obj, bool):
        return False
    if isinstance(obj, int):
        return attr in _INT_METHODS
    if isinstance(obj, (list, tuple)):
        return attr in _SEQ_METHODS
    if isinstance(obj, dict):
        return attr in _DICT_METHODS
    if isinstance(obj, (set, frozenset)):
        return attr in _SET_METHODS
    if type(obj).__module__ in ("_hashlib", "hashlib"):
        return attr in _HASH_METHODS
    return False


class SafeEvaluator:
    """Evaluates a restricted expression grammar without executing sample code."""

    def __init__(self, env=None, budget=None):
        self.env = dict(env or {})
        self.budget = budget or _Budget()


    def eval_node(self, node: ast.AST):
        return self._eval(node, self.env)


    def _eval(self, node, env):
        self.budget.step()
        handler = getattr(self, "_n_" + type(node).__name__, None)
        if handler is None:
            raise SafeEvalError(f"unsupported node: {type(node).__name__}")
        return handler(node, env)


    def _n_Expression(self, node, env):
        return self._eval(node.body, env)

    def _n_Constant(self, node, env):
        return node.value

    def _n_List(self, node, env):
        return _check_size([self._eval(e, env) for e in node.elts])

    def _n_Tuple(self, node, env):
        return _check_size(tuple(self._eval(e, env) for e in node.elts))

    def _n_Set(self, node, env):
        return _check_size({self._eval(e, env) for e in node.elts})

    def _n_Dict(self, node, env):
        result = {}
        for k, v in zip(node.keys, node.values):
            if k is None:
                merged = self._eval(v, env)
                if not isinstance(merged, dict):
                    raise SafeEvalError("bad dict unpack")
                result.update(merged)
            else:
                result[self._eval(k, env)] = self._eval(v, env)
        return _check_size(result)

    def _n_JoinedStr(self, node, env):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                parts.append(self._format_value(value, env))
            else:
                raise SafeEvalError("bad f-string part")
        return _check_size("".join(parts))

    def _format_value(self, node, env):
        value = self._eval(node.value, env)
        if node.conversion == 115:
            value = str(value)
        elif node.conversion == 114:
            value = repr(value)
        elif node.conversion == 97:
            value = ascii(value)
        spec = ""
        if node.format_spec is not None:
            spec = self._eval(node.format_spec, env)
            if not isinstance(spec, str):
                raise SafeEvalError("bad format spec")
        return format(value, spec)


    def _n_NamedExpr(self, node, env):
        """
        ``(name := expr)``. Unlike a plain ``Assign`` (a statement, handled
        by :class:`SafeFunctionRunner`), a walrus is an *expression* that can
        appear inside any other expression this evaluator already folds, and
        obfuscators lean on that heavily to sequence side-effect-free
        "statements" through one expression tree (``and``-chains, ternaries).
        ``env`` is the same dict object threaded through every recursive
        ``_eval`` call in one evaluation (only ``_n_Lambda`` ever copies it,
        to snapshot a closure), so writing here is visible to every sibling
        and later subexpression in the same call - exactly assignment's
        real scoping, without needing a separate mutable-scope mechanism.
        """
        if not isinstance(node.target, ast.Name):
            raise SafeEvalError("unsupported walrus target")
        value = self._eval(node.value, env)
        env[node.target.id] = value
        return value

    def _n_Name(self, node, env):
        name = node.id
        if name in env:
            return env[name]
        if name in PURE_BUILTINS:
            return PURE_BUILTINS[name]
        if name == "__import__":
            return _IMPORT_BUILTIN
        if name == "getattr":
            return _GETATTR_BUILTIN
        if name in SAFE_MODULES:
            return _SafeModule(name)
        raise SafeEvalError(f"unbound name: {name}")


    def _n_BinOp(self, node, env):
        op = _BINOPS.get(type(node.op))
        if op is None:
            raise SafeEvalError("unsupported binary operator")
        left = self._eval(node.left, env)
        right = self._eval(node.right, env)
        if isinstance(node.op, ast.Mult) and isinstance(left, (str, bytes, list, tuple)):
            return _check_size(_guard_repeat(left, right))
        if isinstance(node.op, ast.Mult) and isinstance(right, (str, bytes, list, tuple)):
            return _check_size(_guard_repeat(right, left))
        return _check_size(op(left, right))

    def _n_UnaryOp(self, node, env):
        op = _UNARYOPS.get(type(node.op))
        if op is None:
            raise SafeEvalError("unsupported unary operator")
        return op(self._eval(node.operand, env))

    def _n_BoolOp(self, node, env):
        if isinstance(node.op, ast.And):
            result = True
            for value in node.values:
                result = self._eval(value, env)
                if not result:
                    return result
            return result
        result = False
        for value in node.values:
            result = self._eval(value, env)
            if result:
                return result
        return result

    def _n_Compare(self, node, env):
        # `type(a) == type(b)` is a kind test. Comparing the two type *names*
        # answers it without ever binding a type object, keeping the
        # subclass-walk escape closed.
        if (len(node.ops) == 1 and isinstance(node.ops[0], (ast.Eq, ast.NotEq))
                and _is_type_call(node.left)
                and _is_type_call(node.comparators[0])):
            self.budget.step()
            left_name = type(self._eval(node.left.args[0], env)).__name__
            right_name = type(self._eval(node.comparators[0].args[0], env)).__name__
            same = left_name == right_name
            return same if isinstance(node.ops[0], ast.Eq) else not same

        left = self._eval(node.left, env)
        for op, comparator in zip(node.ops, node.comparators):
            fn = _CMPOPS.get(type(op))
            if fn is None:
                raise SafeEvalError("unsupported comparison")
            right = self._eval(comparator, env)
            if not fn(left, right):
                return False
            left = right
        return True

    def _n_IfExp(self, node, env):
        if self._eval(node.test, env):
            return self._eval(node.body, env)
        return self._eval(node.orelse, env)


    def _n_Subscript(self, node, env):
        value = self._eval(node.value, env)
        index = self._eval(node.slice, env)
        return _check_size(value[index])

    def _n_Slice(self, node, env):
        lower = self._eval(node.lower, env) if node.lower is not None else None
        upper = self._eval(node.upper, env) if node.upper is not None else None
        step = self._eval(node.step, env) if node.step is not None else None
        return slice(lower, upper, step)

    def _n_Starred(self, node, env):
        raise SafeEvalError("bare starred expression")


    def _n_Attribute(self, node, env):
        # `type(x).__name__` is modelled as one operation returning a string.
        # The bare name `type` stays unbound: handing a sample the type object
        # itself reopens the subclass-walk escape, whereas the type's *name* is
        # inert data. Samples use this to switch on a value's kind.
        if (node.attr == _TYPE_NAME_ATTR
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "type"
                and len(node.value.args) == 1
                and not node.value.keywords):
            self.budget.step()
            return type(self._eval(node.value.args[0], env)).__name__

        obj = self._eval(node.value, env)
        return self._get_attr(obj, node.attr)

    def _get_attr(self, obj, attr: str):
        if isinstance(obj, _SafeModule):
            return obj.lookup(attr)
        if isinstance(obj, _BoundDunder):
            if attr == _TYPE_NAME_ATTR:
                return obj.name
            raise SafeEvalError(f"attribute refused: {attr}")
        if attr in _DUNDER_ARITH:
            return _BoundDunder(obj, attr)
        if attr == _TYPE_NAME_ATTR and isinstance(obj, type):
            return obj.__name__
        if attr == _CLASS_ATTR and isinstance(obj, _CLASS_ACCESSIBLE):
            return type(obj)
        if attr.startswith("__") or attr.endswith("__"):
            raise SafeEvalError(f"dunder access refused: {attr}")
        if isinstance(obj, type):
            # unbound method on a builtin type, e.g. str.join / int.from_bytes
            if obj is str and attr in _STR_METHODS:
                return getattr(str, attr)
            if obj is bytes and attr in _BYTES_METHODS:
                return getattr(bytes, attr)
            if obj is int and attr in _INT_METHODS:
                return getattr(int, attr)
            raise SafeEvalError(f"type attribute refused: {attr}")
        if not _method_allowed(obj, attr):
            raise SafeEvalError(f"attribute refused: {attr}")
        return getattr(obj, attr)


    def _n_Call(self, node, env):
        # `__builtins__` itself, evaluated as a bare name, is the real
        # builtins module/dict object - which this interpreter never hands
        # out (only per-name lookups through PURE_BUILTINS are trusted). A
        # sample computing `getattr(__builtins__, name)` therefore cannot
        # reach here through the normal argument-evaluation path below; the
        # target has to be recognized syntactically before evaluating it.
        if (isinstance(node.func, ast.Name) and node.func.id == "getattr"
                and len(node.args) == 2 and not node.keywords
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id in ("__builtins__", "builtins")):
            ok, name = safe_eval(node.args[1], env)
            if ok and isinstance(name, str) and name in PURE_BUILTINS:
                return PURE_BUILTINS[name]
            # `getattr(__builtins__, '__import__')` / `getattr(__builtins__,
            # 'getattr')` reach for the two callables that are sentinels
            # rather than PURE_BUILTINS entries - the general
            # `_GetattrBuiltin` path (in `apply`) already resolves both when
            # the target comes from `__import__('builtins')`, so the literal-
            # `__builtins__`-name spelling has to recognize them too, or the
            # two paths silently diverge on the exact same two names.
            if ok and name == "__import__":
                return _IMPORT_BUILTIN
            if ok and name == "getattr":
                return _GETATTR_BUILTIN
            raise SafeEvalError(f"builtin not allowed: {name!r}" if ok
                                else "builtin name unresolved")

        func = self._eval(node.func, env)
        args = []
        for arg in node.args:
            if isinstance(arg, ast.Starred):
                spread = self._eval(arg.value, env)
                if not isinstance(spread, (list, tuple, set, frozenset, str, bytes)):
                    raise SafeEvalError("bad star-arg")
                args.extend(spread)
            else:
                args.append(self._eval(arg, env))
        kwargs = {}
        for kw in node.keywords:
            if kw.arg is None:
                spread = self._eval(kw.value, env)
                if not isinstance(spread, dict):
                    raise SafeEvalError("bad kwargs spread")
                kwargs.update(spread)
            else:
                kwargs[kw.arg] = self._eval(kw.value, env)
        return self.apply(func, args, kwargs)

    def apply(self, func, args, kwargs=None):
        kwargs = kwargs or {}
        self.budget.step(4)
        if isinstance(func, ExecSink):
            # The sample "runs" its payload; we record the argument instead so the
            # caller can splice the decoded source in as real statements.
            if args:
                func.captured.append(args[0])
            return None
        if isinstance(func, _Closure):
            return self._apply_closure(func, args, kwargs)
        if isinstance(func, _BoundDunder):
            return func(*args)
        if isinstance(func, _ImportBuiltin):
            # `__import__('base64')` is extremely common in packed samples,
            # however it is spelled - a bare name, `builtins.__import__`, a
            # dict-subscript lookup. Whichever expression resolved to this
            # sentinel, the call itself is handled once, here.
            if len(args) != 1 or kwargs:
                raise SafeEvalError("import not allowed: unsupported call shape")
            name = args[0]
            if isinstance(name, str) and (name in SAFE_MODULES or name == _BUILTINS_MODULE):
                return _SafeModule(name)
            raise SafeEvalError(f"import not allowed: {name!r}")
        if isinstance(func, _GetattrBuiltin):
            # `getattr(X, name)` resolved through a non-literal target
            # (`getattr(__import__('builtins'), name)`,
            # `getattr(__import__('zlib'), name)`,
            # `getattr('some string', 'split')`) reaches here; the
            # literal-`__builtins__`-name spelling is handled earlier in
            # `_n_Call`, before its unsafe target is evaluated at all.
            # A module stub already knows exactly which attributes it grants
            # via `lookup()`; any other value routes through the same
            # `_get_attr` an ordinary `x.attr` expression would use, so
            # `getattr(x, 'y')` and `x.y` are equally permissive - neither
            # more nor less - which is what "just a different spelling"
            # ought to mean.
            if len(args) != 2 or kwargs:
                raise SafeEvalError("getattr not allowed: unsupported call shape")
            target, name = args
            if not isinstance(name, str):
                raise SafeEvalError(f"getattr not allowed: {target!r}, {name!r}")
            if isinstance(target, _SafeModule):
                return target.lookup(name)
            return self._get_attr(target, name)
        if isinstance(func, _SafeModule):
            raise SafeEvalError("module is not callable")
        if callable(func) and self._is_trusted_callable(func):
            args = [self._as_callback(a) for a in args]
            kwargs = {k: self._as_callback(v) for k, v in kwargs.items()}
            result = func(*args, **kwargs)
            return _check_size(self._materialize(result))
        raise SafeEvalError("call target not allowed")

    def _as_callback(self, value):
        """
        Let a vetted higher-order builtin invoke an interpreted lambda.

        ``map``/``filter``/``sorted`` call their function argument directly, and a
        :class:`_Closure` is deliberately not callable, so the closure is wrapped
        in an adapter that routes back through :meth:`apply`. The body is still
        interpreted under the same budget — this grants no new capability, it
        only lets an allowed builtin reach an already-allowed closure.
        """
        if not isinstance(value, _Closure):
            return value

        def invoke(*args, **kwargs):
            return self._apply_closure(value, list(args), kwargs)

        return invoke

    def _is_trusted_callable(self, func) -> bool:
        if func in _TRUSTED_CALLABLES:
            return True
        # bound methods of concrete values we already vetted via _get_attr
        self_obj = getattr(func, "__self__", None)
        if self_obj is not None:
            return _method_allowed(self_obj, getattr(func, "__name__", "")) or isinstance(
                self_obj, type
            )
        return False

    def _materialize(self, value):
        """Force lazy builtins (map/filter/zip) so budgets actually bind."""
        if isinstance(value, (map, filter, zip, enumerate, reversed)):
            out = []
            for item in value:
                self.budget.step()
                out.append(item)
                if len(out) > MAX_ITERATIONS:
                    raise SafeEvalError("iterator too long")
            return out
        return value

    def _apply_closure(self, closure: _Closure, args, kwargs):
        if self.budget.depth >= MAX_CALL_DEPTH:
            raise SafeEvalError("call depth exceeded")
        spec = closure.node.args
        if spec.posonlyargs or spec.kwonlyargs or spec.kwarg:
            raise SafeEvalError("unsupported lambda signature")
        names = [a.arg for a in spec.args]
        local = dict(closure.env)
        defaults = list(spec.defaults or [])
        if len(args) < len(names) - len(defaults):
            raise SafeEvalError("too few arguments")
        for i, name in enumerate(names):
            if i < len(args):
                local[name] = args[i]
            elif name in kwargs:
                local[name] = kwargs[name]
            else:
                default_index = i - (len(names) - len(defaults))
                if default_index < 0:
                    raise SafeEvalError("missing argument")
                local[name] = self._eval(defaults[default_index], closure.env)
        if spec.vararg:
            local[spec.vararg.arg] = tuple(args[len(names):])
        elif len(args) > len(names):
            raise SafeEvalError("too many arguments")
        self.budget.depth += 1
        try:
            return self._eval(closure.node.body, local)
        finally:
            self.budget.depth -= 1

    def _n_Lambda(self, node, env):
        return _Closure(node, dict(env))


    def _n_ListComp(self, node, env):
        return _check_size(list(self._iter_comp(node, env)))

    def _n_SetComp(self, node, env):
        return _check_size(set(self._iter_comp(node, env)))

    def _n_GeneratorExp(self, node, env):
        return _check_size(list(self._iter_comp(node, env)))

    def _n_DictComp(self, node, env):
        result = {}
        for local in self._iter_scopes(node.generators, env):
            result[self._eval(node.key, local)] = self._eval(node.value, local)
            if len(result) > MAX_ITERATIONS:
                raise SafeEvalError("comprehension too long")
        return _check_size(result)

    def _iter_comp(self, node, env):
        count = 0
        for local in self._iter_scopes(node.generators, env):
            count += 1
            if count > MAX_ITERATIONS:
                raise SafeEvalError("comprehension too long")
            yield self._eval(node.elt, local)

    def _iter_scopes(self, generators, env, index=0):
        if index >= len(generators):
            yield env
            return
        gen = generators[index]
        if gen.is_async:
            raise SafeEvalError("async comprehension")
        iterable = self._eval(gen.iter, env)
        iterable = self._materialize(iterable)
        if not isinstance(iterable, (list, tuple, str, bytes, bytearray, set, frozenset, dict, range)):
            raise SafeEvalError("non-iterable comprehension source")
        for item in iterable:
            self.budget.step()
            local = dict(env)
            self._bind_target(gen.target, item, local)
            if all(self._eval(cond, local) for cond in gen.ifs):
                yield from self._iter_scopes(generators, local, index + 1)

    def _bind_target(self, target, value, env):
        if isinstance(target, ast.Name):
            env[target.id] = value
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            items = list(value)
            star_at = next(
                (i for i, e in enumerate(target.elts) if isinstance(e, ast.Starred)),
                None,
            )
            if star_at is None:
                if len(items) != len(target.elts):
                    raise SafeEvalError("unpack length mismatch")
                for elt, item in zip(target.elts, items):
                    self._bind_target(elt, item, env)
                return
            # Extended unpacking: `a, *b, c = seq` — one starred element
            # collects whatever is left over between the fixed-position ones.
            before, after = target.elts[:star_at], target.elts[star_at + 1:]
            if len(items) < len(before) + len(after):
                raise SafeEvalError("unpack length mismatch")
            for elt, item in zip(before, items):
                self._bind_target(elt, item, env)
            tail_start = len(items) - len(after)
            self._bind_target(target.elts[star_at].value, items[len(before):tail_start], env)
            for elt, item in zip(after, items[tail_start:]):
                self._bind_target(elt, item, env)
            return
        raise SafeEvalError("unsupported comprehension target")


class _Return(Exception):
    """Unwinds a ``return`` out of an interpreted function body."""

    def __init__(self, value):
        self.value = value


class _Break(Exception):
    pass


class _Continue(Exception):
    pass


class SafeFunctionRunner(SafeEvaluator):
    """
    Interprets straight-line function bodies (assign / if / for / while / return).

    Obfuscator decode helpers are usually a short imperative routine rather than a
    single expression, so folding their call sites needs statement support. The
    same allowlists and budget apply, and there is still no host execution.
    """

    _MAX_LOOP = 200_000

    def run_function(self, funcdef, args, kwargs=None):
        kwargs = kwargs or {}
        spec = funcdef.args
        if spec.posonlyargs or spec.kwonlyargs or spec.kwarg or spec.vararg:
            raise SafeEvalError("unsupported function signature")
        names = [a.arg for a in spec.args]
        defaults = list(spec.defaults or [])
        local = dict(self.env)
        for i, name in enumerate(names):
            if i < len(args):
                local[name] = args[i]
            elif name in kwargs:
                local[name] = kwargs[name]
            else:
                default_index = i - (len(names) - len(defaults))
                if default_index < 0:
                    raise SafeEvalError("missing argument")
                local[name] = self._eval(defaults[default_index], local)
        if len(args) > len(names):
            raise SafeEvalError("too many arguments")
        try:
            self._exec_block(funcdef.body, local)
        except _Return as ret:
            return ret.value
        return None

    def _exec_block(self, body, env):
        for stmt in body:
            self._exec(stmt, env)

    def _exec(self, node, env):
        self.budget.step()
        handler = getattr(self, "_s_" + type(node).__name__, None)
        if handler is None:
            raise SafeEvalError(f"unsupported statement: {type(node).__name__}")
        handler(node, env)

    def _s_Pass(self, node, env):
        return

    def _s_Return(self, node, env):
        value = self._eval(node.value, env) if node.value is not None else None
        raise _Return(value)

    def _s_Expr(self, node, env):
        self._eval(node.value, env)

    def _s_Assign(self, node, env):
        value = self._eval(node.value, env)
        for target in node.targets:
            self._assign(target, value, env)

    def _s_AugAssign(self, node, env):
        op = _BINOPS.get(type(node.op))
        if op is None:
            raise SafeEvalError("unsupported augmented operator")
        current = self._eval(node.target, env)
        value = self._eval(node.value, env)
        self._assign(node.target, _check_size(op(current, value)), env)

    def _s_AnnAssign(self, node, env):
        if node.value is not None:
            self._assign(node.target, self._eval(node.value, env), env)

    def _s_If(self, node, env):
        if self._eval(node.test, env):
            self._exec_block(node.body, env)
        else:
            self._exec_block(node.orelse, env)

    def _s_For(self, node, env):
        if node.orelse:
            raise SafeEvalError("for/else unsupported")
        iterable = self._materialize(self._eval(node.iter, env))
        if not isinstance(iterable, (list, tuple, str, bytes, bytearray, set,
                                     frozenset, dict, range)):
            raise SafeEvalError("non-iterable loop source")
        count = 0
        for item in iterable:
            count += 1
            if count > self._MAX_LOOP:
                raise SafeEvalError("loop budget exhausted")
            self.budget.step()
            self._bind_target(node.target, item, env)
            try:
                self._exec_block(node.body, env)
            except _Break:
                break
            except _Continue:
                continue

    def _s_While(self, node, env):
        if node.orelse:
            raise SafeEvalError("while/else unsupported")
        count = 0
        while self._eval(node.test, env):
            count += 1
            if count > self._MAX_LOOP:
                raise SafeEvalError("loop budget exhausted")
            self.budget.step()
            try:
                self._exec_block(node.body, env)
            except _Break:
                break
            except _Continue:
                continue

    def _s_Break(self, node, env):
        raise _Break()

    def _s_Continue(self, node, env):
        raise _Continue()

    def _s_Import(self, node, env):
        # Decoder helpers commonly do their own `import base64` rather than
        # relying on a module-level import, so this must bind the same
        # `_SafeModule` stub the module-level `build_import_env` binds -
        # anything outside `SAFE_MODULES` is silently skipped, same as an
        # unresolved name would be.
        for alias in node.names:
            if alias.name in SAFE_MODULES:
                env[alias.asname or alias.name] = _SafeModule(alias.name)

    def _s_ImportFrom(self, node, env):
        if node.module is None:
            return
        for alias in node.names:
            fn = _MODULE_FUNCS.get((node.module, alias.name))
            if fn is not None:
                env[alias.asname or alias.name] = fn

    def _s_Try(self, node, env):
        # A decoder wrapping its real work in try/except-return-'' is exactly
        # the shape this interpreter exists to fold, so the body runs for
        # real. Only the *handler* bodies are deliberately never executed:
        # this interpreter has no notion of Python's exception-type matching,
        # so running a handler would mean guessing which except clause the
        # sample intended - it never guesses. A SafeEvalError raised inside
        # the try body (or anywhere it calls into) simply propagates through
        # this method uncaught, same as it would from any other statement,
        # which correctly fails the whole fold rather than picking a branch.
        try:
            self._exec_block(node.body, env)
        finally:
            self._exec_block(node.finalbody, env)

    def _assign(self, target, value, env):
        if isinstance(target, ast.Name):
            env[target.id] = value
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            items = list(value)
            if len(items) != len(target.elts):
                raise SafeEvalError("unpack length mismatch")
            for elt, item in zip(target.elts, items):
                self._assign(elt, item, env)
            return
        if isinstance(target, ast.Subscript):
            container = self._eval(target.value, env)
            if not isinstance(container, (list, dict, bytearray)):
                raise SafeEvalError("unsupported subscript assignment")
            container[self._eval(target.slice, env)] = value
            return
        raise SafeEvalError("unsupported assignment target")


def resolves_to_builtins_module(node: ast.AST, env=None) -> bool:
    """
    True when ``node`` evaluates to the ``builtins`` module stub — e.g.
    ``__import__('builtins')`` or ``__builtins__`` when it is the real
    dict-shaped module object. Other callers (:mod:`constant_eval`) need this
    to recognize ``X.exec(...)`` as a real exec call when ``X`` is builtins
    reached indirectly, but the module-stub type is private to this module,
    so the check is exposed as a function rather than the type itself.
    """
    try:
        value = SafeEvaluator(env).eval_node(node)
    except Exception:
        return False
    return isinstance(value, _SafeModule) and value.name == _BUILTINS_MODULE


def safe_call_function(funcdef, args, env=None, kwargs=None):
    """Call an interpreted ``FunctionDef``. Returns ``(ok, value)``."""
    if not isinstance(funcdef, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False, None
    try:
        runner = SafeFunctionRunner(env)
        value = runner.run_function(funcdef, list(args), kwargs)
        if isinstance(value, (_Closure, _SafeModule, _BoundDunder,
                             _ImportBuiltin, _GetattrBuiltin)):
            return False, None
        return True, value
    except SafeEvalError:
        return False, None
    except RecursionError:
        return False, None
    except Exception:
        return False, None


class _BoundDunder:
    """``x.__xor__`` and friends, resolved to a real operation, not an attribute."""

    __slots__ = ("obj", "name")

    def __init__(self, obj, name):
        self.obj = obj
        self.name = name

    def __call__(self, *args):
        fn = _DUNDER_ARITH[self.name]
        # ``int.__xor__(a, b)`` reaches here unbound: the type carries no operand,
        # so the receiver is the first argument instead of ``self.obj``.
        operands = args if isinstance(self.obj, type) else (self.obj,) + args
        try:
            return _check_size(fn(*operands))
        except SafeEvalError:
            raise
        except Exception as exc:
            raise SafeEvalError(str(exc)) from exc


_TRUSTED_CALLABLES = set()
for _fn in PURE_BUILTINS.values():
    if callable(_fn):
        _TRUSTED_CALLABLES.add(_fn)
for _fn in _MODULE_FUNCS.values():
    _TRUSTED_CALLABLES.add(_fn)
_TRUSTED_CALLABLES.update({str.join, str.format, str.maketrans, bytes.fromhex,
                           int.from_bytes, str.encode, bytes.decode})


_SCALAR_TYPES = (int, float, complex, bool, str, bytes, bytearray, type(None))


def build_import_env(tree: ast.AST) -> dict:
    """
    Bind names a module's own ``import``/``from ... import`` statements
    introduce, so a bare reference like ``b64decode(...)`` (from
    ``from base64 import b64decode``) or ``ybgsl.sha256(...)`` (from
    ``import hashlib as ybgsl``) folds the same way the module-qualified
    spelling already does. Only names this maps to an allowlisted function
    or module get bound - importing anything else is silently skipped, same
    as an unresolved name would be.
    """
    env: dict = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name
                if module in SAFE_MODULES:
                    env[alias.asname or module] = _SafeModule(module)
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            if module is None:
                continue
            for alias in node.names:
                fn = _MODULE_FUNCS.get((module, alias.name))
                if fn is not None:
                    env[alias.asname or alias.name] = fn
    return env


def safe_eval(node: ast.AST, env=None):
    """Evaluate a node. Returns ``(ok, value)`` and never raises."""
    try:
        evaluator = SafeEvaluator(env)
        value = evaluator.eval_node(node)
        if isinstance(value, (_Closure, _SafeModule, _BoundDunder,
                             _ImportBuiltin, _GetattrBuiltin)):
            return False, None
        return True, value
    except SafeEvalError:
        return False, None
    except RecursionError:
        return False, None
    except Exception:
        return False, None


def safe_eval_scalar(node: ast.AST, env=None):
    """Like :func:`safe_eval` but only accepts scalar results."""
    ok, value = safe_eval(node, env)
    if ok and isinstance(value, _SCALAR_TYPES):
        return True, value
    return False, None


def safe_eval_source(expression: str, env=None):
    """Parse and evaluate a single expression given as text."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return False, None
    return safe_eval(tree.body, env)


def is_literal_node(node: ast.AST) -> bool:
    """True when a node is a self-contained literal needing no environment."""
    try:
        ast.literal_eval(node)
        return True
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return False
