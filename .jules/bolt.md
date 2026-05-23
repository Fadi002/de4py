## 2026-05-23 - [Consolidated AST passes in StringDecoder]
**Learning:** Multiple consecutive AST parse/unparse cycles on the same source are a major bottleneck in deobfuscation pipelines. Consolidating them into a single lifecycle and using a change-tracking flag instead of `ast.unparse` for convergence checks significantly improves performance.
**Action:** Always prefer consolidating AST transformations into a single NodeTransformer pass when multiple transformations are applied to the same scope.
