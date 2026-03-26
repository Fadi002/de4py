# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
engines/proxy_cleaner.py

Resolves proxy / alias obfuscation patterns:

  1. Tuple-unpack aliases (BlankOBF / cff.py style):
       a, b, c = (int, bytes, 193)
     → builds value map and inlines all uses

  2. Simple name aliases:
       muwener = __import__  →  replace muwener with __import__

  3. Constant proxy-call folding:
       int.from_bytes(bytes([x ^ 193 for x in b'\xa0']), 'big')  →  int

  4. Builtins injection stripping:
       __import__('builtins').x = ...  →  removed

  5. Unicode confusable normalization:
       Cyrillic/Greek lookalikes → ASCII equivalents
"""

import ast
import copy
import re
import io
import tokenize
from typing import Any, Dict, List, Optional, Set, Tuple


# ─── Confusable unicode → ASCII map ──────────────────────────────────────────

_CONFUSABLES: Dict[str, str] = {
    'А':'A','В':'B','С':'C','Е':'E','Н':'H','І':'I','К':'K','М':'M',
    'О':'O','Р':'P','Ѕ':'S','Т':'T','Х':'X','Ү':'Y',
    'а':'a','с':'c','е':'e','і':'i','ј':'j','о':'o','р':'p',
    'ѕ':'s','х':'x','у':'y',
    'Α':'A','Β':'B','Ε':'E','Ζ':'Z','Η':'H','Ι':'I','Κ':'K',
    'Μ':'M','Ν':'N','Ο':'O','Ρ':'P','Τ':'T','Υ':'Y','Χ':'X',
    'ο':'o','ν':'v','α':'a',
}

_SAFE_ENV: Dict[str, Any] = {
    'int':int,'bytes':bytes,'str':str,'float':float,'bool':bool,
    'list':list,'dict':dict,'set':set,'tuple':tuple,
    'len':len,'range':range,'chr':chr,'ord':ord,'abs':abs,
    'sum':sum,'min':min,'max':max,'round':round,
    'True':True,'False':False,'None':None,
    '__import__':__import__,'eval':eval,
}


def _try_eval(node: ast.expr, env: Dict[str, Any]) -> Tuple[bool, Any]:
    try:
        merged = {**_SAFE_ENV, **env}
        code = compile(ast.Expression(body=copy.deepcopy(node)), '<proxy>', 'eval')
        return True, eval(code, {'__builtins__': _SAFE_ENV}, merged)
    except Exception:
        return False, None


def _val_to_ast(val: Any) -> Optional[ast.expr]:
    """Return an AST node for the value, or None if not safely expressible."""
    # Only inline primitive constants — never inline callables/types as Name nodes.
    # Inlining e.g. 'int' as a Name causes SyntaxWarnings when the proxy_cleaner's
    # eval engine tries int([...]) and hits the actual int type.
    if isinstance(val, (bool,)):
        return ast.Constant(value=val)
    if isinstance(val, int) and not isinstance(val, bool):
        return ast.Constant(value=val)
    if isinstance(val, (float, str, bytes, type(None))):
        return ast.Constant(value=val)
    # Don't inline callables, types, or modules — leave them as-is
    return None


class ProxyCleaner:

    def deobfuscate(self, source: str) -> str:
        source = self._normalize_unicode(source)
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        for _ in range(8):
            before = ast.unparse(tree)
            env = self._collect_env(tree)
            if env:
                tree = self._inline(tree, env)
                tree = self._remove_assignments(tree, set(env.keys()))
            tree = self._strip_builtins(tree)
            tree = self._fold_calls(tree, env)
            ast.fix_missing_locations(tree)
            try:
                if ast.unparse(tree) == before:
                    break
            except Exception:
                break

        try:
            return ast.unparse(tree)
        except Exception:
            return source

    # ── Unicode normalization ─────────────────────────────────────────────────

    def _normalize_unicode(self, source: str) -> str:
        if not any(c in _CONFUSABLES for c in source):
            return source
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
        except tokenize.TokenError:
            return re.sub(r'\b\w+\b', lambda m: ''.join(_CONFUSABLES.get(c, c) for c in m.group()), source)

        rename: Dict[str, str] = {}
        existing = {t.string for t in tokens if t.type == tokenize.NAME}
        for tok in tokens:
            if tok.type == tokenize.NAME and any(c in _CONFUSABLES for c in tok.string):
                old = tok.string
                if old not in rename:
                    new = ''.join(_CONFUSABLES.get(c, c) for c in old)
                    i = 0
                    cand = new
                    while cand in existing and cand != old:
                        i += 1
                        cand = f"{new}_u{i}"
                    rename[old] = cand

        if not rename:
            return source

        lines = source.splitlines(keepends=True)
        out, prev = [], (1, 0)
        for tok in tokens:
            sr, sc = tok.start
            er, ec = tok.end
            pr, pc = prev
            # fill gap
            if sr == pr:
                out.append(lines[sr-1][pc:sc] if sr <= len(lines) else '')
            else:
                if pr <= len(lines): out.append(lines[pr-1][pc:])
                for r in range(pr, sr-1):
                    if r < len(lines): out.append(lines[r])
                if sr <= len(lines): out.append(lines[sr-1][:sc])
            out.append(rename.get(tok.string, tok.string) if tok.type == tokenize.NAME else tok.string)
            prev = (er, ec)
        return ''.join(out)

    # ── Collect proxy environment ─────────────────────────────────────────────

    def _collect_env(self, tree: ast.Module) -> Dict[str, Any]:
        env: Dict[str, Any] = {}
        for stmt in tree.body:
            if not isinstance(stmt, ast.Assign):
                continue
            if len(stmt.targets) != 1:
                continue
            t = stmt.targets[0]

            # Simple: name = expr
            if isinstance(t, ast.Name):
                ok, val = _try_eval(stmt.value, env)
                if ok and self._worthy(val):
                    env[t.id] = val

            # Tuple unpack: a, b, c = (e1, e2, e3)
            elif isinstance(t, ast.Tuple) and isinstance(stmt.value, (ast.Tuple, ast.List)):
                names = [e.id for e in t.elts if isinstance(e, ast.Name)]
                vals  = stmt.value.elts
                if len(names) == len(vals) == len(t.elts):
                    for name, vnode in zip(names, vals):
                        ok, val = _try_eval(vnode, env)
                        if ok and self._worthy(val):
                            env[name] = val
        return env

    def _worthy(self, val: Any) -> bool:
        return val is not None and isinstance(val, (int, float, bool, str, bytes, type)) or callable(val)

    # ── Inline proxy values ───────────────────────────────────────────────────

    def _inline(self, tree: ast.Module, env: Dict[str, Any]) -> ast.Module:
        ast_map = {n: _val_to_ast(v) for n, v in env.items()}
        ast_map = {n: node for n, node in ast_map.items() if node is not None}
        if not ast_map:
            return tree

        class Inliner(ast.NodeTransformer):
            def visit_Name(self, node):
                if isinstance(node.ctx, ast.Load) and node.id in ast_map:
                    return copy.deepcopy(ast_map[node.id])
                return node

        return Inliner().visit(tree)

    # ── Remove proxy assignments ──────────────────────────────────────────────

    def _remove_assignments(self, tree: ast.Module, names: Set[str]) -> ast.Module:
        new_body = []
        for stmt in tree.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                t = stmt.targets[0]
                if isinstance(t, ast.Name) and t.id in names:
                    continue
                if (isinstance(t, ast.Tuple)
                        and all(isinstance(e, ast.Name) and e.id in names for e in t.elts)):
                    continue
            new_body.append(stmt)
        tree.body = new_body
        return tree

    # ── Strip builtins injections ─────────────────────────────────────────────

    def _strip_builtins(self, tree: ast.Module) -> ast.Module:
        def _is_builtins_call(node):
            return (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == '__import__'
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == 'builtins')

        class Stripper(ast.NodeTransformer):
            def visit_Assign(self, node):
                self.generic_visit(node)
                for t in node.targets:
                    if isinstance(t, ast.Attribute) and _is_builtins_call(t.value):
                        return None
                    if isinstance(t, ast.Tuple) and all(
                        isinstance(e, ast.Attribute) and _is_builtins_call(e.value)
                        for e in t.elts
                    ):
                        return None
                return node

        return Stripper().visit(tree)

    # ── Fold constant proxy calls ─────────────────────────────────────────────

    def _fold_calls(self, tree: ast.Module, env: Dict[str, Any]) -> ast.Module:
        class Folder(ast.NodeTransformer):
            def visit_Call(self, node):
                self.generic_visit(node)
                ok, result = _try_eval(node, env)
                if ok and isinstance(result, (int, float, bool, str, bytes)):
                    return ast.Constant(value=result)
                return node

        return Folder().visit(tree)
