# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""Inline identity and constant-returning wrapper functions at module
scope. Only single module-level definitions with no decorators, defaults,
rebinds or value-uses qualify; shadowing inside function bodies is not
tracked, so those calls stay untouched."""

import ast
import copy as _copy

from de4py.engines.onyx.framework.governor import statement_lists
from de4py.engines.onyx.framework.rules import Match, Patch, Rule

_SCOPED = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def _collect(tree: ast.Module):
    defs: dict = {}
    def_counts: dict = {}
    rebound: set = set()
    value_uses: set = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            def_counts[node.name] = def_counts.get(node.name, 0) + 1
            defs.setdefault(node.name, node)
        elif isinstance(node, ast.ClassDef):
            value_uses.add(node.name)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                for n in ast.walk(target):
                    if isinstance(n, ast.Name):
                        rebound.add(n.id)
        elif isinstance(node, (ast.For, ast.AsyncFor)) or isinstance(node, ast.With):
            for n in ast.walk(node):
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                    rebound.add(n.id)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                value_uses.add(node.func.value.id)
        elif isinstance(node, ast.Return) and isinstance(node.value, ast.Name):
            value_uses.add(node.value.id)

    eligible = {}
    for name, fn in defs.items():
        if def_counts.get(name, 0) != 1:
            continue
        if name in rebound or name in value_uses:
            continue
        if fn.decorator_list:
            continue
        spec = fn.args
        if spec.vararg or spec.kwarg or spec.kwonlyargs or spec.posonlyargs:
            continue
        if len(fn.body) != 1 or not isinstance(fn.body[0], ast.Return) \
                or fn.body[0].value is None:
            continue

        args = [a.arg for a in spec.args]
        ret = fn.body[0].value
        if len(args) == 1 and isinstance(ret, ast.Name) and ret.id == args[0]:
            eligible[name] = {"kind": "identity"}
        elif not args and isinstance(ret, ast.Constant):
            eligible[name] = {"kind": "const", "value": ret.value}
    return eligible


class InlineWrapperFunctionsRule(Rule):

    name = "inline_wrappers"
    safety = "probably_safe"
    event_category = "INLINE"

    def applies(self, ctx):
        eligible = _collect(ctx.tree)
        if not eligible:
            return
        names = set(eligible)
        module_stmts = ctx.tree.body
        for index, stmt in enumerate(module_stmts):
            found = any(
                isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id in names
                for n in ast.walk(stmt)
            )
            if found:
                yield Match(node=stmt, data={"eligible": eligible,
                                             "stmts": module_stmts})

    def transform(self, ctx, match):
        eligible = match.data["eligible"]
        replaced_total = 0

        class _Replacer(ast.NodeTransformer):
            replaced = 0

            def visit_Call(self, node):
                self.generic_visit(node)
                if not isinstance(node.func, ast.Name):
                    return node
                meta = eligible.get(node.func.id)
                if meta is None:
                    return node
                if meta["kind"] == "identity":
                    if len(node.args) != 1 or node.keywords:
                        return node
                    self.replaced += 1
                    return ast.copy_location(_copy.deepcopy(node.args[0]), node)
                if len(node.args) or node.keywords:
                    return node
                self.replaced += 1
                return ast.copy_location(ast.Constant(value=meta["value"]),
                                         node)

        replacer = _Replacer()
        new = replacer.visit(_copy.deepcopy(match.node))
        if not replacer.replaced:
            return None
        ast.fix_missing_locations(new)
        ctx.count("wrappers_inlined", replacer.replaced)
        return Patch(target=match.node, replacement=new,
                     detail=f"inlined {replacer.replaced} wrapper call(s)")


def default_wrapper_rules():
    return [InlineWrapperFunctionsRule(), DeadWrapperDefinitionRule()]


class DeadWrapperDefinitionRule(Rule):
    """Remove a trivial wrapper ``def`` whose name is never loaded again.

    Runs after inlining: an unreferenced one-liner definition is pure noise.
    Zero Name-loads anywhere in the tree is the gate, so any dynamic or
    attribute-based reference keeps the definition alive.
    """

    name = "dead_wrapper_definitions"
    safety = "probably_safe"
    event_category = "DEAD-CODE"

    def _is_trivial_shape(self, node) -> bool:
        if isinstance(node, ast.AsyncFunctionDef):
            return False
        if node.decorator_list:
            return False
        spec = node.args
        if spec.vararg or spec.kwarg or spec.kwonlyargs or spec.posonlyargs:
            return False
        return len(node.body) == 1 and isinstance(node.body[0], ast.Return)

    def applies(self, ctx):
        loads: set = set()
        attrs_on: set = set()
        for n in ast.walk(ctx.tree):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                loads.add(n.id)
            elif isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
                attrs_on.add(n.value.id)

        for stmt in list(ctx.tree.body):
            if not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if stmt.name in loads or stmt.name in attrs_on:
                continue
            if not self._is_trivial_shape(stmt):
                continue
            yield Match(node=stmt)

    def transform(self, ctx, match):
        ctx.count("dead_defs_removed")
        return Patch(target=match.node, replacement=None,
                     detail=f"removed unused wrapper '{match.node.name}'")
