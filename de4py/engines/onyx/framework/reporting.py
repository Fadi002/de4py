# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.


from collections import Counter


def render_stats_report(stats: dict) -> str:
    """Format engine stats counters into a readable block."""
    if not stats:
        return ""
    labels = {
        "strings_decoded": "strings decoded",
        "constants_folded": "constants folded",
        "dead_code": "dead statements removed",
        "branches_resolved": "branches resolved",
        "lambdas_reduced": "lambda shells reduced",
        "cps_bindings_removed": "CPS bindings unwrapped",
        "cps_functions_deflated": "CPS functions deflated",
        "cps_chains_deflated": "CPS chains deflated",
        "cps_deflate": "CPS transformations",
        "proxies_inlined": "proxy calls inlined",
        "dead_stores_removed": "dead stores removed",
        "aliases_resolved": "aliases resolved",
        "identity_ops_folded": "identity ops folded",
        "opaque_predicates_resolved": "opaque predicates resolved",
        "primitives_renamed": "primitives renamed",
        "fixpoints_renamed": "fixpoint combinators renamed",
        "getattr_resolved": "getattr chains resolved",
        "inline": "wrappers inlined",
        "rename": "names improved",
        "flow": "flow simplifications",
        "fold": "constant folds",
    }
    lines = ["[Engine Stats]"]
    for key in sorted(stats.keys()):
        value = stats[key]
        label = labels.get(key, key.replace("_", " "))
        lines.append(f"  {label}: {value}")
    return "\n".join(lines)


def render_explain_summary(events: list) -> str:
    """Group explain events by category into a compact summary."""
    if not events:
        return ""
    by_cat: dict = {}
    for e in events:
        cat = e.category
        by_cat.setdefault(cat, []).append(e)

    lines = ["[Transform Log]"]
    for cat in sorted(by_cat.keys()):
        entries = by_cat[cat]
        lines.append(f"\n  [{cat}] ({len(entries)} transformation"
                     f"{'s' if len(entries) != 1 else ''})")
        for e in entries[:5]:
            rule_tag = f" ({e.rule})" if getattr(e, 'rule', '') else ""
            conf = f" conf={e.confidence:.2f}" \
                if getattr(e, 'confidence', 1.0) < 1.0 else ""
            lines.append(f"    {e.detail}{rule_tag}{conf}")
        if len(entries) > 5:
            lines.append(f"    ... and {len(entries) - 5} more")
    return "\n".join(lines)
