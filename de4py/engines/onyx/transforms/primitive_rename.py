import copy as _copy
# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""Recognize and rename curried lambda primitives.

After CPS unbinding, obfuscated code contains assignments like::

    _5 = lambda a: lambda b: a == b

This rule recognizes the operation from the body AST shape and renames
the binding to a readable name (``eq``, ``add``, ``mul``, ...), then
propagates the rename through all subsequent Name loads.
"""

import ast

from de4py.engines.onyx.framework.governor import statement_lists
from de4py.engines.onyx.framework.rules import Match, Patch, Rule

# (op_type, identity_pattern) -> readable name
_CURRIED_OPS = {
    ast.Eq: "eq",
    ast.Add: "add",
    ast.Sub: "sub",
    ast.Mult: "mul",
    ast.FloorDiv: "floordiv",
    ast.Mod: "mod",
    ast.BitXor: "xor",
    ast.BitAnd: "and_",
    ast.BitOr: "or_",
    ast.LShift: "lshift",
    ast.RShift: "rshift",
}

_READABLE = {
    "eq": "eq", "add": "add", "sub": "sub", "mul": "mul",
    "floordiv": "floordiv", "mod": "mod", "xor": "xor",
    "and_": "and_op", "or_": "or_op",
    "lshift": "lshift", "rshift": "rshift",
}


def _classify_curried(node):
    """Classify ``lambda a: lambda b: a OP b`` -> op name or None."""
    if not isinstance(node, ast.Lambda):
        return None
    args = node.args.args
    if len(args) != 1:
        return None
    inner = node.body
    if not isinstance(inner, ast.Lambda):
        return None
    inner_args = inner.args.args
    if len(inner_args) != 1:
        return None
    a_name = args[0].arg
    b_name = inner_args[0].arg
    body = inner.body
    if not isinstance(body, ast.BinOp):
        return None
    if not (isinstance(body.left, ast.Name) and body.left.id == a_name
            and isinstance(body.right, ast.Name) and body.right.id == b_name):
        return None
    return _CURRIED_OPS.get(type(body.op))


def _classify_compare(node):
    """Classify ``lambda a: lambda b: a CMP b`` -> op name or None."""
    if not isinstance(node, ast.Lambda):
        return None
    args = node.args.args
    if len(args) != 1:
        return None
    inner = node.body
    if not isinstance(inner, ast.Lambda):
        return None
    inner_args = inner.args.args
    if len(inner_args) != 1:
        return None
    a_name = args[0].arg
    b_name = inner_args[0].arg
    body = inner.body
    if not isinstance(body, ast.Compare) or len(body.ops) != 1 \
            or len(body.comparators) != 1:
        return None
    if not (isinstance(body.left, ast.Name) and body.left.id == a_name
            and isinstance(body.comparators[0], ast.Name)
            and body.comparators[0].id == b_name):
        return None
    import ast as _ast
    cmp_map = {
        _ast.Eq: "eq", _ast.NotEq: "ne", _ast.Lt: "lt",
        _ast.LtE: "le", _ast.Gt: "gt", _ast.GtE: "ge",
    }
    return cmp_map.get(type(body.ops[0]))


class PrimitiveRenameRule(Rule):

    name = "primitive_rename"
    safety = "safe"
    event_category = "RENAME"

    def applies(self, ctx):
        for stmts in statement_lists(ctx.tree):
            for stmt in stmts:
                if not (isinstance(stmt, ast.Assign)
                        and len(stmt.targets) == 1
                        and isinstance(stmt.targets[0], ast.Name)):
                    continue
                name = stmt.targets[0].id
                op = (_classify_curried(stmt.value)
                      or _classify_compare(stmt.value))
                if op is None:
                    continue
                yield Match(node=stmt, data={"name": name, "op": op})

    def transform(self, ctx, match):
        old_name = match.data["name"]
        new_name = _READABLE.get(match.data["op"], match.data["op"])

        # ensure no collision with an existing different binding
        for other in statement_lists(ctx.tree):
            for s in other:
                if isinstance(s, ast.Assign) and s is not match.node:
                    for t in s.targets:
                        if isinstance(t, ast.Name) and t.id == new_name:
                            return None

        class _Renamer(ast.NodeTransformer):
            changed = 0

            def visit_Name(self, n):
                if n.id == old_name and isinstance(n.ctx, ast.Load):
                    self.changed += 1
                    return ast.copy_location(
                        ast.Name(id=new_name, ctx=ast.Load()), n)
                return n

        renamer = _Renamer()
        count_before = renamer.changed
        for stmts in statement_lists(ctx.tree):
            for i, s in enumerate(stmts):
                if s is match.node:
                    # rename the target too
                    stmts[i] = ast.Assign(
                        targets=[ast.Name(id=new_name, ctx=ast.Store())],
                        value=s.value)
                    ast.fix_missing_locations(stmts[i])
                    continue
                new_s = renamer.visit(_copy.deepcopy(s))
                if renamer.changed > count_before:
                    stmts[i] = new_s
                    ast.fix_missing_locations(new_s)
                    count_before = renamer.changed

        ctx.count("primitives_renamed")
        ctx.log("RENAME", f"renamed '{old_name}' -> '{new_name}' "
                f"({renamer.changed - count_before} refs)",
                rule=self.name)
        return Patch(target=match.node, replacement=None,
                     detail="renamed")  # original already replaced in-place
