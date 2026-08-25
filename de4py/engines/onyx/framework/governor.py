# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import ast

_OSCILLATION_WINDOW = 6

_PASS_REQUIRED_OWNERS = (
    ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
    ast.If, ast.While, ast.For, ast.AsyncFor,
    ast.With, ast.AsyncWith, ast.Try, ast.ExceptHandler,
)


def _iter_stmt_lists(tree: ast.Module):
    stack = [tree]
    while stack:
        node = stack.pop()
        for field_name in ("body", "orelse", "finalbody"):
            stmts = getattr(node, field_name, None)
            if isinstance(stmts, list):
                yield node, field_name, stmts
                stack.extend(s for s in stmts if isinstance(s, ast.AST))
        handlers = getattr(node, "handlers", None)
        if isinstance(handlers, list):
            stack.extend(h for h in handlers if isinstance(h, ast.AST))


def statement_lists(tree: ast.Module):
    for _owner, _field_name, stmts in _iter_stmt_lists(tree):
        yield stmts


def _apply_patch(tree: ast.Module, patch) -> bool:
    for parent, field_name, stmts in _iter_stmt_lists(tree):
        if patch.target not in stmts:
            continue
        idx = stmts.index(patch.target)
        if patch.replacement is None:
            del stmts[idx]
            if (field_name == "body" and not stmts
                    and isinstance(parent, _PASS_REQUIRED_OWNERS)):
                filler = ast.Pass()
                ast.copy_location(filler, patch.target)
                stmts.append(filler)
        elif isinstance(patch.replacement, list):
            for new in patch.replacement:
                ast.copy_location(new, patch.target)
            stmts[idx:idx + 1] = patch.replacement
        else:
            new = patch.replacement
            ast.copy_location(new, patch.target)
            stmts[idx] = new
        ast.fix_missing_locations(patch.target)
        return True
    return False


def run_governor(ctx, registry, deadline_s=None):
    import time as _time
    start = _time.monotonic()
    budget = min(deadline_s or 30.0, 30.0)

    # scale iterations with tree complexity
    node_count = sum(1 for _ in ast.walk(ctx.tree))
    max_iters = ctx.config.max_iterations
    if node_count > 5000:
        max_iters = min(max_iters, 3)
    elif node_count > 1000:
        max_iters = min(max_iters, 6)

    recent = []
    for iteration in range(max_iters):
        elapsed = _time.monotonic() - start
        if deadline_s is not None and elapsed > deadline_s:
            break

        # cheap digest: use node count + first/last stmt types as signature
        sig = (node_count, type(ctx.tree.body[0]).__name__ if ctx.tree.body else "",
               type(ctx.tree.body[-1]).__name__ if ctx.tree.body else "")
        if sig in recent:
            break
        recent.append(sig)
        del recent[:-_OSCILLATION_WINDOW]

        changed = False
        for rule in registry.rules:
            if not ctx.config.allows(rule.safety):
                continue
            rule_start = _time.monotonic()
            try:
                matches = list(rule.applies(ctx))
            except Exception:
                continue
            for match in matches[:20]:
                if _time.monotonic() - start > budget:
                    break
                t0 = _time.monotonic()
                try:
                    patch = rule.transform(ctx, match)
                except (RecursionError, MemoryError):
                    break
                except Exception:
                    continue
                if _time.monotonic() - t0 > 3.0:
                    break
                if patch is None:
                    continue
                if _apply_patch(ctx.tree, patch):
                    ctx.log(rule.event_category, patch.detail,
                            rule=rule.name,
                            confidence=getattr(match, "confidence", 1.0))
                    key = rule.event_category.lower().replace("-", "_")
                    ctx.count(key)
                    changed = True
                if _time.monotonic() - start > budget:
                    break
            if _time.monotonic() - start > budget:
                break
        if not changed:
            break
    return ctx
