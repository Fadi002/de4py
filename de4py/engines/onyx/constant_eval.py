# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).

"""
Pre-lift AST constant folding + deobfuscation passes.

Handles:
  - b64decode / b85decode call chains (direct-import and module style)
  - chr(ord(i) - N) join comprehensions
  - int.__xor__ XOR decode patterns (style-2 obfuscation)
  - True+True+True arithmetic, len("literal"), int("N") etc.
  - globals()['__builtins__'] access → direct Name
  - builtins-dict subscript calls: d['any'](...) → any(...)
  - getattr(obj, 'attr') → obj.attr chain flattening
  - Pure XOR wrapper function inlining at call sites
  - Module-level constant variable propagation
  - Dead unused constant assignment elimination
"""

import ast
import re
from base64 import b64decode, b85decode

import base64 as _b64mod, zlib as _zlibmod, bz2 as _bz2mod, lzma as _lzmamod
import builtins as _builtins_mod

_SAFE_MODS = {
    'base64': _b64mod, 'zlib': _zlibmod, 'bz2': _bz2mod,
    'lzma': _lzmamod, 'builtins': _builtins_mod,
}

def _safe_import(name, *args, **kwargs):
    if name in _SAFE_MODS:
        return _SAFE_MODS[name]
    raise ImportError(f"Module '{name}' not allowed in safe eval")

_SAFE_BUILTINS_DICT = {'__import__': _safe_import}
for _pyside_key in ('__orig_import__', '__feature_import__', 'qApp'):
    if hasattr(_builtins_mod, _pyside_key):
        _SAFE_BUILTINS_DICT[_pyside_key] = getattr(_builtins_mod, _pyside_key)

_SAFE_ENV= {
    'b64decode': b64decode,
    'b85decode': b85decode,
    'chr': chr, 'ord': ord, 'len': len, 'int': int,
    'str': str, 'bytes': bytes, 'list': list, 'range': range,
    'True': True, 'False': False, 'None': None,
    '__import__': _safe_import,
    '__builtins__': _SAFE_BUILTINS_DICT,
}


def _safe_eval(node: ast.AST):
    """Evaluate a node as a constant. Returns (ok, value)."""
    try:
        val = eval(compile(ast.Expression(body=node), '<fold>', 'eval'), _SAFE_ENV)
        if isinstance(val, (int, float, str, bytes, bool, type(None))):
            return True, val
    except Exception:
        pass
    return False, None


class ConstantExprFolder(ast.NodeTransformer):
    """
    Bottom-up constant folder.
    Folds any expression whose value is statically determinable using the
    safe environment (b64/b85 decode, chr/ord arithmetic, XOR, int, len…).
    Also restructures getattr(obj, 'attr') → obj.attr for readability.
    """

    def _fold(self, node: ast.AST) -> ast.AST:
        ok, val = _safe_eval(node)
        if ok:
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
            # Try to constant-fold the attribute access
            ok, val = _safe_eval(attr_node)
            if ok:
                return ast.copy_location(ast.Constant(value=val), node)
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
    """
    Resolves builtins-dict subscript pattern used in style-2 obfuscation.
    Pattern:
        x = __builtins__  (or via isinstance+__dict__ guard)
        y['any'](...) → any(...)
    """

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
    """
    Propagates module-level constant variable assignments.
    Pattern:
        x = 'some_constant'      ← assignment from a Constant
        func(x + y)              → func('some_constant' + y)

    Used primarily for test_obf.py style: 4 variables holding b64 slices
    are inlined at their use site so string concatenation can be further folded.
    """

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


class DeadAssignmentEliminator(ast.NodeTransformer):
    """
    Removes unused constant-value assignments in function/method bodies.
    Pattern:
        def f(x):
            _unused = 746    ← assigned but never read → remove
            ...

    Only removes assignments where:
    - RHS is a Constant (no side effects)
    - The target Name is never read in the same function body
    """

    def _eliminate(self, stmts: list) -> list:
        # Collect all Name-load uses in these statements
        used: set = set()
        for stmt in stmts:
            for n in ast.walk(stmt):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                    used.add(n.id)

        result = []
        for stmt in stmts:
            # Remove simple constant assignments to unused variables
            if (isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and isinstance(stmt.value, ast.Constant)
                    and stmt.targets[0].id not in used):
                continue  # drop
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
    """
    Detects simple pure functions (XOR decoders, join-chr, etc.) and inlines
    their call sites when arguments are all literals.

    Patterns recognized:
      def _xor_XXX(lst):
          return bytes([c ^ KEY for c in lst]).decode(ENC)

      def _join_XXX(lst):
          return ''.join(chr(c) for c in lst)

    At call sites with a literal list arg, evaluates and replaces with string.
    """

    def __init__(self):
        # func_name → (key, encoding) for XOR decoders
        self._xor_funcs= {}
        # func_name → encoding for join-chr decoders
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
            # Pattern: bytes([c ^ KEY for c in lst]).decode(ENC)
            xor_info = self._extract_xor_pattern(ret, stmt)
            if xor_info:
                self._xor_funcs[name] = xor_info

    def _extract_xor_pattern(self, expr, func_def):
        """
        Match: bytes([VAR ^ KEY for VAR in PARAM]).decode(ENC)
        or:    getattr(bytes([VAR ^ KEY for VAR in PARAM]), 'decode')(ENC)
        Returns (key, encoding) or None.
        """
        # Normalize getattr(..., 'decode')(enc) → ....decode(enc)
        if (isinstance(expr, ast.Call)
                and isinstance(expr.func, ast.Attribute)
                and expr.func.attr == 'decode'):
            inner = expr.func.value
            enc = expr.args[0].value if expr.args and isinstance(expr.args[0], ast.Constant) else 'utf-8'
        else:
            return None

        # inner must be bytes([...])
        if not (isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Name)
                and inner.func.id == 'bytes'
                and len(inner.args) == 1):
            return None

        comp = inner.args[0]
        if not isinstance(comp, ast.ListComp):
            return None

        # Listcomp: c ^ KEY for c in PARAM
        if len(comp.generators) != 1:
            return None
        gen = comp.generators[0]
        if not (isinstance(gen.target, ast.Name)
                and isinstance(gen.iter, ast.Name)):
            return None

        loop_var = gen.target.id
        param_var = gen.iter.id

        # Check param_var is the function's first parameter
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
            # Must be a literal list of integers
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



class DeadFunctionEliminator(ast.NodeTransformer):
    """
    Removes module-level function definitions that are never called.
    A function is dead if its name never appears as a Load Name in the module,
    i.e. it's defined but never used anywhere (not passed, not called).
    """

    def visit_Module(self, node: ast.Module):
        # Collect all defined function names at module level
        defined = {
            stmt.name
            for stmt in node.body
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if not defined:
            return node

        # Collect all Load uses of Names anywhere in the tree
        # Skip the function def's own name (in its def statement)
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
    """
    Converts eval(b'identifier') or X.eval(b'identifier') → Name('identifier').

    Pattern used in test_obf.py to dynamically access builtins:
        eval(b'exec')      → exec
        eval(b'getattr')   → getattr
        eval(b'__import__') → __import__
        builtins.eval(b'decompress') → decompress  (when chained with getattr)
    """
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
        # eval(b'name')
        if isinstance(node.func, ast.Name) and node.func.id == 'eval':
            return self._try_unwrap(node)
        # X.eval(b'name')
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'eval':
            return self._try_unwrap(node)
        return node


class EvalExecUnwrapper(ast.NodeTransformer):
    """
    Handles the pattern: eval(b'exec')(payload) → exec(payload)
    and:                  eval('exec')(payload) → exec(payload)
    Common in test_obf.py style payloads.
    """

    def visit_Call(self, node: ast.Call):
        self.generic_visit(node)
        # Match: Call(Call(eval, [b'exec'|'exec']), [payload])
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
    """Remove module-level class definitions that are never referenced."""

    def visit_Module(self, node: ast.Module):
        defined = {s.name for s in node.body if isinstance(s, ast.ClassDef)}
        if not defined:
            return node
        used: set = set()
        for stmt in node.body:
            for n in ast.walk(stmt):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if n is not stmt:  # skip the def name itself at top level
                        pass
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
    Evaluates for-loops where all referenced data is constant and the body
    calls exec() with a computed payload.  Universal pattern:

        for key in range(1, N):
            if list[i] ^ key == list[j]:
                exec(decompress(bytes(x ^ key for x in list[...])))
                break

    After fold_constants has resolved `list` to a Python list, this loop
    can be fully evaluated. We run it in a sandbox with exec() captured,
    decode the payload, and replace the for-loop with the decoded statements.
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
        # Must iterate over range(...)
        if not (isinstance(node.iter, ast.Call)
                and isinstance(node.iter.func, ast.Name)
                and node.iter.func.id == 'range'):
            return None
        # Bounds must be constants
        args = node.iter.args
        try:
            bounds = [eval(compile(ast.Expression(a), '<b>', 'eval'), _SAFE_ENV)
                      for a in args]
        except Exception:
            return None
        rng = range(*bounds)
        if len(rng) > 100_000:  # sanity guard
            return None

        # Safety check: only block real I/O / system ops.
        # exec/eval are OK here — we replace them with a capture function.
        _LOOP_DANGER = frozenset({'open', 'system', 'popen', 'connect',
                                   'send', 'write', 'unlink', 'remove'})
        for n in ast.walk(node):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                if n.func.id in _LOOP_DANGER:
                    return None

        # Build sandbox: safe builtins + safe modules + known constants
        sandbox = dict(_SAFE_BUILTINS_EXEC)
        sandbox.update(_FULL_SAFE_MODS)
        sandbox.update(self._const_map)

        captured = []

        def _capture(code, *a, **kw):
            captured.append(code)

        builtins = dict(sandbox['__builtins__'])
        builtins['exec'] = _capture
        sandbox['__builtins__'] = builtins
        sandbox['exec'] = _capture  # in case exec is used directly

        try:
            code_str = ast.unparse(node)
            exec(compile(ast.parse(code_str), '<for_eval>', 'exec'), sandbox)
        except Exception:
            return None

        if not captured:
            return None

        payload = captured[0]
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

def _run_fold(tree: ast.AST, passes: int = 8) -> ast.AST:
    for _ in range(passes):
        new = ConstantExprFolder().visit(tree)
        ast.fix_missing_locations(new)
        if ast.dump(new) == ast.dump(tree):
            break
        tree = new
    return tree


def fold_constants(source: str) -> str:
    """
    Full pre-lift deobfuscation pipeline on Python source text.

    Pass order:
    1. Fold constants (chr/ord, arithmetic, b64/b85, slice, XOR)
    2. globals()['key'] → Name('key')
    3. Fold again
    4. Unwrap builtins-dict subscripts
    5. Module-level constant propagation (for test_obf.py style)
    6. Final fold (catches newly-constant expressions after propagation)
    7. Pure function inlining (XOR decoders at call sites)
    8. Dead constant assignment elimination
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    try:
        ast.fix_missing_locations(tree)

        # Pass 0: eval(b'name') → Name('name') — must be FIRST so subsequent
        # folds can see getattr/exec/etc. as plain names
        tree = EvalNameUnwrapper().visit(tree)
        ast.fix_missing_locations(tree)

        # Pass 1: fold constants so lambda args become string literals
        tree = _run_fold(tree, 8)

        # Pass 2: resolve globals()['key'] → Name('key')
        tree = GlobalsBuiltinResolver().visit(tree)
        ast.fix_missing_locations(tree)

        # Pass 2b: re-run EvalNameUnwrapper after first fold (some eval(b'x') may
        # only be visible after the first fold unlocks them)
        tree = EvalNameUnwrapper().visit(tree)
        ast.fix_missing_locations(tree)

        # Pass 3: fold again (may unlock more after globals resolution)
        tree = _run_fold(tree, 4)

        # Pass 4: unwrap builtins-dict subscript calls
        tree = BuiltinsDictUnwrapper().visit(tree)
        ast.fix_missing_locations(tree)

        # Pass 5: propagate module-level constants (for multi-variable b64 patterns)
        tree = ASTConstantPropagator().visit(tree)
        ast.fix_missing_locations(tree)

        # Pass 6: final fold (string concat of propagated constants, etc.)
        tree = _run_fold(tree, 4)

        # Pass 7: inline pure XOR/decode functions at call sites
        tree = PureFunctionInliner().visit(tree)
        ast.fix_missing_locations(tree)
        tree = _run_fold(tree, 2)

        # Pass 8: remove dead constant assignments in functions
        tree = DeadAssignmentEliminator().visit(tree)
        ast.fix_missing_locations(tree)

        # Pass 9: remove functions/classes never referenced
        tree = DeadFunctionEliminator().visit(tree)
        ast.fix_missing_locations(tree)
        tree = DeadClassEliminator().visit(tree)

        # Pass 10: eval(b'exec')(payload) → exec(payload)
        tree = EvalExecUnwrapper().visit(tree)
        ast.fix_missing_locations(tree)
        tree = _run_fold(tree, 2)

        # Pass 11: evaluate any remaining pure functions with constant args
        tree = PureFunctionEvaluator().visit(tree)
        ast.fix_missing_locations(tree)
        tree = _run_fold(tree, 2)
        # Re-eliminate dead functions exposed by inlining
        tree = DeadFunctionEliminator().visit(tree)
        ast.fix_missing_locations(tree)

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
        ast.fix_missing_locations(tree)
        tree = _run_fold(tree, 2)
        tree = DeadFunctionEliminator().visit(tree)
        tree = DeadClassEliminator().visit(tree)
        ast.fix_missing_locations(tree)

        # Pass 12: remove junk no-op expression statements
        tree = JunkStatementCleaner().visit(tree)
        ast.fix_missing_locations(tree)

        # Pass 13: normalize import aliases for known-safe modules
        tree = ImportAliasNormalizer().visit(tree)
        ast.fix_missing_locations(tree)
        ast.fix_missing_locations(tree)

        return ast.unparse(tree)
    except Exception:
        return source


import hashlib as _hashlib_mod
import binascii as _binascii_mod
import struct as _struct_mod
import codecs as _codecs_mod

_FULL_SAFE_MODS = {
    **_SAFE_MODS,
    'hashlib': _hashlib_mod,
    'binascii': _binascii_mod,
    'struct': _struct_mod,
    'codecs': _codecs_mod,
}

_SAFE_BUILTINS_EXEC_DICT = {
    '__import__': _safe_import,
    'len': len, 'range': range, 'enumerate': enumerate,
    'zip': zip, 'map': map, 'filter': filter, 'reversed': reversed,
    'bytes': bytes, 'bytearray': bytearray, 'chr': chr, 'ord': ord,
    'str': str, 'int': int, 'float': float, 'bool': bool,
    'list': list, 'tuple': tuple, 'dict': dict, 'set': set,
    'abs': abs, 'min': min, 'max': max, 'sum': sum, 'any': any, 'all': all,
    'isinstance': isinstance, 'issubclass': issubclass,
    'repr': repr, 'hex': hex, 'oct': oct, 'bin': bin,
    'Exception': Exception, 'ValueError': ValueError,
    'TypeError': TypeError, 'print': print,
}
for _pyside_key in ('__orig_import__', '__feature_import__', 'qApp'):
    if hasattr(_builtins_mod, _pyside_key):
        _SAFE_BUILTINS_EXEC_DICT[_pyside_key] = getattr(_builtins_mod, _pyside_key)

_SAFE_BUILTINS_EXEC = {
    '__builtins__': _SAFE_BUILTINS_EXEC_DICT
}

_DANGEROUS_ATTRS = frozenset({
    'open', 'exec', 'eval', 'compile', 'system', 'popen',
    'subprocess', 'socket', 'connect', 'send', 'recv',
    'write', 'unlink', 'remove', 'rmdir', 'makedirs',
})


def _is_safe_for_execution(funcdef: ast.FunctionDef) -> bool:
    """Return True if the function only does computation — no I/O or shell."""
    for node in ast.walk(funcdef):
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            return False
        if isinstance(node, ast.Call):
            fname = ''
            if isinstance(node.func, ast.Name):
                fname = node.func.id
            elif isinstance(node.func, ast.Attribute):
                fname = node.func.attr
            if fname in _DANGEROUS_ATTRS:
                return False
    return True


class PureFunctionEvaluator(ast.NodeTransformer):
    """
    Evaluates pure module-level functions at call sites when all arguments are
    constants. Handles any custom string-decryption, encoding-wrapping, or
    arithmetic helper regardless of implementation.

    The function is compiled and executed in a restricted sandbox that includes
    base64, hashlib, binascii, struct, codecs — enough for common obfuscation
    decode helpers.
    """

    def __init__(self):
        self._funcs= {}   # name → callable

    def visit_Module(self, node: ast.Module):
        self._collect(node)
        self.generic_visit(node)
        return node

    def _collect(self, module: ast.Module):
        sandbox = dict(_SAFE_BUILTINS_EXEC)
        sandbox.update(_FULL_SAFE_MODS)

        for stmt in module.body:
            if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not _is_safe_for_execution(stmt):
                continue

            try:
                mod_node = ast.Module(body=[stmt], type_ignores=[])
                ast.fix_missing_locations(mod_node)
                code = compile(mod_node, '<pure_eval>', 'exec')
                ns = dict(sandbox)
                exec(code, ns)
                fn = ns.get(stmt.name)
                if callable(fn):
                    self._funcs[stmt.name] = fn
            except Exception:
                pass

    def visit_Call(self, node: ast.Call):
        self.generic_visit(node)

        if not (isinstance(node.func, ast.Name)
                and node.func.id in self._funcs
                and not node.keywords):
            return node

        # All positional args must be constants
        args = []
        for a in node.args:
            if isinstance(a, ast.Constant):
                args.append(a.value)
            else:
                return node

        try:
            result = self._funcs[node.func.id](*args)
            if isinstance(result, (str, int, float, bytes, bool, type(None))):
                return ast.copy_location(ast.Constant(value=result), node)
        except Exception:
            pass

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
        # Pure builtins with no side effects
        func_name = ''
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif (isinstance(node.func, ast.Attribute)
              and isinstance(node.func.value, ast.Constant)):
            func_name = node.func.attr  # e.g. ''.join(...)
        if func_name in _PURE_BUILTINS:
            return all(_is_pure_expr(a) for a in node.args)
    return False


class JunkStatementCleaner(ast.NodeTransformer):
    """
    Removes expression statements that have no side effects:
      - Standalone arithmetic:  27 - 73
      - Pure builtin calls:     len([]), dict(), sorted([])
      - Constant expressions:   'dead string', 42
      - Already-constant names
    """

    def _clean(self, stmts: list) -> list:
        result = []
        for stmt in stmts:
            if (isinstance(stmt, ast.Expr)
                    and not isinstance(stmt.value, (ast.Yield, ast.YieldFrom, ast.Await))
                    and _is_pure_expr(stmt.value)
                    and not isinstance(stmt.value, ast.Constant)):
                continue  # drop it
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
    """
    Simplifies import aliases for standard/safe modules:
      import csv as HTza9v1Dldu  → import csv  (and renames uses)
      from base64 import b64decode as _x → from base64 import b64decode

    Only normalizes aliases for modules in a known-safe set so we don't
    accidentally rename third-party or user modules.
    """

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
