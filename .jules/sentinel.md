# Sentinel's Journal - Critical Security Learnings

## 2026-05-23 - Remote Code Execution (RCE) via Unsafe Eval Environment
**Vulnerability:** The `ProxyCleaner` in the Onyx deobfuscation engine used `eval()` to evaluate constant expressions and proxy calls. Its restricted environment (`_SAFE_ENV`) explicitly included dangerous built-ins: `__import__` and `eval`. This allowed an attacker to craft an obfuscated Python script that, when processed by `de4py`, would execute arbitrary shell commands on the host machine.

**Learning:** Including `__import__` and `eval` in a "safe" environment for static analysis tools is extremely dangerous. Even if intended to handle nested obfuscation, it opens a direct path to RCE during the deobfuscation process itself.

**Prevention:** Always use a strictly minimal set of built-ins for `eval()` or `exec()`. Never include `__import__`, `eval`, `exec`, `open`, or other OS-interacting functions unless absolutely necessary and properly sandboxed. For static analysis, `ast.literal_eval` is preferred when possible, and a whitelist-based approach should be used for anything more complex.
