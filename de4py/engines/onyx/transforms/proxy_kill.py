# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.


import ast
import copy as _copy

from de4py.engines.onyx.framework.governor import statement_lists
from de4py.engines.onyx.framework.rules import Match, Patch, Rule


def _pure(node):
    from de4py.engines.onyx.constant_eval import _is_pure_expr
    return _is_pure_expr(node)


class _Collector(ast.NodeVisitor):

    def __init__(self):
        self.defs: dict = {}
        self.counts: dict = {}
        self.rebound: set = set()
        self.value_uses: set = set()

    def visit_FunctionDef(self, node):
        self.counts[node.name] = self.counts.get(node.name, 0) + 1
        self.defs.setdefault(node.name, node)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.value_uses.add(node.name)
        self.generic_visit(node)

    def visit_Assign(self, node):
        for t in node.targets:
            for n in ast.walk(t):
                if isinstance(n, ast.Name):
                    self.rebound.add(n.id)
        self.generic_visit(node)

    def visit_Call(self, node):
        f = node.func
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
            self.value_uses.add(f.value.id)
        self.generic_visit(node)

    def visit_Return(self, node):
        if isinstance(node.value, ast.Name):
            self.value_uses.add(node.value.id)
        self.generic_visit(node)


class ForwardingProxyInlineRule(Rule):
    """Inline calls through pure forwarding wrappers::

        def f(a, b): return g(a, b)     ->     f(x, y) becomes g(x, y)

    Only exact positional mirroring qualifies: one wrapper parameter per
    call argument, same order, keywords never pass. Module-level defs only;
    shadowing inside inner scopes keeps those calls untouched."""

    name = "forwarding_proxies"
    safety = "probably_safe"
    event_category = "INLINE"

    def _forwarder_shape(self, fn):
        spec = fn.args
        if fn.decorator_list or len(fn.body) != 1 or not isinstance(fn.body[0], ast.Return):
            return None
        ret = fn.body[0].value
        if not isinstance(ret, ast.Call):
            return None

        # Pattern 1: star-args pass-through def f(*a, **kw) -> g(*a, **kw)
        params = [a.arg for a in spec.args]
        if spec.vararg and not params and not spec.kwonlyargs:
            has_star = any(isinstance(a, ast.Starred) for a in ret.args)
            has_dstar = any(
                isinstance(k, ast.keyword) and k.arg is None
                for k in (ret.keywords or []))
            if has_star and has_dstar:
                return self._callee_shape(ret.func, 0)

        # Pattern 2: exact positional mirroring def f(a,b) -> g(a,b)
        if spec.vararg or spec.kwarg or spec.kwonlyargs or spec.posonlyargs or spec.defaults or not params:
            return None
        if ret.keywords or len(ret.args) != len(params):
            return None
        for a, p in zip(ret.args, params):
            if not (isinstance(a, ast.Name) and a.id == p
                    and isinstance(a.ctx, ast.Load)):
                return None
        return self._callee_shape(ret.func, len(params))

    @staticmethod
    def _callee_shape(callee, nparams):
        if isinstance(callee, ast.Name):
            return {"kind": "name", "id": callee.id,
                    "nparams": nparams}
        if isinstance(callee, ast.Attribute) and isinstance(callee.value, ast.Name):
            return {"kind": "attr", "value": callee.value.id,
                    "attr": callee.attr, "nparams": nparams}
        return None

    def _collect(self, tree):
        collector = _Collector()
        collector.visit(tree)
        out = []
        for name, fn in collector.defs.items():
            if collector.counts.get(name, 0) != 1:
                continue
            if name in collector.rebound or name in collector.value_uses:
                continue
            shape = self._forwarder_shape(fn)
            if shape is not None:
                out.append((name, shape))
        return out

    def applies(self, ctx):
        forwarders = self._collect(ctx.tree)
        if not forwarders:
            return
        index = {name: shape for name, shape in forwarders}
        for stmts in statement_lists(ctx.tree):
            for stmt in stmts:
                hits = []
                for n in ast.walk(stmt):
                    if isinstance(n, ast.Call) \
                            and isinstance(n.func, ast.Name) \
                            and n.func.id in index \
                            and not n.keywords \
                            and len(n.args) == index[
                                n.func.id]["nparams"]:
                        hits.append(n)
                if hits:
                    shapes = {h.func.id: index[h.func.id] for h in hits}
                    yield Match(node=stmt,
                                data={"hits": len(hits),
                                      "shapes": shapes})

    def transform(self, ctx, match):
        shapes = match.data["shapes"]

        class _Swap(ast.NodeTransformer):
            replaced = 0

            def visit_Call(self, node):
                self.generic_visit(node)
                if not isinstance(node.func, ast.Name):
                    return node
                shape = shapes.get(node.func.id)
                if shape is None or node.keywords \
                        or len(node.args) != shape["nparams"]:
                    return node
                if shape["kind"] == "name":
                    new_func = ast.Name(id=shape["id"], ctx=ast.Load())
                else:
                    new_func = ast.Attribute(
                        value=ast.Name(id=shape["value"], ctx=ast.Load()),
                        attr=shape["attr"], ctx=ast.Load())
                node.func = ast.copy_location(new_func, node.func)
                self.replaced += 1
                return node

        swapper = _Swap()
        new = swapper.visit(_copy.deepcopy(match.node))
        if not swapper.replaced:
            return None
        ast.fix_missing_locations(new)
        ctx.count("proxies_inlined", swapper.replaced)
        return Patch(target=match.node, replacement=new,
                     detail=f"inlined {swapper.replaced} proxied call(s)")


class DeadStoreRule(Rule):

    name = "dead_stores"
    safety = "safe"
    event_category = "DEAD-CODE"

    def applies(self, ctx):
        for stmts in statement_lists(ctx.tree):
            loads: dict = {}
            for other in stmts:
                for n in ast.walk(other):
                    if isinstance(n, ast.Name) \
                            and isinstance(n.ctx, ast.Load):
                        loads[n.id] = loads.get(n.id, 0) + 1
            for stmt in stmts:
                if not (isinstance(stmt, ast.Assign)
                        and len(stmt.targets) == 1
                        and isinstance(stmt.targets[0], ast.Name)):
                    continue
                name = stmt.targets[0].id
                if loads.get(name):
                    continue
                if not _pure(stmt.value):
                    continue
                yield Match(node=stmt)

    def transform(self, ctx, match):
        ctx.count("dead_stores_removed")
        return Patch(target=match.node, replacement=None,
                     detail="removed dead store")


def default_proxy_rules():
    return [ForwardingProxyInlineRule(), DeadStoreRule()]
