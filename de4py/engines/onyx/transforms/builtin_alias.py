import copy as _copy
# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""Resolves single-assignment aliases of builtins and imported names.

Obfuscated code routinely hides real operations behind alias layers::

    _106 = len
    _339 = print
    decode = base64.b64decode
    result = decode(data)

This rule recognizes single-assign bindings whose initializer is a bare
Name load (builtin, module attribute, or another alias) and replaces all
downstream Load occurrences with the resolved original."""

import ast

from de4py.engines.onyx.framework.governor import statement_lists
from de4py.engines.onyx.framework.rules import Match, Patch, Rule


class BuiltinAliasResolveRule(Rule):

    name = "builtin_alias_resolve"
    safety = "probably_safe"
    event_category = "ALIAS"

    def applies(self, ctx):
        for stmts in statement_lists(ctx.tree):
            for stmt in stmts:
                if not (isinstance(stmt, ast.Assign)
                        and len(stmt.targets) == 1
                        and isinstance(stmt.targets[0], ast.Name)):
                    continue
                value = stmt.value
                if isinstance(value, ast.Name) \
                        and isinstance(value.ctx, ast.Load) \
                        and value.id != stmt.targets[0].id:
                    yield Match(node=stmt,
                                data={"alias": stmt.targets[0].id,
                                      "original": value.id})
                elif isinstance(value, ast.Attribute) \
                        and isinstance(value.value, ast.Name) \
                        and isinstance(value.value.ctx, ast.Load):
                    yield Match(node=stmt,
                                data={
                                    "alias": stmt.targets[0].id,
                                    "original": None,
                                    "attr_expr": ast.unparse(value),
                                })

    def transform(self, ctx, match):
        alias = match.data["alias"]
        original = match.data.get("original")
        attr_text = match.data.get("attr_expr")

        if original:
            replacement_node_factory = lambda n: ast.Name(
                id=original, ctx=ast.Load())
            detail = f"resolved alias '{alias}' -> '{original}'"
        else:
            try:
                attr_ast = ast.parse(attr_text, mode='eval').body
            except SyntaxError:
                return None

            def replacement_node_factory(n):
                return ast.parse(attr_text, mode='eval').body

            detail = f"resolved attribute alias '{alias}' -> '{attr_text}'"

        class _Resolver(ast.NodeTransformer):
            changed = 0

            def visit_Name(self, n):
                if n.id == alias and isinstance(n.ctx, ast.Load) \
                        and n is not getattr(n, '_skip', None):
                    self.changed += 1
                    rep = replacement_node_factory(n)
                    return ast.copy_location(rep, n)
                return n

        resolver = _Resolver()
        for stmts in statement_lists(ctx.tree):
            for i, s in enumerate(stmts):
                # skip the assignment itself (we want to REMOVE it later,
                # not rewrite its own target)
                if isinstance(s, ast.Assign) \
                        and len(s.targets) == 1 \
                        and isinstance(s.targets[0], ast.Name) \
                        and s.targets[0].id == alias:
                    continue
                new_s = resolver.visit(_copy.deepcopy(s))
                if resolver.changed > 0:
                    stmts[i] = new_s
                    ast.fix_missing_locations(new_s)

        # remove the alias assignment if fully resolved
        removed = False
        for stmts in statement_lists(ctx.tree):
            for i, s in enumerate(stmts):
                if isinstance(s, ast.Assign) \
                        and len(s.targets) == 1 \
                        and isinstance(s.targets[0], ast.Name) \
                        and s.targets[0].id == alias:
                    del stmts[i]
                    removed = True
                    break
            if removed:
                break

        if resolver.changed > 0:
            ctx.count("aliases_resolved")
            ctx.log("ALIAS", detail, rule=self.name)

        return None
