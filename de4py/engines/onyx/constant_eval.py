# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).

"""Pre-lift AST constant folding + deobfuscation passes."""

import ast
import importlib.util
import re
import subprocess
import sys
from typing import Any, Optional

from de4py.engines.onyx.safe_eval import (
    ExecSink,
    SafeFunctionRunner,
    build_import_env,
    resolves_to_builtins_module,
    safe_call_function,
    safe_eval,
    safe_eval_scalar,
)


def _safe_eval(node: ast.AST, env: Optional[dict] = None):
    return safe_eval_scalar(node, env)


class ConstantExprFolder(ast.NodeTransformer):
    """Bottom-up folder over the safe evaluator; also flattens getattr chains."""

    def __init__(self, env: Optional[dict] = None):
        super().__init__()
        self.env = env
        self.changed = False
        self._tainted: dict = {}

    def _tainted_subtree(self, node: ast.AST) -> bool:
        cached = self._tainted.get(id(node))
        if cached is not None and cached[0] is node:
            return cached[1]
        if isinstance(node, ast.NamedExpr):
            result = True
        else:
            result = any(
                self._tainted_subtree(child)
                for child in ast.iter_child_nodes(node)
            )
        self._tainted[id(node)] = (node, result)
        return result

    def _fold(self, node: ast.AST) -> ast.AST:
        if self._tainted_subtree(node):
            return node
        ok, val = _safe_eval(node, self.env)
        if ok:
            self.changed = True
            return ast.copy_location(ast.Constant(value=val), node)
        return node

    def visit_BinOp(self, node):
        self.generic_visit(node)
        return self._fold(node)

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        return self._fold(node)

    def visit_Call(self, node):
        self.generic_visit(node)

        # Transform getattr(obj, 'attr') → obj.attr (enables further folding)
        if (isinstance(node.func, ast.Name)
                and node.func.id == 'getattr'
                and len(node.args) == 2
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
                and not node.keywords):
            attr_node = ast.Attribute(
                value=node.args[0],
                attr=node.args[1].value,
                ctx=ast.Load()
            )
            ast.copy_location(attr_node, node)
            ok, val = _safe_eval(attr_node)
            if ok:
                self.changed = True
                return ast.copy_location(ast.Constant(value=val), node)
            self.changed = True
            return attr_node

        return self._fold(node)

    def visit_Subscript(self, node):
        self.generic_visit(node)
        return self._fold(node)

    def visit_Attribute(self, node):
        self.generic_visit(node)
        return self._fold(node)

    def visit_JoinedStr(self, node):
        self.generic_visit(node)
        return self._fold(node)

    def visit_IfExp(self, node):
        self.generic_visit(node)
        return self._fold(node)

    def visit_Compare(self, node):
        self.generic_visit(node)
        return self._fold(node)

    def visit_BoolOp(self, node):
        self.generic_visit(node)
        return self._fold(node)


class GlobalsBuiltinResolver(ast.NodeTransformer):
    """globals()['key'] → Name('key')"""

    def visit_Subscript(self, node: ast.Subscript):
        self.generic_visit(node)
        if (isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == 'globals'
                and not node.value.args
                and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)):
            return ast.copy_location(
                ast.Name(id=node.slice.value, ctx=ast.Load()), node)
        return node


class BuiltinsDictUnwrapper(ast.NodeTransformer):
    """Resolve builtins-dict subscript calls (`y['any'](...)` → `any(...)`)."""

    def __init__(self):
        self._builtins_src: set = {'__builtins__'}
        self._builtins_dict: set = set()

    def visit_Module(self, node: ast.Module):
        self._collect_aliases(node)
        self.generic_visit(node)
        return node

    def _collect_aliases(self, node: ast.AST):
        for child in ast.walk(node):
            if not isinstance(child, ast.Assign) or len(child.targets) != 1:
                continue
            tgt = child.targets[0]
            if not isinstance(tgt, ast.Name):
                continue
            val = child.value
            name = tgt.id

            if isinstance(val, ast.Name) and val.id in self._builtins_src:
                self._builtins_src.add(name)
                self._builtins_dict.add(name)
            elif (isinstance(val, ast.Call) and isinstance(val.func, ast.Name)
                    and val.func.id == 'vars' and len(val.args) == 1
                    and not val.keywords
                    and isinstance(val.args[0], ast.Name)
                    and val.args[0].id in self._builtins_src):
                # vars(__builtins__) is the builtins module's own __dict__ —
                # the same lookup table __builtins__['name'] would use.
                self._builtins_dict.add(name)
            elif isinstance(val, ast.IfExp):
                body_name = val.body.id if isinstance(val.body, ast.Name) else None
                orelse_obj = (
                    val.orelse.value.id
                    if (isinstance(val.orelse, ast.Attribute)
                        and isinstance(val.orelse.value, ast.Name)
                        and val.orelse.attr == '__dict__')
                    else None
                )
                if body_name in self._builtins_src or orelse_obj in self._builtins_src:
                    self._builtins_dict.add(name)

        self._builtins_dict.update(self._builtins_src)

    def visit_Subscript(self, node: ast.Subscript):
        self.generic_visit(node)
        if (isinstance(node.value, ast.Name)
                and node.value.id in self._builtins_dict
                and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)):
            return ast.copy_location(
                ast.Name(id=node.slice.value, ctx=ast.Load()), node)
        return node


class ASTConstantPropagator(ast.NodeTransformer):
    """Inline module-level constant assignments so their uses can fold."""

    def __init__(self):
        self._const_map= {}

    def _collect(self, stmts: list):
        for node in stmts:
            if (not isinstance(node, ast.Assign)
                    or len(node.targets) != 1
                    or not isinstance(node.targets[0], ast.Name)):
                continue
            val = node.value
            name = node.targets[0].id
            if isinstance(val, ast.Constant):
                self._const_map[name] = val.value
            elif (isinstance(val, ast.List)
                    and all(isinstance(e, ast.Constant) for e in val.elts)):
                # Track all-constant lists too (used by key-search loops)
                self._const_map[name] = [e.value for e in val.elts]

    def visit_Module(self, node: ast.Module):
        self._collect(node.body)
        self.generic_visit(node)
        return node

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Load) and node.id in self._const_map:
            return ast.copy_location(
                ast.Constant(value=self._const_map[node.id]), node)
        return node


_SAFE_SCALAR = (str, int, float, bool, bytes, type(None))


def _as_literal_node(value: Any) -> Optional[ast.expr]:
    """ast node reproducing ``value``, or None if it holds anything unsafe.
    Recurses so containers of containers fold in one shot."""
    if isinstance(value, _SAFE_SCALAR):
        return ast.Constant(value=value)
    if isinstance(value, (list, tuple)):
        raw = [_as_literal_node(v) for v in value]
        if any(e is None for e in raw):
            return None
        elts = [e for e in raw if e is not None]
        cls = ast.List if isinstance(value, list) else ast.Tuple
        return cls(elts=elts, ctx=ast.Load())
    if isinstance(value, dict):
        keys, vals = [], []
        for k, v in value.items():
            kn, vn = _as_literal_node(k), _as_literal_node(v)
            if kn is None or vn is None:
                return None
            keys.append(kn)
            vals.append(vn)
        return ast.Dict(keys=keys, values=vals)
    return None


class TupleUnpackConstantFolder(ast.NodeTransformer):
    """
    Evaluates constant-pool assignments — ``a, b, c = <expr>`` or
    ``name = <expr>`` — where the RHS folds to a container.

    ``safe_eval_scalar`` deliberately refuses container results, so this
    pass uses the full interpreter. Tuple unpack is gated on a same-length
    flat name LHS, since an unpack changes meaning when lengths disagree.
    """

    def visit_Assign(self, node: ast.Assign):
        self.generic_visit(node)
        if len(node.targets) != 1:
            return node
        target = node.targets[0]

        if isinstance(target, ast.Name):
            if isinstance(node.value, (ast.Constant, ast.List, ast.Tuple, ast.Dict)):
                return node
            ok, value = safe_eval(node.value)
            if not ok or not isinstance(value, (list, tuple, dict)):
                return node
            literal = _as_literal_node(value)
            if literal is None:
                return node
            node.value = ast.copy_location(literal, node.value)
            return node

        if not (isinstance(target, (ast.Tuple, ast.List))
                and target.elts
                and all(isinstance(e, ast.Name) for e in target.elts)):
            return node
        if isinstance(node.value, (ast.Tuple, ast.List)):
            return node

        ok, value = safe_eval(node.value)
        if not ok or not isinstance(value, (tuple, list)):
            return node
        if len(value) != len(target.elts):
            return node
        if not all(isinstance(v, _SAFE_SCALAR) for v in value):
            return node

        node.value = ast.copy_location(
            ast.Tuple(elts=[ast.Constant(value=v) for v in value], ctx=ast.Load()),
            node.value,
        )
        return node


class DeadAssignmentEliminator(ast.NodeTransformer):
    """Remove function-local constant assignments whose name is never read.
    Only constants (no side effects) targeting a name never loaded again."""

    def _eliminate(self, stmts: list) -> list:
        used: set = set()
        for stmt in stmts:
            for n in ast.walk(stmt):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                    used.add(n.id)

        result = []
        for stmt in stmts:
            if (isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and isinstance(stmt.value, ast.Constant)
                    and stmt.targets[0].id not in used):
                continue
            result.append(stmt)
        return result

    def _visit_body(self, node):
        self.generic_visit(node)
        node.body = self._eliminate(node.body)
        return node

    def visit_FunctionDef(self, node):
        return self._visit_body(node)

    visit_AsyncFunctionDef = visit_FunctionDef


class PureFunctionInliner(ast.NodeTransformer):
    """Inline pure decode helpers at call sites whose arguments are literals."""

    def __init__(self):
        self._xor_funcs= {}
        self._join_funcs= {}

    def visit_Module(self, node: ast.Module):
        self._collect_pure_funcs(node)
        self.generic_visit(node)
        return node

    def _collect_pure_funcs(self, module: ast.Module):
        for stmt in module.body:
            if not isinstance(stmt, ast.FunctionDef):
                continue
            if len(stmt.body) != 1 or not isinstance(stmt.body[0], ast.Return):
                continue
            ret = stmt.body[0].value
            if ret is None:
                continue
            name = stmt.name
            xor_info = self._extract_xor_pattern(ret, stmt)
            if xor_info:
                self._xor_funcs[name] = xor_info

    def _extract_xor_pattern(self, expr, func_def):
        """Match bytes([VAR ^ KEY for VAR in PARAM]).decode(ENC); return (key, enc) or None."""
        # Normalize getattr(..., 'decode')(enc) → ....decode(enc)
        if (isinstance(expr, ast.Call)
                and isinstance(expr.func, ast.Attribute)
                and expr.func.attr == 'decode'):
            inner = expr.func.value
            enc = expr.args[0].value if expr.args and isinstance(expr.args[0], ast.Constant) else 'utf-8'
        else:
            return None

        if not (isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Name)
                and inner.func.id == 'bytes'
                and len(inner.args) == 1):
            return None

        comp = inner.args[0]
        if not isinstance(comp, ast.ListComp):
            return None

        if len(comp.generators) != 1:
            return None
        gen = comp.generators[0]
        if not (isinstance(gen.target, ast.Name)
                and isinstance(gen.iter, ast.Name)):
            return None

        loop_var = gen.target.id
        param_var = gen.iter.id

        if not func_def.args.args or func_def.args.args[0].arg != param_var:
            return None

        # elt must be loop_var ^ KEY or KEY ^ loop_var
        elt = comp.elt
        if not isinstance(elt, ast.BinOp) or not isinstance(elt.op, ast.BitXor):
            return None

        key = None
        if isinstance(elt.left, ast.Name) and elt.left.id == loop_var and isinstance(elt.right, ast.Constant):
            key = elt.right.value
        elif isinstance(elt.right, ast.Name) and elt.right.id == loop_var and isinstance(elt.left, ast.Constant):
            key = elt.left.value

        if key is None or not isinstance(key, int):
            return None

        return (key, enc)

    def visit_Call(self, node: ast.Call):
        self.generic_visit(node)

        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id

        if func_name and func_name in self._xor_funcs and len(node.args) == 1:
            arg = node.args[0]
            if (isinstance(arg, ast.List)
                    and all(isinstance(e, ast.Constant) and isinstance(e.value, int)
                            for e in arg.elts)):
                key, enc = self._xor_funcs[func_name]
                try:
                    result = bytes(e.value ^ key for e in arg.elts).decode(enc)
                    return ast.copy_location(ast.Constant(value=result), node)
                except Exception:
                    pass

        return node


def _is_library_module(node: ast.Module) -> bool:
    """True when the module only defines things and never runs code at import.
    Its top-level names are public API, so dead-definition removal would
    destroy the file; obfuscated payloads always execute at top level."""
    for stmt in node.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                             ast.Import, ast.ImportFrom)):
            continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            continue
        if isinstance(stmt, (ast.Assign, ast.AnnAssign)) and not any(
            isinstance(n, ast.Call) for n in ast.walk(stmt)
        ):
            continue
        return False
    return True


class DeadFunctionEliminator(ast.NodeTransformer):
    """Remove module-level functions whose name never appears as a Load."""

    def visit_Module(self, node: ast.Module):
        if _is_library_module(node):
            return node

        defined = {
            stmt.name
            for stmt in node.body
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if not defined:
            return node

        used: set = set()
        for stmt in node.body:
            func_name = getattr(stmt, 'name', None)
            for n in ast.walk(stmt):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Don't count the name as a use within its own definition
                    if n.name == func_name:
                        continue
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                    used.add(n.id)

        dead = defined - used
        if not dead:
            return node

        node.body = [
            stmt for stmt in node.body
            if not (isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and stmt.name in dead)
        ]
        return node


class EvalNameUnwrapper(ast.NodeTransformer):
    """Convert eval(b'name') / X.eval(b'name') → Name('name')."""
    _IDENT = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

    def _try_unwrap(self, node: ast.Call) -> ast.AST:
        if (len(node.args) == 1
                and isinstance(node.args[0], ast.Constant)
                and not node.keywords):
            val = node.args[0].value
            if isinstance(val, (str, bytes)):
                name = val.decode('utf-8') if isinstance(val, bytes) else val
                if self._IDENT.match(name):
                    return ast.copy_location(
                        ast.Name(id=name, ctx=ast.Load()), node)
        return node

    def visit_Call(self, node: ast.Call):
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id == 'eval':
            return self._try_unwrap(node)
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'eval':
            return self._try_unwrap(node)
        return node


class EvalExecUnwrapper(ast.NodeTransformer):
    """eval(b'exec')(payload) → exec(payload)."""

    def visit_Call(self, node: ast.Call):
        self.generic_visit(node)
        if (isinstance(node.func, ast.Call)
                and isinstance(node.func.func, ast.Name)
                and node.func.func.id == 'eval'
                and len(node.func.args) == 1
                and isinstance(node.func.args[0], ast.Constant)
                and node.func.args[0].value in (b'exec', 'exec')
                and not node.func.keywords):
            exec_call = ast.Call(
                func=ast.Name(id='exec', ctx=ast.Load()),
                args=node.args,
                keywords=node.keywords
            )
            return ast.copy_location(exec_call, node)
        return node


class DeadClassEliminator(ast.NodeTransformer):
    def visit_Module(self, node: ast.Module):
        if _is_library_module(node):
            return node

        defined = {s.name for s in node.body if isinstance(s, ast.ClassDef)}
        if not defined:
            return node
        used: set = set()
        for stmt in node.body:
            for n in ast.walk(stmt):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                    used.add(n.id)
        dead = defined - used
        if not dead:
            return node
        node.body = [s for s in node.body
                     if not (isinstance(s, ast.ClassDef) and s.name in dead)]
        return node


class ConstantForLoopEvaluator(ast.NodeTransformer):
    """
    Evaluates key-search for-loops whose body exec()s a computed payload:

        for key in range(1, N):
            if list[i] ^ key == list[j]:
                exec(decompress(bytes(x ^ key for x in list[...])))
                break

    Runs the loop in the sandbox with exec captured, decodes the payload,
    and replaces the for-loop with the decoded statements.
    """

    def __init__(self, const_map: dict):
        # const_map: name → Python value (scalars and lists)
        self._const_map = {k: v for k, v in const_map.items()
                           if isinstance(v, (int, float, str, bytes, bool,
                                             type(None), list, tuple))}

    def visit_Module(self, node: ast.Module):
        self.generic_visit(node)
        new_body = []
        for stmt in node.body:
            replacement = self._try_eval_for(stmt)
            if replacement is not None:
                new_body.extend(replacement)
            else:
                new_body.append(stmt)
        node.body = new_body
        return node

    def _try_eval_for(self, node: ast.AST):
        if not isinstance(node, ast.For):
            return None
        if not (isinstance(node.iter, ast.Call)
                and isinstance(node.iter.func, ast.Name)
                and node.iter.func.id == 'range'):
            return None
        bounds = []
        for arg in node.iter.args:
            ok, value = safe_eval_scalar(arg)
            if not ok or not isinstance(value, int):
                return None
            bounds.append(value)
        if not bounds:
            return None
        try:
            rng = range(*bounds)
        except (TypeError, ValueError):
            return None
        if len(rng) > 100_000:  # sanity guard
            return None

        # The loop runs under the AST interpreter; exec/eval are bound to a
        # sink that records the payload as data.
        sink = ExecSink()
        env = dict(self._const_map)
        env['exec'] = sink
        env['eval'] = sink

        runner = SafeFunctionRunner(env)
        try:
            runner._exec(node, runner.env)
        except Exception:
            return None

        if not sink.captured:
            return None

        payload = sink.captured[0]
        if isinstance(payload, bytes):
            try:
                payload = payload.decode('utf-8')
            except Exception:
                return None
        if not isinstance(payload, str):
            return None

        try:
            inner = ast.parse(payload)
            ast.fix_missing_locations(inner)
            return inner.body if inner.body else None
        except SyntaxError:
            return None


class MarshalPayloadEvaluator(ast.NodeTransformer):
    """
    Recovers ``exec(marshal.loads(BYTES))`` / bare ``marshal.loads(BYTES)``
    payloads. ``marshal.loads`` only deserializes a code object and never
    executes, so calling it directly is safe; the code object is handed to
    the xdis-backed Decompiler for source recovery. When no backend
    succeeds the call is replaced with a short note rather than a
    multi-megabyte bytes literal.
    """

    MAX_BYTES = 8 * 1024 * 1024

    def __init__(self):
        self._spliced_ids = set()

    def visit_Module(self, node: ast.Module):
        # Statement positions are replaced first: only they can hold the
        # recovered source. Anything visit_Call reaches is nested inside a
        # larger expression, where the best outcome is a compact note.
        node.body = self._process(node.body)
        self.generic_visit(node)
        return node

    def _process(self, stmts: list) -> list:
        out = []
        for stmt in stmts:
            replacement = self._try_replace_stmt(stmt)
            out.extend(replacement if replacement is not None else [stmt])
        return out

    @staticmethod
    def _is_marshal_loads(call) -> bool:
        return (isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == 'loads'
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == 'marshal'
                and len(call.args) == 1 and not call.keywords)

    def _eval_marshal_bytes(self, call) -> Any:
        """Evaluate the argument through safe_eval rather than requiring a
        pre-folded literal — it is usually a decode/decompress chain."""
        if not self._is_marshal_loads(call) or id(call) in self._spliced_ids:
            return None
        ok, value = safe_eval(call.args[0])
        if not ok or not isinstance(value, (bytes, bytearray)):
            return None
        value = bytes(value)
        return value if len(value) <= self.MAX_BYTES else None

    def visit_Call(self, node: ast.Call):
        self.generic_visit(node)
        raw = self._eval_marshal_bytes(node)
        if raw is None:
            return node
        info = _unmarshal_best_effort(raw)
        if info is None:
            note = f"marshal payload ({len(raw)} bytes): could not be unmarshaled under any available Python interpreter"
        else:
            version, name, argcount, code_len = info
            note = (f"marshal payload: verified code object under Python {version} "
                     f"({code_len} bytecode bytes, name={name!r}, {argcount} args) — "
                     "no decompiler backend available to recover source")
        return ast.copy_location(ast.Constant(value=note), node)

    def _try_replace_stmt(self, stmt):
        call = None
        if (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
                and isinstance(stmt.value.func, ast.Name)
                and stmt.value.func.id == 'exec'
                and len(stmt.value.args) == 1 and not stmt.value.keywords):
            call = stmt.value.args[0]
        elif isinstance(stmt, ast.Expr):
            call = stmt.value

        raw = self._eval_marshal_bytes(call) if call is not None else None
        if raw is None:
            return None
        self._spliced_ids.add(id(call))

        info = _unmarshal_best_effort(raw)
        if info is None:
            note = (f"marshal payload ({len(raw)} bytes): could not be unmarshaled "
                     "under any available Python interpreter — bytecode format is "
                     "version-specific, and none of the interpreters on this machine "
                     "produced a valid code object")
            return [ast.Expr(value=ast.Constant(value=note))]

        version, name, argcount, code_len = info
        if version == _THIS_PYTHON:
            source = self._decompile(raw)
            if source:
                try:
                    inner = ast.parse(source)
                    ast.fix_missing_locations(inner)
                    if inner.body:
                        return inner.body
                except SyntaxError:
                    pass

        note = (f"marshal payload: round-trip-verified as a code object under "
                f"Python {version} ({code_len} top-level bytecode bytes, "
                f"name={name!r}, {argcount} args) but no decompiler backend "
                f"available — install decompile3/uncompyle6/pycdc to recover source")
        return [ast.Expr(value=ast.Constant(value=note))]

    def _decompile(self, raw: bytes) -> Optional[str]:
        try:
            from de4py.engines.onyx.decompiler import Decompiler
            header = importlib.util.MAGIC_NUMBER + b"\x00" * 12
            result = Decompiler().decompile_from_bytes(header + raw)
        except Exception:
            return None
        if result and "ERROR: All decompilers failed" not in result:
            return result
        return None


_THIS_PYTHON = "%d.%d" % sys.version_info[:2]

_UNMARSHAL_PROBE = (
    "import marshal,sys\n"
    "data=sys.stdin.buffer.read()\n"
    "try:\n"
    "    code=marshal.loads(data)\n"
    "    redumped=marshal.dumps(code)\n"
    "except Exception:\n"
    "    sys.exit(1)\n"
    "co_code=getattr(code,'co_code',None)\n"
    "if co_code is None or len(redumped)!=len(data):\n"
    "    sys.exit(1)\n"
    "sys.stdout.write('%r\\t%r\\t%d' % (code.co_name, code.co_argcount, len(co_code)))\n"
)

_interpreter_cache: Optional[list] = None


def _candidate_interpreters() -> list:
    """This machine's Python interpreters, current one first. Marshal bytecode
    is tied to the exact build that compiled it, and the wrong interpreter can
    silently produce a garbage code object, so one is not enough."""
    global _interpreter_cache
    if _interpreter_cache is not None:
        return _interpreter_cache

    candidates = [sys.executable]
    try:
        out = subprocess.run(["py", "-0p"], capture_output=True, text=True, timeout=5)
        for line in out.stdout.splitlines():
            path = line.strip().split()[-1] if line.strip() else ""
            if path.lower().endswith((".exe",)) and path not in candidates:
                candidates.append(path)
    except Exception:
        pass
    _interpreter_cache = candidates
    return candidates


def _unmarshal_best_effort(raw: bytes):
    """
    Unmarshal ``raw`` as a code object, validating the result rather than
    trusting a non-exception. Runs in a subprocess: ``marshal.loads`` is a
    C-level deserializer with no safety contract against malformed input and
    can genuinely segfault, so a crash must not take down the analysis.
    Returns (version_str, co_name, co_argcount, len(co_code)) or None.
    """
    for interp in _candidate_interpreters():
        try:
            proc = subprocess.run(
                [interp, "-c", _UNMARSHAL_PROBE],
                input=raw, capture_output=True, timeout=10,
            )
        except Exception:
            continue
        if proc.returncode != 0 or not proc.stdout:
            continue
        try:
            name_r, argcount_r, code_len_r = proc.stdout.decode().split("\t")
            version = re.search(r"(\d+\.\d+)", interp)
            version = version.group(1) if version else "?"
            return version, ast.literal_eval(name_r), int(argcount_r), int(code_len_r)
        except Exception:
            continue
    return None


def _run_fold(tree: ast.AST, passes: int = 8, env: Optional[dict] = None) -> ast.AST:
    for _ in range(passes):
        folder = ConstantExprFolder(env)
        tree = folder.visit(tree)
        if not folder.changed:
            break
    return tree


def fold_constants(source: str) -> str:
    """Run the full pre-lift deobfuscation pipeline on Python source text."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    original_dump = ast.dump(tree)

    try:
        # Names the module's own import statements introduce (`from base64
        # import b64decode`, `import hashlib as ybgsl`, ...) so the folder
        # resolves them the same way it already resolves the module-qualified
        # spelling. Rebuilt every pass since a fold can surface new imports
        # (e.g. after unwrapping a dynamic-import call).
        env = build_import_env(tree)

        # Pass 0: eval(b'name') → Name('name') — must be FIRST so subsequent
        # folds can see getattr/exec/etc. as plain names
        tree = EvalNameUnwrapper().visit(tree)

        # Pass 1: fold constants so lambda args become string literals
        tree = _run_fold(tree, 8, env)

        # Pass 1b: evaluate bulk constant-pool unpacks — `a, b, ... = <expr>`
        # where <expr> folds (via the full interpreter, not the scalar-only
        # folder above) to a same-length tuple of scalars.
        tree = TupleUnpackConstantFolder().visit(tree)

        # Pass 2: resolve globals()['key'] → Name('key')
        tree = GlobalsBuiltinResolver().visit(tree)

        # Pass 2b: re-run EvalNameUnwrapper after first fold (some eval(b'x') may
        # only be visible after the first fold unlocks them)
        tree = EvalNameUnwrapper().visit(tree)

        # Pass 3: fold again (may unlock more after globals resolution)
        env = build_import_env(tree)
        tree = _run_fold(tree, 4, env)

        # Pass 4: unwrap builtins-dict subscript calls
        tree = BuiltinsDictUnwrapper().visit(tree)

        # Pass 5: propagate module-level constants (for multi-variable b64 patterns)
        tree = ASTConstantPropagator().visit(tree)

        # Pass 6: final fold (string concat of propagated constants, etc.)
        tree = _run_fold(tree, 4, env)

        # Pass 7: inline pure XOR/decode functions at call sites
        tree = PureFunctionInliner().visit(tree)
        tree = _run_fold(tree, 2, env)

        # Pass 8: remove dead constant assignments in functions
        tree = DeadAssignmentEliminator().visit(tree)

        # Pass 9: remove functions/classes never referenced
        tree = DeadFunctionEliminator().visit(tree)
        tree = DeadClassEliminator().visit(tree)

        # Pass 10: eval(b'exec')(payload) → exec(payload)
        tree = EvalExecUnwrapper().visit(tree)
        tree = _run_fold(tree, 2)

        # Pass 11: evaluate any remaining pure functions with constant args
        tree = PureFunctionEvaluator().visit(tree)
        tree = _run_fold(tree, 2)
        # Re-eliminate dead functions exposed by inlining
        tree = DeadFunctionEliminator().visit(tree)

        # Pass 11b: evaluate for-loops over constant data with exec payloads
        # Collect current module-level constants (including lists) for sandbox
        _cmap= {}
        for _s in tree.body:
            if (isinstance(_s, ast.Assign)
                    and len(_s.targets) == 1
                    and isinstance(_s.targets[0], ast.Name)):
                _v = _s.value
                if isinstance(_v, ast.Constant):
                    _cmap[_s.targets[0].id] = _v.value
                elif (isinstance(_v, ast.List)
                        and all(isinstance(_e, ast.Constant) for _e in _v.elts)):
                    _cmap[_s.targets[0].id] = [_e.value for _e in _v.elts]
        tree = ConstantForLoopEvaluator(_cmap).visit(tree)
        tree = _run_fold(tree, 2)
        tree = DeadFunctionEliminator().visit(tree)
        tree = DeadClassEliminator().visit(tree)

        # Pass 11c: recover exec(marshal.loads(BYTES)) compiled-bytecode payloads
        tree = MarshalPayloadEvaluator().visit(tree)

        # Pass 11d: recover exec(<expr>) when <expr> folds to source text.
        # After the marshal pass: bytes that happen to parse as Python must
        # not be mistaken for source when they were meant for marshal.loads.
        tree = TopLevelExecUnwrapper().visit(tree)
        tree = _run_fold(tree, 4, env)

        # Pass 12: remove junk no-op expression statements
        tree = JunkStatementCleaner().visit(tree)

        # Pass 13: normalize import aliases for known-safe modules
        tree = ImportAliasNormalizer().visit(tree)
        ast.fix_missing_locations(tree)

        if ast.dump(tree) == original_dump:
            return source
        return ast.unparse(tree)
    except Exception:
        return source


class PureFunctionEvaluator(ast.NodeTransformer):
    """Evaluate module-level decode helpers at constant call sites.
    The helper is never compiled or executed: its FunctionDef is kept as data
    and re-interpreted by the bounded AST interpreter, so a helper reaching
    for I/O or attribute escapes simply fails to fold."""

    def __init__(self):
        self._funcs = {}   # name → ast.FunctionDef

    def visit_Module(self, node: ast.Module):
        self._collect(node)
        self.generic_visit(node)
        return node

    def _collect(self, module: ast.Module):
        for stmt in module.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._funcs[stmt.name] = stmt

    def visit_Call(self, node: ast.Call):
        self.generic_visit(node)

        if not (isinstance(node.func, ast.Name)
                and node.func.id in self._funcs
                and not node.keywords):
            return node

        args = []
        for a in node.args:
            ok, value = safe_eval(a)
            if not ok:
                return node
            args.append(value)

        ok, result = safe_call_function(self._funcs[node.func.id], args)
        if not ok:
            return node
        if isinstance(result, (str, int, float, bytes, bool, type(None))):
            return ast.copy_location(ast.Constant(value=result), node)
        # Decoders commonly return a whole pool a VM indexes; reuse the
        # recursive literal builder rather than dropping non-scalar results.
        literal = _as_literal_node(result)
        if literal is not None:
            return ast.copy_location(literal, node)

        return node


_PURE_BUILTINS = frozenset({
    'len', 'str', 'int', 'float', 'bool', 'bytes', 'list', 'tuple',
    'dict', 'set', 'repr', 'hex', 'oct', 'bin', 'abs', 'min', 'max',
    'sorted', 'reversed', 'sum', 'any', 'all', 'zip', 'map', 'filter',
    'enumerate', 'range', 'id', 'type', 'hash', 'dir', 'vars', 'callable',
})


def _is_pure_expr(node: ast.AST) -> bool:
    """True if node has no side effects (safe to discard as a statement)."""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.Name, ast.Attribute)):
        return True
    if isinstance(node, (ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare)):
        return all(_is_pure_expr(c) for c in ast.walk(node)
                   if c is not node and isinstance(c, ast.expr))
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(_is_pure_expr(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return all(_is_pure_expr(e) for e in (node.keys + node.values) if e)
    if isinstance(node, ast.Call):
        func_name = ''
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif (isinstance(node.func, ast.Attribute)
              and isinstance(node.func.value, ast.Constant)):
            func_name = node.func.attr  # e.g. ''.join(...)
        if func_name in _PURE_BUILTINS:
            return all(_is_pure_expr(a) for a in node.args)
    return False


class TopLevelExecUnwrapper(ast.NodeTransformer):
    """
    Splice ``exec(<expr>)`` in place when ``<expr>`` folds to Python source
    text — the text-payload sibling of ``MarshalPayloadEvaluator``. The
    argument is evaluated through safe_eval, never a real exec; the
    recovered source is spliced in as data, never executed.
    """

    def __init__(self):
        self._spliced_ids = set()

    def visit_Module(self, node: ast.Module):
        node.body = self._process(node.body)
        self.generic_visit(node)
        return node

    def _process(self, stmts: list) -> list:
        out = []
        for stmt in stmts:
            replacement = self._try_replace_stmt(stmt)
            out.extend(replacement if replacement is not None else [stmt])
        return out

    @staticmethod
    def _callee_is_exec(func: ast.expr) -> bool:
        """Also recognize ``__import__('builtins').exec`` — both spellings
        name the same real function."""
        if isinstance(func, ast.Name):
            return func.id == 'exec'
        if isinstance(func, ast.Attribute) and func.attr == 'exec':
            return resolves_to_builtins_module(func.value)
        return False

    @staticmethod
    def _callee_is_compile(func: ast.expr) -> bool:
        """Same recognition as :meth:`_callee_is_exec`, for ``compile(...)``."""
        if isinstance(func, ast.Name):
            return func.id == 'compile'
        if isinstance(func, ast.Attribute) and func.attr == 'compile':
            return resolves_to_builtins_module(func.value)
        return False

    def _payload_expr(self, call_arg: ast.expr) -> ast.expr:
        """exec's real argument, peeling one layer of ``compile(source,
        filename, mode)`` if present. compile stays on the dangerous-builtins
        list, so the wrapper is peeled here; only ``source`` is evaluated."""
        if (isinstance(call_arg, ast.Call) and self._callee_is_compile(call_arg.func)
                and len(call_arg.args) >= 1):
            return call_arg.args[0]
        return call_arg

    def _try_replace_stmt(self, stmt):
        if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
                and self._callee_is_exec(stmt.value.func)
                and len(stmt.value.args) in (1, 2) and not stmt.value.keywords):
            return None
        call = stmt.value
        if id(call) in self._spliced_ids:
            return None

        ok, payload = safe_eval(self._payload_expr(call.args[0]))
        if not ok or not isinstance(payload, (str, bytes)):
            return None
        if isinstance(payload, bytes):
            try:
                payload = payload.decode('utf-8')
            except UnicodeDecodeError:
                return None
        if not payload.strip():
            return None

        try:
            inner = ast.parse(payload)
        except SyntaxError:
            return None
        ast.fix_missing_locations(inner)
        if not inner.body:
            return None

        self._spliced_ids.add(id(call))
        return inner.body


class JunkStatementCleaner(ast.NodeTransformer):
    """Remove expression statements that have no side effects."""

    def _clean(self, stmts: list) -> list:
        result = []
        for stmt in stmts:
            if (isinstance(stmt, ast.Expr)
                    and not isinstance(stmt.value, (ast.Yield, ast.YieldFrom, ast.Await))
                    and _is_pure_expr(stmt.value)
                    and not isinstance(stmt.value, ast.Constant)):
                continue
            result.append(stmt)
        return result

    def visit_Module(self, node: ast.Module):
        self.generic_visit(node)
        node.body = self._clean(node.body)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.generic_visit(node)
        node.body = self._clean(node.body)
        # Keep at least a pass if body becomes empty
        if not node.body:
            node.body = [ast.Pass()]
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_If(self, node: ast.If):
        self.generic_visit(node)
        node.body = self._clean(node.body) or [ast.Pass()]
        if node.orelse:
            node.orelse = self._clean(node.orelse)
        return node

    def visit_For(self, node: ast.For):
        self.generic_visit(node)
        node.body = self._clean(node.body) or [ast.Pass()]
        return node

    def visit_While(self, node: ast.While):
        self.generic_visit(node)
        node.body = self._clean(node.body) or [ast.Pass()]
        return node


class ImportAliasNormalizer(ast.NodeTransformer):
    """Drop aliases on imports of a known-safe module set, renaming uses.
    The allowlist keeps third-party/user modules from being touched."""

    _KNOWN_SAFE = frozenset({
        'base64', 'hashlib', 'zlib', 'bz2', 'lzma', 'codecs', 'binascii',
        'struct', 'csv', 'json', 'os', 'sys', 'io', 're', 'math',
        'random', 'string', 'itertools', 'functools', 'collections',
        'pathlib', 'datetime', 'time', 'copy', 'gc',
    })

    def __init__(self):
        self._alias_map= {}   # alias_name → real_name

    def visit_Module(self, node: ast.Module):
        self._collect_aliases(node)
        self.generic_visit(node)
        node.body = self._rewrite_imports(node.body)
        return node

    def _collect_aliases(self, node: ast.Module):
        for stmt in node.body:
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    if (alias.asname
                            and alias.name in self._KNOWN_SAFE):
                        self._alias_map[alias.asname] = alias.name

            elif isinstance(stmt, ast.ImportFrom):
                if stmt.module in self._KNOWN_SAFE:
                    for alias in stmt.names:
                        if alias.asname:
                            self._alias_map[alias.asname] = alias.name

    def _rewrite_imports(self, stmts: list) -> list:
        result = []
        for stmt in stmts:
            if isinstance(stmt, ast.Import):
                new_names = []
                for alias in stmt.names:
                    if alias.asname and alias.name in self._KNOWN_SAFE:
                        new_names.append(ast.alias(name=alias.name, asname=None))
                    else:
                        new_names.append(alias)
                stmt.names = new_names
            elif isinstance(stmt, ast.ImportFrom):
                if stmt.module in self._KNOWN_SAFE:
                    new_names = []
                    for alias in stmt.names:
                        if alias.asname:
                            new_names.append(ast.alias(name=alias.name, asname=None))
                        else:
                            new_names.append(alias)
                    stmt.names = new_names
            result.append(stmt)
        return result

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Load) and node.id in self._alias_map:
            return ast.copy_location(
                ast.Name(id=self._alias_map[node.id], ctx=ast.Load()), node)
        return node

    def visit_Attribute(self, node: ast.Attribute):
        self.generic_visit(node)
        if (isinstance(node.value, ast.Name)
                and node.value.id in self._alias_map):
            new_val = ast.Name(id=self._alias_map[node.value.id], ctx=ast.Load())
            ast.copy_location(new_val, node.value)
            node.value = new_val
        return node
