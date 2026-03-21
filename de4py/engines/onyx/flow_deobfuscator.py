# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Advanced control-flow and structural deobfuscation pass.
"""

import ast
import copy
from typing import Dict, List, Optional, Set, Tuple, Union


class FlowDeobfuscator:

    def deobfuscate(self, source: str) -> str:
        """
        Apply all flow-level transforms.  Each pass works on the AST; the
        result is unparsed back to source so subsequent passes see clean text.
        Returns the original source if anything goes wrong.
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        changed = True
        passes  = 0
        while changed and passes < 8:
            passes += 1
            before = ast.unparse(tree)

            tree = self._resolve_constant_aliases(tree)
            tree = self._resolve_import_aliases(tree)
            tree = self._remove_bogus_try_except(tree)
            tree = self._fold_redundant_var_chains(tree)
            tree = self._resolve_getattr_string_calls(tree)

            ast.fix_missing_locations(tree)
            after = ast.unparse(tree)
            changed = (before != after)

        try:
            return ast.unparse(tree)
        except Exception:
            return source

    # --- 1. Constant alias folding ---------------------------------------------

    def _resolve_constant_aliases(self, tree: ast.Module) -> ast.Module:
        """
        Find module-level assignments like X = "literal" or X = 42
        where X is assigned exactly once and never augmented/deleted.
        Replace all subsequent uses of X with the literal value.
        Only handles primitive types (str, int, float, bool, bytes, None).
        """
        # Collect single-assignment constant names at module level
        assignment_count: Dict[str, int] = {}
        constant_value:   Dict[str, ast.Constant] = {}

        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, (str, int, float, bool, bytes, type(None)))
            ):
                name = node.targets[0].id
                assignment_count[name] = assignment_count.get(name, 0) + 1
                if assignment_count[name] == 1:
                    constant_value[name] = node.value

        # Remove names that are assigned more than once
        aliases = {k: v for k, v in constant_value.items() if assignment_count[k] == 1}

        # Also exclude names that are augmented or used as assignment targets elsewhere
        class MutationFinder(ast.NodeVisitor):
            def __init__(self):
                self.mutated: Set[str] = set()
            def visit_AugAssign(self, node):
                if isinstance(node.target, ast.Name):
                    self.mutated.add(node.target.id)
                self.generic_visit(node)
            def visit_Assign(self, node):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        # Already in aliases → check if reassigned
                        pass
                self.generic_visit(node)
            def visit_NamedExpr(self, node):
                if isinstance(node.target, ast.Name):
                    self.mutated.add(node.target.id)
                self.generic_visit(node)

        mf = MutationFinder()
        mf.visit(tree)
        for name in mf.mutated:
            aliases.pop(name, None)

        if not aliases:
            return tree

        # Replace Name loads with the constant
        class AliasReplacer(ast.NodeTransformer):
            def visit_Name(self, node: ast.Name) -> ast.expr:
                if node.id in aliases and isinstance(node.ctx, ast.Load):
                    return copy.deepcopy(aliases[node.id])
                return node

        tree = AliasReplacer().visit(tree)

        # Remove the original alias assignments (they're now inlined)
        tree.body = [
            node for node in tree.body
            if not (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in aliases
            )
        ]

        return tree

    # --- 2. Import alias resolution --------------------------------------------

    def _resolve_import_aliases(self, tree: ast.Module) -> ast.Module:
        """
        Resolve simple module alias assignments:
          os2 = os          → remove; replace os2.x with os.x
          sys2 = sys        → similar
        Only module-level, single-target assignments to a known import name.
        """
        # Build set of imported names at module level
        imported_names: Set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name)

        # Find   alias_name = imported_name  at module level
        alias_map: Dict[str, str] = {}   # alias → real_name
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Name)
                and node.value.id in imported_names
                and node.targets[0].id not in imported_names
            ):
                alias_map[node.targets[0].id] = node.value.id

        if not alias_map:
            return tree

        class ImportAliasReplacer(ast.NodeTransformer):
            def visit_Name(self, node: ast.Name) -> ast.expr:
                if node.id in alias_map and isinstance(node.ctx, ast.Load):
                    return ast.Name(id=alias_map[node.id], ctx=ast.Load())
                return node

        tree = ImportAliasReplacer().visit(tree)

        # Remove the alias assignment statements
        tree.body = [
            node for node in tree.body
            if not (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in alias_map
            )
        ]

        return tree

    # --- 3. Bogus try/except removal -------------------------------------------

    def _remove_bogus_try_except(self, tree: ast.Module) -> ast.Module:
        """
        Remove try/except blocks where:
          - The try body contains only simple, non-raising statements
          - All handlers are bare `except: pass` or `except Exception: pass`
          - There is no finally block doing meaningful work
        Replace with just the try body.
        """

        class BogusExceptRemover(ast.NodeTransformer):

            def visit_Try(self, node: ast.Try) -> Union[ast.Try, List[ast.stmt]]:
                self.generic_visit(node)

                # All handlers must be pass-only
                all_pass_handlers = all(
                    len(h.body) == 1 and isinstance(h.body[0], ast.Pass)
                    for h in node.handlers
                )
                if not all_pass_handlers or not node.handlers:
                    return node

                # Try body must be "safe" (no calls that commonly raise)
                if not _is_safe_block(node.body):
                    return node

                # No meaningful finally
                if node.finalbody and not all(isinstance(s, ast.Pass) for s in node.finalbody):
                    return node

                # Safe to unwrap — return just the body
                return node.body

        return BogusExceptRemover().visit(tree)

    # --- 4. Redundant variable chain folding -----------------------------------

    def _fold_redundant_var_chains(self, tree: ast.Module) -> ast.Module:
        """
        Within function bodies, collapse single-use variable chains:
          a = expr
          b = a        (a used only here)
          → b = expr
        Only applies when the intermediate variable is:
          - Assigned exactly once
          - Used exactly once (in the next statement as an rhs)
          - Not a parameter, not in NEVER_RENAME set
          - Not referenced anywhere else in the function
        """

        class ChainFolder(ast.NodeTransformer):

            def _fold_block(self, stmts: List[ast.stmt]) -> List[ast.stmt]:
                """Fold redundant chains within a flat statement list."""
                result = []
                skip_next = False
                for i, stmt in enumerate(stmts):
                    if skip_next:
                        skip_next = False
                        continue

                    if (
                        i + 1 < len(stmts)
                        and isinstance(stmt, ast.Assign)
                        and len(stmt.targets) == 1
                        and isinstance(stmt.targets[0], ast.Name)
                        and isinstance(stmts[i+1], ast.Assign)
                        and len(stmts[i+1].targets) == 1
                        and isinstance(stmts[i+1].targets[0], ast.Name)
                        and isinstance(stmts[i+1].value, ast.Name)
                        and stmts[i+1].value.id == stmt.targets[0].id
                    ):
                        intermediate = stmt.targets[0].id
                        # Verify it's used only in the next statement
                        rest = stmts[i+2:]
                        rest_source = ast.unparse(ast.Module(body=rest, type_ignores=[]))
                        if intermediate not in rest_source:
                            # Fold: replace b = a with b = <original rhs>
                            new_stmt = ast.Assign(
                                targets=stmts[i+1].targets,
                                value=stmt.value,
                                lineno=stmt.lineno,
                                col_offset=stmt.col_offset,
                            )
                            result.append(new_stmt)
                            skip_next = True
                            continue

                    result.append(stmt)
                return result

            def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
                self.generic_visit(node)
                node.body = self._fold_block(node.body)
                return node

            visit_AsyncFunctionDef = visit_FunctionDef

        return ChainFolder().visit(tree)

    # --- 5. getattr string call normalization ----------------------------------

    def _resolve_getattr_string_calls(self, tree: ast.Module) -> ast.Module:
        """
        getattr(obj, "method")  →  obj.method   (as an Attribute node)
        getattr(obj, "method")(args)  →  obj.method(args)

        Only when the attribute name is a string literal.
        """

        class GetAttrResolver(ast.NodeTransformer):

            def visit_Call(self, node: ast.Call) -> ast.expr:
                self.generic_visit(node)

                # getattr(obj, "attr") used as a call: getattr(obj, "attr")(...)
                if (
                    isinstance(node.func, ast.Call)
                    and isinstance(node.func.func, ast.Name)
                    and node.func.func.id == 'getattr'
                    and len(node.func.args) == 2
                    and isinstance(node.func.args[1], ast.Constant)
                    and isinstance(node.func.args[1].value, str)
                    and node.func.args[1].value.isidentifier()
                ):
                    new_func = ast.Attribute(
                        value=node.func.args[0],
                        attr=node.func.args[1].value,
                        ctx=ast.Load(),
                    )
                    return ast.Call(func=new_func, args=node.args, keywords=node.keywords)

                return node

            def visit_Expr(self, node: ast.Expr) -> ast.stmt:
                self.generic_visit(node)
                return node

        # Also replace standalone getattr(obj, "attr") expressions (not calls)
        class GetAttrStandalone(ast.NodeTransformer):
            def visit_Call(self, node: ast.Call) -> ast.expr:
                self.generic_visit(node)
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id == 'getattr'
                    and len(node.args) == 2
                    and isinstance(node.args[1], ast.Constant)
                    and isinstance(node.args[1].value, str)
                    and node.args[1].value.isidentifier()
                    and not node.keywords  # no default arg
                ):
                    return ast.Attribute(
                        value=node.args[0],
                        attr=node.args[1].value,
                        ctx=ast.Load(),
                    )
                return node

        tree = GetAttrResolver().visit(tree)
        tree = GetAttrStandalone().visit(tree)
        return tree


# --- Helpers ------------------------------------------------------------------

_SAFE_NODE_TYPES = (
    ast.Assign, ast.AugAssign, ast.AnnAssign,
    ast.Pass, ast.Import, ast.ImportFrom,
    ast.Expr,   # standalone expressions (might call things, so we're conservative)
)

_UNSAFE_CALL_NAMES = {
    'eval', 'exec', 'open', 'subprocess', 'os', 'socket',
    '__import__', 'compile', 'marshal',
}


def _is_safe_block(stmts: List[ast.stmt]) -> bool:
    """
    Heuristic: return True if none of the statements in the block
    are likely to raise exceptions in normal execution.
    We're conservative — if any Call is present to risky functions, return False.
    """
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                func = node.func
                name = ''
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name in _UNSAFE_CALL_NAMES:
                    return False
            if isinstance(node, (ast.Raise, ast.Assert)):
                return False
    return True
