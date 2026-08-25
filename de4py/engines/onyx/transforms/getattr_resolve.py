import copy as _copy
# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""Resolves ``getattr(obj, "literal")`` calls into direct ``obj.literal``
attribute access when both arguments are statically known."""

import ast

from de4py.engines.onyx.framework.governor import statement_lists
from de4py.engines.onyx.framework.rules import Match, Patch, Rule


class GetattrResolveRule(Rule):

    name = "getattr_resolve"
    safety = "safe"
    event_category = "FOLD"

    def applies(self, ctx):
        for stmts in statement_lists(ctx.tree):
            for stmt in stmts:
                for n in ast.walk(stmt):
                    if isinstance(n, ast.Call) \
                            and isinstance(n.func, ast.Name) \
                            and n.func.id == "getattr" \
                            and len(n.args) == 2 \
                            and not n.keywords \
                            and isinstance(n.args[1], ast.Constant) \
                            and isinstance(n.args[1].value, str) \
                            and n.args[1].value.isidentifier():
                        yield Match(node=stmt)

    def transform(self, ctx, match):
        class _Resolver(ast.NodeTransformer):
            changed = 0

            def visit_Call(self, node):
                self.generic_visit(node)
                if isinstance(node.func, ast.Name) \
                        and node.func.id == "getattr" \
                        and len(node.args) == 2 \
                        and not node.keywords \
                        and isinstance(node.args[1], ast.Constant) \
                        and isinstance(node.args[1].value, str) \
                        and node.args[1].value.isidentifier():
                    obj = node.args[0]
                    attr_name = node.args[1].value
                    new_node = ast.Attribute(
                        value=obj,
                        attr=attr_name,
                        ctx=ast.Load())
                    ast.copy_location(new_node, node)
                    self.changed += 1
                    return new_node
                return node

        resolver = _Resolver()
        new = resolver.visit(_copy.deepcopy(match.node))
        if not resolver.changed:
            return None
        ast.fix_missing_locations(new)
        ctx.count("getattr_resolved", resolver.changed)
        return Patch(target=match.node, replacement=new,
                     detail=f"resolved {resolver.changed} getattr call(s)")
