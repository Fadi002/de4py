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
from typing import Any, Dict, List, Optional, Set, Tuple, Union


def _find_state_machine_vars(tree: ast.AST) -> set:
    """Return names used as state variables in while-True dispatcher loops."""
    state_vars: set = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.While):
            continue
        if not (isinstance(node.test, ast.Constant) and node.test.value):
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.If):
                test = stmt.test
                if (isinstance(test, ast.Compare)
                        and len(test.ops) == 1
                        and isinstance(test.ops[0], ast.Eq)
                        and isinstance(test.left, ast.Name)
                        and test.comparators
                        and isinstance(test.comparators[0], ast.Constant)
                        and isinstance(test.comparators[0].value, int)):
                    state_vars.add(test.left.id)
    return state_vars


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

        try:
            changed = True
            passes  = 0
            while changed and passes < 8:
                passes += 1
                before = ast.unparse(tree)

                tree = self._resolve_constant_aliases(tree)
                tree = self._resolve_local_aliases(tree)
                tree = self._resolve_import_aliases(tree)
                tree = self._remove_bogus_try_except(tree)
                tree = self._fold_redundant_var_chains(tree)
                tree = self._resolve_getattr_string_calls(tree)
                tree = self._fold_known_var_joins(tree)
                tree = self._fold_join_and_chr_lists(tree)
                tree = self._inline_const_functions(tree)

                ast.fix_missing_locations(tree)
                after = ast.unparse(tree)
                changed = (before != after)

            return ast.unparse(tree)
        except RecursionError:
            return source
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

        # Protect state machine variables from being inlined
        _sm_protected = _find_state_machine_vars(tree)
        for name in _sm_protected:
            aliases.pop(name, None)

        # Also exclude names that are augmented or used as assignment targets elsewhere
        # Count ALL assignments to each name anywhere in the full tree
        # (not just module-level). If a name is assigned more than once anywhere,
        # it is not a true constant alias and must not be folded.
        all_assign_counts: Dict[str, int] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        all_assign_counts[t.id] = all_assign_counts.get(t.id, 0) + 1
            elif isinstance(node, ast.AugAssign):
                if isinstance(node.target, ast.Name):
                    all_assign_counts[node.target.id] = all_assign_counts.get(node.target.id, 0) + 99
            elif isinstance(node, ast.NamedExpr):
                if isinstance(node.target, ast.Name):
                    all_assign_counts[node.target.id] = all_assign_counts.get(node.target.id, 0) + 99
            elif isinstance(node, (ast.For, ast.comprehension)):
                target = getattr(node, 'target', None)
                if target and isinstance(target, ast.Name):
                    all_assign_counts[target.id] = all_assign_counts.get(target.id, 0) + 99

        # Remove any alias that is re-assigned anywhere in the tree
        for name in list(aliases.keys()):
            if all_assign_counts.get(name, 0) > 1:
                aliases.pop(name)

        class MutationFinder(ast.NodeVisitor):
            def __init__(self):
                self.mutated: Set[str] = set()
            def visit_AugAssign(self, node):
                if isinstance(node.target, ast.Name):
                    self.mutated.add(node.target.id)
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

    # --- 1b. Function-level constant alias folding --------------------------------

    def _resolve_local_aliases(self, tree: ast.Module) -> ast.Module:
        """
        Like _resolve_constant_aliases but applied inside function bodies.
        Folds single-assignment constant aliases within a flat statement list.
        """

        class LocalAliasFolder(ast.NodeTransformer):

            def _fold_stmts(self, stmts):
                import copy as _copy
                # Collect names assigned exactly once to a constant at the TOP of this block
                assign_count = {}
                const_val    = {}
                alias_source_stmts = set()  # ids of statements that are alias sources
                for s in stmts:
                    if (isinstance(s, ast.Assign)
                            and len(s.targets) == 1
                            and isinstance(s.targets[0], ast.Name)
                            and isinstance(s.value, ast.Constant)
                            and isinstance(s.value.value, (str, int, float, bool, bytes, type(None)))):
                        n = s.targets[0].id
                        assign_count[n] = assign_count.get(n, 0) + 1
                        if assign_count[n] == 1:
                            const_val[n] = s.value
                            alias_source_stmts.add(id(s))

                aliases = {k: v for k, v in const_val.items() if assign_count.get(k, 0) == 1}

                # Check for mutation ANYWHERE in the block — but skip the alias source stmts
                for s in stmts:
                    if id(s) in alias_source_stmts:
                        continue  # don't let the alias source stmt invalidate itself
                    for node in ast.walk(s):
                        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                            aliases.pop(node.target.id, None)
                        if isinstance(node, ast.NamedExpr) and isinstance(node.target, ast.Name):
                            aliases.pop(node.target.id, None)
                        if isinstance(node, ast.Assign):
                            for t in node.targets:
                                if isinstance(t, ast.Name) and t.id in aliases:
                                    aliases.pop(t.id, None)
                        if isinstance(node, ast.For) and isinstance(getattr(node, 'target', None), ast.Name):
                            aliases.pop(node.target.id, None)

                if not aliases:
                    return stmts

                class _Replacer(ast.NodeTransformer):
                    def visit_Name(self, node):
                        if node.id in aliases and isinstance(node.ctx, ast.Load):
                            return _copy.deepcopy(aliases[node.id])
                        return node

                new_stmts = []
                for s in stmts:
                    # Remove the alias assignment itself
                    if (isinstance(s, ast.Assign)
                            and len(s.targets) == 1
                            and isinstance(s.targets[0], ast.Name)
                            and s.targets[0].id in aliases):
                        continue
                    new_stmts.append(_Replacer().visit(s))
                return new_stmts

            def visit_FunctionDef(self, node):
                self.generic_visit(node)
                node.body = self._fold_stmts(node.body)
                return node

            visit_AsyncFunctionDef = visit_FunctionDef

            # NOTE: do NOT fold stmts inside if/while/for branch bodies.
            # The return/use of variables may be outside those branches,
            # making variables appear unused when they are actually read.

        return LocalAliasFolder().visit(tree)

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

            def visit_If(self, node: ast.If) -> ast.If:
                self.generic_visit(node)
                node.body   = self._fold_block(node.body)
                node.orelse = self._fold_block(node.orelse)
                return node

            def visit_While(self, node: ast.While) -> ast.While:
                self.generic_visit(node)
                node.body = self._fold_block(node.body)
                return node

            def visit_For(self, node: ast.For) -> ast.For:
                self.generic_visit(node)
                node.body = self._fold_block(node.body)
                return node

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
        tree = _SetAttrInliner().visit(tree)
        return tree


    def _fold_known_var_joins(self, tree: ast.Module) -> ast.Module:
        """
        When a variable is assigned a list of string constants, and then joined:
          parts = ["a", "b", "c"]
          code  = "".join(parts)
        → fold into: code = "abc"
        Works at module level and inside function bodies.
        """
        import copy as _copy

        class VarJoinFolder(ast.NodeTransformer):

            def _fold_block(self, stmts):
                known_lists: Dict[str, list] = {}
                new_stmts = []
                for stmt in stmts:
                    # Track: name = [str_const, str_const, ...]
                    if (isinstance(stmt, ast.Assign)
                            and len(stmt.targets) == 1
                            and isinstance(stmt.targets[0], ast.Name)
                            and isinstance(stmt.value, (ast.List, ast.Tuple))
                            and all(isinstance(e, ast.Constant) and isinstance(e.value, str)
                                    for e in stmt.value.elts)):
                        known_lists[stmt.targets[0].id] = [e.value for e in stmt.value.elts]
                    # Fold: sep.join(name) when name is a known list
                    if (isinstance(stmt, ast.Assign)
                            and isinstance(stmt.value, ast.Call)
                            and isinstance(stmt.value.func, ast.Attribute)
                            and stmt.value.func.attr == 'join'
                            and isinstance(stmt.value.func.value, ast.Constant)
                            and isinstance(stmt.value.func.value.value, str)
                            and len(stmt.value.args) == 1
                            and isinstance(stmt.value.args[0], ast.Name)
                            and stmt.value.args[0].id in known_lists):
                        sep = stmt.value.func.value.value
                        elts = known_lists[stmt.value.args[0].id]
                        folded = sep.join(elts)
                        new_stmt = ast.Assign(
                            targets=stmt.targets,
                            value=ast.Constant(value=folded),
                            lineno=stmt.lineno,
                            col_offset=stmt.col_offset,
                        )
                        new_stmts.append(new_stmt)
                        continue
                    new_stmts.append(stmt)
                return new_stmts

            def visit_FunctionDef(self, node):
                self.generic_visit(node)
                node.body = self._fold_block(node.body)
                return node
            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Module(self, node):
                self.generic_visit(node)
                node.body = self._fold_block(node.body)
                return node

        return VarJoinFolder().visit(tree)

    def _fold_join_and_chr_lists(self, tree: ast.Module) -> ast.Module:
        """
        Fold constant join/chr patterns:
          "".join(["a","b","c"])           -> "abc"
          "".join(chr(x) for x in [N...]) -> "..."  (if all printable)
          "".join(map(chr,[N...]))         -> "..."
          [chr(x) for x in [N...]]        -> ["a","b","c"]  (if all printable)
        Also folds known-arg function calls:
          f(const_arg) when f is a known pure single-arg function returning a constant
        """
        import copy as _copy

        # Collect module-level and top-level int-list assignments for variable resolution
        int_list_vars: dict = {}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign)
                    and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and isinstance(node.value, (ast.List, ast.Tuple))
                    and all(isinstance(e, ast.Constant) and isinstance(e.value, int)
                            for e in node.value.elts)):
                int_list_vars[node.targets[0].id] = [e.value for e in node.value.elts]

        class JoinFolder(ast.NodeTransformer):
            def visit_Call(self, node):
                self.generic_visit(node)

                # "sep".join(iterable)
                if not (isinstance(node.func, ast.Attribute)
                        and node.func.attr == 'join'
                        and isinstance(node.func.value, ast.Constant)
                        and isinstance(node.func.value.value, str)
                        and len(node.args) == 1 and not node.keywords):
                    return node

                sep = node.func.value.value
                arg = node.args[0]

                # Case 1: join a list/tuple of string constants
                if isinstance(arg, (ast.List, ast.Tuple)):
                    if all(isinstance(e, ast.Constant) and isinstance(e.value, str)
                           for e in arg.elts):
                        result = sep.join(e.value for e in arg.elts)
                        return ast.Constant(value=result)

                # Case 2: join(chr(x) for x in [N,N,...]) or join(map(chr,[N,...]))
                chr_vals = self._extract_chr_list(arg)
                if chr_vals is None:
                    # Case 2b: join(chr(x) for x in VAR_NAME) where VAR_NAME is known int list
                    if isinstance(arg, (ast.GeneratorExp, ast.ListComp)):
                        if (len(arg.generators) == 1
                                and isinstance(arg.elt, ast.Call)
                                and isinstance(arg.elt.func, ast.Name)
                                and arg.elt.func.id == 'chr'
                                and len(arg.elt.args) == 1
                                and isinstance(arg.elt.args[0], ast.Name)):
                            gen = arg.generators[0]
                            var = arg.elt.args[0].id
                            if (isinstance(gen.target, ast.Name)
                                    and gen.target.id == var
                                    and not gen.ifs
                                    and isinstance(gen.iter, ast.Name)
                                    and gen.iter.id in int_list_vars):
                                chr_vals = int_list_vars[gen.iter.id]

                if chr_vals is not None:
                    try:
                        result = sep.join(chr(v) for v in chr_vals)
                        if all(32 <= v <= 126 for v in chr_vals):
                            return ast.Constant(value=result)
                    except Exception:
                        pass

                return node

            def _extract_chr_list(self, node):
                """Extract list of ints from chr(x) for x in [...] or map(chr,[...])."""
                # GeneratorExp/ListComp: chr(x) for x in [N,N,...]
                if isinstance(node, (ast.GeneratorExp, ast.ListComp)):
                    if (len(node.generators) == 1
                            and isinstance(node.elt, ast.Call)
                            and isinstance(node.elt.func, ast.Name)
                            and node.elt.func.id == 'chr'
                            and len(node.elt.args) == 1
                            and isinstance(node.elt.args[0], ast.Name)):
                        gen = node.generators[0]
                        var = node.elt.args[0].id
                        if (isinstance(gen.target, ast.Name)
                                and gen.target.id == var
                                and not gen.ifs
                                and isinstance(gen.iter, (ast.List, ast.Tuple))):
                            elts = gen.iter.elts
                            if all(isinstance(e, ast.Constant) and isinstance(e.value, int)
                                   for e in elts):
                                return [e.value for e in elts]
                # map(chr, [N,N,...])
                if (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == 'map'
                        and len(node.args) == 2
                        and isinstance(node.args[0], ast.Name)
                        and node.args[0].id == 'chr'
                        and isinstance(node.args[1], (ast.List, ast.Tuple))):
                    elts = node.args[1].elts
                    if all(isinstance(e, ast.Constant) and isinstance(e.value, int)
                           for e in elts):
                        return [e.value for e in elts]
                return None

        return JoinFolder().visit(tree)


    def _inline_const_functions(self, tree: ast.Module) -> ast.Module:
        """
        Inline zero-arg constant functions:
          def foo(): return 42
          x = foo() + foo()  →  x = 42 + 42
        Then remove the (now-unused) function definitions.
        Only removes a def if it was actually CALLED somewhere in the module.
        """
        inliner = _ConstFnInliner()
        inliner.collect(tree)
        if not inliner.fn_values and not inliner.fn_bodies:
            return tree
        # Only inline/remove functions that are actually called
        called_names = set()
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in (set(inliner.fn_values) | set(inliner.fn_bodies))):
                called_names.add(node.func.id)
        if not called_names:
            return tree
        # Restrict to only called functions
        inliner.fn_values = {k: v for k, v in inliner.fn_values.items() if k in called_names}
        inliner.fn_bodies = {k: v for k, v in inliner.fn_bodies.items() if k in called_names}
        if not inliner.fn_values and not inliner.fn_bodies:
            return tree
        tree = inliner.visit(tree)
        tree = inliner.remove_defs(tree)
        return tree

# --- Helpers ------------------------------------------------------------------

class _SetAttrInliner(ast.NodeTransformer):
    """setattr(obj, 'attr', val) -> obj.attr = val when attr is a valid identifier literal."""
    def visit_Expr(self, node: ast.Expr):
        self.generic_visit(node)
        call = node.value
        if (isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == 'setattr'
                and len(call.args) == 3
                and isinstance(call.args[1], ast.Constant)
                and isinstance(call.args[1].value, str)
                and call.args[1].value.isidentifier()
                and not call.keywords):
            target = ast.Attribute(
                value=call.args[0],
                attr=call.args[1].value,
                ctx=ast.Store(),
            )
            return ast.Assign(
                targets=[target],
                value=call.args[2],
                lineno=node.lineno,
                col_offset=node.col_offset,
            )
        return node


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
    Conservative heuristic: return True only if the block contains
    NO function calls at all (pure constant assignments / trivial ops).
    This avoids incorrectly stripping try/except blocks that protect
    real method calls (os.path.*, subprocess.*, etc).
    """
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                return False   # Any call at all → keep the try/except
            if isinstance(node, (ast.Raise, ast.Assert)):
                return False
    return True


# ─── Zero-arg constant function inliner ─────────────────────────────────────

class _SubstCallsWithKnown(ast.NodeTransformer):
    """Substitute zero-arg function calls with their known constant return values."""
    def __init__(self, fn_values: dict):
        self.fn_values = fn_values
    def visit_Call(self, node):
        self.generic_visit(node)
        if (isinstance(node.func, ast.Name)
                and node.func.id in self.fn_values
                and not node.args and not node.keywords):
            return ast.Constant(value=self.fn_values[node.func.id])
        return node


class _ConstFnInliner(ast.NodeTransformer):
    """
    Collect module-level functions that:
      - take no args and return a single constant  → inline all zero-arg calls
      - take one arg and return a constant expression using only that arg + constants
        → inline when called with a constant argument (safe eval)
    """

    def __init__(self):
        self.fn_values:    Dict[str, Any] = {}   # name → constant (zero-arg)
        self.fn_bodies:    Dict[str, tuple] = {}  # name → (arg_name, return_expr_node)

    def collect(self, tree: ast.Module) -> None:
        # First pass: collect simple constant-returning zero-arg functions
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            if (not node.args.args and not node.args.vararg
                    and not node.args.kwonlyargs
                    and len(node.body) == 1
                    and isinstance(node.body[0], ast.Return)
                    and isinstance(node.body[0].value, ast.Constant)):
                self.fn_values[node.name] = node.body[0].value.value
            elif (len(node.args.args) == 1 and not node.args.vararg
                    and not node.args.kwonlyargs and not node.args.defaults
                    and len(node.body) == 1
                    and isinstance(node.body[0], ast.Return)):
                arg_name = node.args.args[0].arg
                ret_expr = node.body[0].value
                self.fn_bodies[node.name] = (arg_name, ret_expr)

        # Second pass: try to evaluate zero-arg functions that call other known functions
        # Also handle multi-stmt bodies where the function reduces to a constant
        import copy as _copy

        def _try_eval_fn_body(fn_node) -> tuple:
            """Try to statically evaluate a zero-arg function body to a constant."""
            if not (not fn_node.args.args and not fn_node.args.vararg
                    and not fn_node.args.kwonlyargs):
                return False, None
            body = fn_node.body
            if not body or not isinstance(body[-1], ast.Return):
                return False, None
            ret_val = body[-1].value
            if ret_val is None:
                return False, None

            # Build a local env from the function body assignments
            local_env = {}
            for stmt in body[:-1]:
                if (isinstance(stmt, ast.Assign)
                        and len(stmt.targets) == 1
                        and isinstance(stmt.targets[0], ast.Name)):
                    # Try to evaluate the rhs with current local_env + fn_values
                    try:
                        subst = _copy.deepcopy(stmt.value)
                        subst = _SubstCallsWithKnown(self.fn_values).visit(subst)
                        ast.fix_missing_locations(subst)
                        safe_builtins = {
                            'chr': chr, 'ord': ord, 'len': len, 'str': str,
                            'int': int, 'abs': abs, 'join': str.join,
                            'list': list, 'tuple': tuple, 'map': map,
                            'range': range,
                        }
                        code = compile(ast.Expression(body=subst), '<local>', 'eval')
                        val = eval(code, {'__builtins__': safe_builtins}, dict(local_env))
                        local_env[stmt.targets[0].id] = val
                    except Exception:
                        return False, None  # can't evaluate — stop
                else:
                    return False, None  # non-assignment stmt — stop

            # Now try to evaluate the return expression
            try:
                subst_ret = _copy.deepcopy(ret_val)
                subst_ret = _SubstCallsWithKnown(self.fn_values).visit(subst_ret)
                ast.fix_missing_locations(subst_ret)
                safe_builtins = {
                    'chr': chr, 'ord': ord, 'len': len, 'str': str, 'int': int,
                    'abs': abs, 'join': str.join, 'list': list, 'tuple': tuple,
                    'map': map, 'range': range,
                }
                code = compile(ast.Expression(body=subst_ret), '<ret>', 'eval')
                result = eval(code, {'__builtins__': safe_builtins}, dict(local_env))
                if isinstance(result, (str, int, float, bool, type(None))):
                    return True, result
            except Exception:
                pass
            return False, None

        changed = True
        while changed:
            changed = False
            for node in tree.body:
                if not isinstance(node, ast.FunctionDef):
                    continue
                if node.name in self.fn_values:
                    continue
                ok, val = _try_eval_fn_body(node)
                if ok:
                    self.fn_values[node.name] = val
                    changed = True
                    continue
                # Fallback: single-stmt return with known-call substitution
                if not (not node.args.args and not node.args.vararg
                        and not node.args.kwonlyargs
                        and len(node.body) == 1
                        and isinstance(node.body[0], ast.Return)):
                    continue
                ret = node.body[0].value
                try:
                    substituted = _copy.deepcopy(ret)
                    substituted = _SubstCallsWithKnown(self.fn_values).visit(substituted)
                    ast.fix_missing_locations(substituted)
                    code = compile(ast.Expression(body=substituted), '<infer>', 'eval')
                    val = eval(code, {'__builtins__': {'chr': chr, 'ord': ord, 'len': len,
                                                       'str': str, 'int': int, 'abs': abs,
                                                       'join': str.join, 'list': list,
                                                       'map': map, 'range': range}})
                    if isinstance(val, (str, int, float, bool, type(None))):
                        self.fn_values[node.name] = val
                        changed = True
                except Exception:
                    pass

    def _try_eval_with_arg(self, expr_node, arg_name: str, arg_val) -> tuple:
        """Try to evaluate return expr substituting arg_name=arg_val."""
        import copy as _copy
        try:
            substituted = _SubstituteConst(arg_name, arg_val).visit(_copy.deepcopy(expr_node))
            ast.fix_missing_locations(substituted)
            code = compile(ast.Expression(body=substituted), '<inline>', 'eval')
            result = eval(code, {'__builtins__': {'chr': chr, 'ord': ord, 'len': len,
                                                   'str': str, 'int': int, 'abs': abs}})
            return True, result
        except Exception:
            return False, None

    def visit_Call(self, node: ast.Call) -> ast.expr:
        self.generic_visit(node)
        # Zero-arg call
        if (isinstance(node.func, ast.Name)
                and node.func.id in self.fn_values
                and not node.args and not node.keywords):
            return ast.Constant(value=self.fn_values[node.func.id])
        # Single-arg call with constant argument
        if (isinstance(node.func, ast.Name)
                and node.func.id in self.fn_bodies
                and len(node.args) == 1
                and isinstance(node.args[0], ast.Constant)
                and not node.keywords):
            arg_name, ret_expr = self.fn_bodies[node.func.id]
            ok, val = self._try_eval_with_arg(ret_expr, arg_name, node.args[0].value)
            if ok and isinstance(val, (str, int, float, bool, type(None))):
                return ast.Constant(value=val)
        return node

    def remove_defs(self, tree: ast.Module) -> ast.Module:
        inlined = set(self.fn_values) | set(self.fn_bodies)
        # Only remove defs that are no longer called anywhere after inlining
        remaining_calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                remaining_calls.add(node.func.id)
        to_remove = inlined - remaining_calls
        tree.body = [
            n for n in tree.body
            if not (isinstance(n, ast.FunctionDef) and n.name in to_remove)
        ]
        return tree


class _SubstituteConst(ast.NodeTransformer):
    """Replace all occurrences of a name with a constant value."""
    def __init__(self, name: str, value):
        self.name  = name
        self.value = value
    def visit_Name(self, node):
        if node.id == self.name and isinstance(node.ctx, ast.Load):
            return ast.Constant(value=self.value)
        return node
