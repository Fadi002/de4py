# ONYX Engine Guide

ONYX is the deobfuscation engine inside de4py. It transforms obfuscated
Python source back into readable code using a rule-based pipeline.

## Quick Start

```bash
# TUI with engine mode
python -m de4py --tui
> onyx <file.py>
> mode aggressive
> explain on
> stats on

# Programmatic
from de4py.engines.onyx.engine import OnyxAlpha
result = OnyxAlpha().deobfuscate("sample.py")
```

## Engine Modes

| Mode | Behavior |
|------|----------|
| `safe` | Only provably safe rules (no output changes unless certain) |
| `normal` | Default: safe + probably-safe rules |
| `aggressive` | All rules including speculative (auto-revert on validation failure) |

Set via CLI (`mode aggressive`) or the GUI dropdown in the deobfuscator screen.

## Architecture

```
Pipeline
├── Structural pass (fast, unlocks obfuscated trees)
│   ├── CpsUnbindRule          - inverts lambda-obfuscator let-bindings
│   └── CpsFunctionDeflateRule - converts FIX-wrapped lambdas to def stmts
├── Convergence loop (legacy stages: string decode, flow, etc.)
├── Simplification pass (cleanup + optimization)
│   ├── LambdaIifeReduceRule   - beta-reduces IIFE shells
│   ├── JunkStatementsRule     - removes no-op expressions
│   ├── ConstantBranchRule     - resolves literal-condition ifs
│   ├── UnreachableAfterTerm   - drops code after return/raise
│   ├── SelfAssignmentRule     - removes x = x
│   ├── RedundantPassRule      - removes unnecessary pass statements
│   ├── LocalCopyPropagation   - inlines single-assign temporaries
│   ├── ForwardingProxyInline  - resolves proxy function calls
│   ├── DeadStoreRule          - removes assignments to unused names
│   ├── IdentityOpRule         - folds x+0, x*1, x^0, etc.
│   ├── TautologyCompareRule   - resolves always-true/false predicates
│   ├── BuiltinAliasResolve    - resolves _106 = len → len(...)
│   ├── GetattrResolveRule     - getattr(obj, 'attr') → obj.attr
│   ├── InlineWrapperFunctions - identity/const-return wrappers
│   ├── DeadWrapperDefinition  - removes orphaned wrapper defs
│   ├── PrimitiveRenameRule    - renames λa.λb.a+b to add
│   └── FixpointRenameRule     - renames Y-combinator to _fixpoint
└── Post-convergence simplification
```

## Decoder Registry

Structural AST-level detectors for encoded strings:

```python
from de4py.engines.onyx.strings.registry import scan_tree, register, Decoder

class MyDecoder(Decoder):
    name = "custom_xor"
    def detect(self, node): ...
    def decode(self, node): ...

register(MyDecoder())
```

Built-in decoders: `b64`, `hex`, `zlib`, `chr_chain`

## Adding Custom Rules

```python
from de4py.engines.onyx.framework.rules import Rule, Match, Patch

class MyRule(Rule):
    name = "my_rule"
    safety = "safe"  # safe | probably_safe | speculative
    event_category = "MY-CATEGORY"

    def applies(self, ctx):
        # ctx.tree is the parsed AST; yield Match(node=...) for each finding
        ...

    def transform(self, ctx, match):
        # Return Patch(target=stmt, replacement=new_stmt_or_list)
        # replacement=None removes the target statement
        ...
```

Register in `pipeline.py` `_run_framework_pass()`.

## CLI Commands

| Command | Effect |
|---------|--------|
| `mode <safe\|normal\|aggressive>` | Set engine analysis mode |
| `explain <on\|off>` | Show transformation log after processing |
| `stats <on\|off>` | Show statistics counters |
| `max_iterations <n>` | Override governor iteration limit |

## Crash Safety

The engine runs in an isolated worker subprocess. A native crash
(stack overflow from deeply nested trees) cannot kill the host app.
On crash, the original source is preserved and a clean error is shown.

Override with env var `DE4PY_INPROCESS=1` for debugging.

## Testing

```bash
pytest de4py/engines/onyx/tests/
```

Differential execution tests verify that transformations preserve
semantics by running both original and cleaned code in isolated
subprocesses and comparing behavior.
