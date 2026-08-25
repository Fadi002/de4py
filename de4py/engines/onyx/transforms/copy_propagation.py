# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""Local copy propagation for single-assignment scalar temporaries.

Obfuscators chain decoders through temp variables (``t1 = b64decode(...)``,
``t2 = t1.decode()``, ...). Within one statement list, a name assigned exactly
once from a pure expression and never rebound/mutated/deleted has its uses
replaced by the initializer; the assignment is then dropped. Mutability is
respected - lists/dicts/sets/calls are never propagated, so shared-reference
semantics survive.
"""

import ast
import copy as _copy

from de4py.engines.onyx.framework.governor import statement_lists
from de4py.engines.onyx.framework.rules import Match, Patch, Rule

_UNSAFE_INIT = (ast.List, ast.Dict, ast.Set, ast.Starred, ast.Call)
_SCOPED = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def _loads_of(stmts: list, name: str) -> int:
    return sum(
        1 for n in ast.walk(ast.Module(body=list(stmts), type_ignores=[]))
        if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load)
    )


def _scan_scope(stmts: list) -> dict:
    """name -> info dict for single-assignment candidates of this list."""
    counts: dict = {}
    written_elsewhere: set = set()
    inits: dict = {}

    def note_write(name):
        written_elsewhere.add(name)

    for stmt in stmts:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                and isinstance(stmt.targets[0], ast.Name):
            name = stmt.targets[0].id
            counts[name] = counts.get(name, 0) + 1
            if counts[name] == 1:
                inits[name] = stmt
            if isinstance(stmt.value, _UNSAFE_INIT):
                note_write(name)
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) \
                and stmt.value is not None:
            name = stmt.target.id
            counts[name] = counts.get(name, 0) + 1
            note_write(name)
        elif isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
            note_write(stmt.target.id)
        elif isinstance(stmt, (ast.For, ast.AsyncFor)):
            if isinstance(stmt.target, ast.Name):
                note_write(stmt.target.id)
        elif isinstance(stmt, ast.With):
            for item in stmt.items:
                if isinstance(item.optional_vars, ast.Name):
                    note_write(item.optional_vars.id)
        elif isinstance(stmt, ast.Delete):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    note_write(target.id)

    info = {}
    for name, count in counts.items():
        if count != 1 or name in written_elsewhere:
            continue
        stmt = inits.get(name)
        if stmt is None or not isinstance(stmt.value, ast.expr):
            continue
        if not _is_pure_expr_local(stmt.value):
            continue
        # A self-referencing initializer (t = t + 1) would re-inject the name
        # on every substitution - infinite loop. Exclude outright.
        if any(isinstance(n, ast.Name) and n.id == name
               for n in ast.walk(stmt.value)):
            continue
        uses = _loads_of(
            [s for s in stmts if s is not stmt], name
        )
        if uses:
            info[name] = {"stmt": stmt, "expr": stmt.value, "uses": uses}
    return info


def _is_pure_expr_local(node: ast.expr) -> bool:
    from de4py.engines.onyx.constant_eval import _is_pure_expr
    return _is_pure_expr(node)


class LocalCopyPropagationRule(Rule):

    name = "copy_propagation"
    safety = "probably_safe"
    event_category = "COPY-PROP"

    MAX_TREE_NODES = 5000

    def applies(self, ctx):
        node_count = sum(1 for _ in ast.walk(ctx.tree))
        if node_count > self.MAX_TREE_NODES:
            return
        seen_lists: set = set()
        for stmts in statement_lists(ctx.tree):
            key = id(stmts)
            if key in seen_lists:
                continue
            # one list at a time keeps patch application unambiguous
            info = _scan_scope(stmts)
            for name, meta in info.items():
                yield Match(node=meta["stmt"],
                            data={"name": name, "list_id": key,
                                  "count": meta["uses"]})
            seen_lists.add(key)
            if info:
                break

    def _substitute(self, stmts, name, expr, skip_stmt):
        class _Replacer(ast.NodeTransformer):
            def visit_Name(self, node):
                if node.id == name and isinstance(node.ctx, ast.Load):
                    return ast.copy_location(_copy.deepcopy(expr), node)
                return node

        replaced = False
        index = 0
        while index < len(stmts):
            stmt = stmts[index]
            if stmt is skip_stmt:
                index += 1
                continue
            scoped = any(isinstance(n, _SCOPED) for n in ast.walk(stmt))
            binds = any(
                isinstance(n, ast.Name) and n.id == name
                for comp_node in ast.walk(stmt)
                if isinstance(comp_node, ast.comprehension)
                for n in ast.walk(comp_node.target)
            )
            touches = any(isinstance(n, ast.Name) and n.id == name
                          for n in ast.walk(stmt))
            if not touches or scoped or binds:
                index += 1
                continue
            new = _Replacer().visit(_copy.deepcopy(stmt))
            ast.fix_missing_locations(new)
            stmts[index:index + 1] = (
                new.body if isinstance(new, ast.Module) else [new]
            )
            replaced = True
            index += 1
        return replaced

    def transform(self, ctx, match):
        name = match.data["name"]
        expr_holder = match.node.value

        for stmts in statement_lists(ctx.tree):
            if match.node in stmts:
                replaced = self._substitute(stmts, name, expr_holder, match.node)
                if not replaced:
                    return None
                stmts.remove(match.node)
                ctx.log("COPY-PROP", f"propagated temp '{name}'",
                        rule=self.name, confidence=0.9)
                ctx.count("temps_propagated")
                return Patch(target=match.node, replacement=None,
                             detail=f"propagated temp '{name}'")
        return None


def default_copy_rules():
    return [LocalCopyPropagationRule()]
