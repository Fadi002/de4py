# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import ast
import logging
import textwrap
import requests
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


OLLAMA_BASE_URL = "http://localhost:11434"
GENERATE_URL    = f"{OLLAMA_BASE_URL}/api/generate"
TAGS_URL        = f"{OLLAMA_BASE_URL}/api/tags"

# Maximum source length to send to the LLM per chunk
MAX_CHUNK_CHARS = 3000


RENAME_PROMPT = """\
You are an expert Python code analyst specializing in reverse engineering and deobfuscation.

The following Python function has been obfuscated — its variable names, parameter names, and possibly the function name itself have been replaced with meaningless short identifiers.

Your task: Rename ALL identifiers (variables, parameters, function name) to clear, descriptive, idiomatic Python names that reflect their actual purpose in the code logic.

STRICT RULES:
1. Return ONLY the renamed Python function — no explanation, no markdown, no code fences
2. Do NOT change any logic, values, operators, or structure
3. Use snake_case for variables and functions
4. Names must reflect what the identifier actually represents or does
5. If you cannot determine a good name, use a generic but descriptive name like "input_value" or "result_data"
6. Do NOT add comments or docstrings
7. The function must have EXACTLY the same number of parameters as the original
8. The function must have EXACTLY the same number of return statements as the original

Function to rename:
{code}
"""

ANNOTATE_PROMPT = """\
Add a concise one-line docstring and brief inline comments to explain what this Python function does and what its key operations accomplish.

STRICT RULES:
1. Return ONLY the annotated Python function — no explanation, no markdown, no code fences
2. Do NOT change any logic, variable names, or structure
3. Docstring must be a single line in triple quotes immediately after the def line
4. Inline comments should be short (< 10 words) and placed on the relevant line

Function to annotate:
{code}
"""

FIX_SYNTAX_PROMPT = """\
You are an expert Python developer and debugger. 
The following Python code has a syntax error.

Error Message:
{error}

Your task: Fix the syntax error in the code so that it parses as valid Python.

STRICT RULES:
1. Return ONLY the fixed Python code — no explanation, no markdown, no code fences.
2. Do NOT change variable names, logic, or structure unless strictly necessary to fix the syntax.
3. Fix the syntax error precisely where it occurs.

Broken Code:
{code}
"""


class LLMRenamer:

    def __init__(
        self,
        model: str = "qwen2.5-coder:1.5b",
        num_ctx: int = 4096,
        num_batch: int = 512,
        num_gpu: int = -1
    ):
        self.model = model
        self.num_ctx = num_ctx
        self.num_batch = num_batch
        self.num_gpu = num_gpu
        self.available = self._check_ollama()

    def _check_ollama(self) -> bool:
        """Verify Ollama is running and pull the model if missing"""
        try:
            response = requests.get(TAGS_URL, timeout=5)
            if response.status_code != 200:
                logger.error("[LLM] Error: Ollama returned status %s", response.status_code)
                return False

            data = response.json()
            models = [m.get("name", "") for m in data.get("models", [])]

            model_base = self.model.split(":")[0]
            if not any(model_base in m for m in models):
                logger.info("[LLM] Model '%s' not found. Downloading now...", self.model)
                pull_response = requests.post(
                    f"{OLLAMA_BASE_URL}/api/pull",
                    json={"name": self.model, "stream": False},
                    timeout=10000
                )
                if pull_response.status_code == 200:
                    logger.info("[LLM] Successfully downloaded %s!", self.model)
                    return True
                else:
                    logger.error("[LLM] Failed to download model: %s", pull_response.text)
                    return False

            return True
        except requests.exceptions.ConnectionError:
            logger.warning("[LLM] Warning: Could not connect to Ollama at %s", OLLAMA_BASE_URL)
            logger.warning("[LLM] Start it with: ollama serve")
            return False
        except requests.exceptions.Timeout:
            logger.warning("[LLM] Warning: Connection to Ollama timed out")
            return False
        except Exception as e:
            logger.error("[LLM] Error checking Ollama: %s", e)
            return False

    def process_file(self, source: str, annotate: bool = False) -> str:
        """
        Main entry point. Splits source into function-level chunks,
        processes each through the LLM, and reassembles.
        """
        if not self.available:
            return source

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        functions = self._collect_top_level_functions(tree, source)

        if not functions:
            if len(source) <= MAX_CHUNK_CHARS:
                renamed = self._call_llm(source, "rename")
                if renamed and self._is_valid_python(renamed):
                    source = renamed
                    if annotate:
                        annotated = self._call_llm(source, "annotate")
                        if annotated and self._is_valid_python(annotated):
                            source = annotated
            return source

        total = len(functions)
        logger.info("[LLM] Found %d top-level functions to deobfuscate", total)

        source_lines = source.splitlines(keepends=True)

        for idx, (fn_source, fn_node, start_line, end_line) in enumerate(
            reversed(functions), 1
        ):
            display_idx = total - idx + 1
            if len(fn_source) > MAX_CHUNK_CHARS:
                logger.info(
                    "[LLM] [%d/%d] Skipping %r — too large (%d chars)",
                    display_idx, total, fn_node.name, len(fn_source)
                )
                continue

            logger.info("[LLM] [%d/%d] Deobfuscating function: %r...", display_idx, total, fn_node.name)
            renamed = self._call_llm(fn_source, "rename")

            if renamed and renamed != fn_source and self._is_structurally_valid(renamed, fn_node):
                renamed = self._match_indentation(fn_source, renamed)
                source_lines[start_line:end_line] = [renamed + "\n"]
                fn_source = renamed
                logger.info("[LLM] [%d/%d] Renamed successfully", display_idx, total)
            else:
                if renamed and renamed != fn_source:
                    logger.warning(
                        "[LLM] [%d/%d] Rename rejected (structural mismatch or invalid Python)",
                        display_idx, total
                    )
                else:
                    logger.info("[LLM] [%d/%d] No changes or rename failed", display_idx, total)

            if annotate:
                logger.info("[LLM] [%d/%d] Adding annotations to: %r...", display_idx, total, fn_node.name)
                annotated = self._call_llm(fn_source, "annotate")
                if annotated and self._is_valid_python(annotated):
                    annotated = self._match_indentation(fn_source, annotated)
                    source_lines[start_line:end_line] = [annotated + "\n"]
                    logger.info("[LLM] [%d/%d] Annotations added", display_idx, total)

        return "".join(source_lines)

    def fix_syntax(self, code: str, error_msg: str) -> str:
        """
        Attempt to fix syntax errors.
        First tries fast AST-based structural repair, then falls back to LLM.
        """
        # Fast path: try AST structural repair first (no LLM needed)
        repaired = self._ast_repair(code)
        if repaired and repaired != code:
            try:
                import ast as _ast
                _ast.parse(repaired)
                logger.info("[LLM] Syntax fixed by AST repair (no LLM needed)")
                return repaired
            except SyntaxError:
                pass

        if not self.available:
            return code
            
        max_input_chars = int(self.num_ctx * 0.8)
        if len(code) > max_input_chars:
            return code
            
        prompt = FIX_SYNTAX_PROMPT.format(error=error_msg, code=code)
        
        logger.info("[LLM] Requesting syntax fix from Ollama (%s)...", self.model)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature":    0.0,
                "top_p":          0.9,
                "top_k":          20,
                "num_ctx":        self.num_ctx,
                "num_batch":      self.num_batch,
                "num_predict":    2048,
            },
        }

        if self.num_gpu != -1:
            payload["options"]["num_gpu"] = self.num_gpu

        try:
            response = requests.post(GENERATE_URL, json=payload, timeout=180)
            response.raise_for_status()
            raw = response.json().get("response", "")
            fixed_code = self._extract_python(raw)
            if fixed_code and self._is_valid_python(fixed_code):
                logger.info("[LLM] Syntax successfully fixed by LLM")
                return fixed_code
            else:
                logger.warning("[LLM] LLM failed to fix syntax")
                return code
        except Exception as e:
            logger.error("[LLM] Error during syntax fix: %s", e)
            return code


    def _ast_repair(self, source: str) -> str:
        """Fast AST-based structural repair: fix empty bodies, strip bad lines."""
        import ast as _ast

        def _fix_empty(src):
            try:
                tree = _ast.parse(src)
                changed = False
                for node in _ast.walk(tree):
                    for field in ('body', 'orelse', 'finalbody'):
                        val = getattr(node, field, None)
                        if isinstance(val, list) and not val:
                            needs = isinstance(node, (
                                _ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef,
                                _ast.If, _ast.While, _ast.For, _ast.With,
                                _ast.Try, _ast.ExceptHandler,
                            ))
                            if needs and field == 'body':
                                val.append(_ast.Pass())
                                changed = True
                if changed:
                    _ast.fix_missing_locations(tree)
                    return _ast.unparse(tree)
            except Exception:
                pass
            return src

        result = _fix_empty(source)
        try:
            _ast.parse(result)
            return result
        except SyntaxError as e:
            err_lineno = getattr(e, 'lineno', 1) or 1

        lines = source.splitlines(keepends=True)
        idx = err_lineno - 1
        if 0 <= idx < len(lines):
            candidate = ''.join(lines[:idx] + lines[idx+1:])
            candidate = _fix_empty(candidate)
            try:
                _ast.parse(candidate)
                return candidate
            except SyntaxError:
                pass

        return source

    def _collect_top_level_functions(
        self, tree: ast.Module, source: str
    ) -> List[Tuple[str, ast.FunctionDef, int, int]]:
        """
        Extract (source_text, ast_node, start_line_index, end_line_index) for
        each TOP-LEVEL function definition only.
        """
        lines = source.splitlines(keepends=True)
        results = []

        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            start = node.lineno - 1
            end   = node.end_lineno

            fn_source = "".join(lines[start:end])
            results.append((fn_source, node, start, end))

        return results


    def _is_structurally_valid(self, renamed_source: str, original_node: ast.FunctionDef) -> bool:
        """
        Accept LLM output only when it is valid Python AND structurally
        consistent with the original function.
        """
        if not self._is_valid_python(renamed_source):
            return False

        try:
            renamed_tree = ast.parse(renamed_source)
        except SyntaxError:
            return False

        fn_nodes = [
            n for n in renamed_tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        if len(fn_nodes) != 1:
            logger.warning("[LLM] Structural reject: expected 1 function, got %d", len(fn_nodes))
            return False

        renamed_fn = fn_nodes[0]
        orig_args  = len(original_node.args.args)
        new_args   = len(renamed_fn.args.args)
        if orig_args != new_args:
            logger.warning(
                "[LLM] Structural reject: parameter count changed (%d → %d)",
                orig_args, new_args
            )
            return False

        orig_returns = sum(
            1 for n in ast.walk(original_node) if isinstance(n, ast.Return)
        )
        new_returns  = sum(
            1 for n in ast.walk(renamed_fn)    if isinstance(n, ast.Return)
        )
        if orig_returns > 0 and new_returns == 0:
            logger.warning(
                "[LLM] Structural reject: all return statements removed (original had %d)",
                orig_returns
            )
            return False
        if orig_returns > 0 and new_returns > 0 and abs(orig_returns - new_returns) > orig_returns:
            logger.warning(
                "[LLM] Structural reject: return count changed too much (%d → %d)",
                orig_returns, new_returns
            )
            return False

        return True


    def _match_indentation(self, original: str, renamed: str) -> str:
        """
        Re-apply the leading indentation of the original function block.
        """
        first_line = next((l for l in original.splitlines() if l.strip()), "")
        indent = len(first_line) - len(first_line.lstrip())
        prefix = " " * indent

        if indent == 0:
            return renamed

        dedented = textwrap.dedent(renamed)
        reindented_lines = []
        for line in dedented.splitlines(keepends=True):
            if line.strip():
                reindented_lines.append(prefix + line)
            else:
                reindented_lines.append(line)
        return "".join(reindented_lines)


    def _call_llm(self, code: str, task: str) -> Optional[str]:
        """Make a single Ollama API call for the given task."""
        max_input_chars = int(self.num_ctx * 0.8)
        if len(code) > max_input_chars:
            code = code[:max_input_chars]

        prompt_template = RENAME_PROMPT if task == "rename" else ANNOTATE_PROMPT
        prompt = prompt_template.format(code=code)

        logger.info("[LLM] Requesting %s from Ollama (%s)...", task, self.model)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature":    0.05,
                "top_p":          0.9,
                "top_k":          40,
                "num_ctx":        self.num_ctx,
                "num_batch":      self.num_batch,
                "num_predict":    2048,
                "repeat_penalty": 1.1,
            },
        }

        if self.num_gpu != -1:
            payload["options"]["num_gpu"] = self.num_gpu

        try:
            response = requests.post(
                GENERATE_URL,
                json=payload,
                timeout=180,
            )
            response.raise_for_status()
            raw = response.json().get("response", "")
            logger.info("[LLM] Response received")
            return self._extract_python(raw)
        except requests.Timeout:
            logger.warning("[LLM] Timeout — function too complex for %s on CPU", self.model)
            return None
        except Exception as e:
            logger.error("[LLM] Error: %s", e)
            return None

    def _extract_python(self, raw: str) -> Optional[str]:
        """Extract clean Python code from the LLM's raw response."""
        if not raw or not raw.strip():
            return None

        if "```python" in raw:
            parts = raw.split("```python")
            if len(parts) > 1:
                code = parts[1].split("```")[0].strip()
                if code:
                    return self._clean_extracted(code)

        if "```" in raw:
            parts = raw.split("```")
            if len(parts) > 1:
                code = parts[1].strip()
                if code.lower().startswith("python"):
                    code = code[code.index("\n")+1:] if "\n" in code else code[6:]
                code = code.strip()
                if code:
                    return self._clean_extracted(code)

        stripped = raw.strip()

        preamble_patterns = [
            "Here is the renamed", "Here's the renamed", "Here is the fixed",
            "Here's the fixed", "The fixed code", "Renamed function:",
            "Fixed code:", "Here is the corrected",
        ]
        for pat in preamble_patterns:
            if stripped.lower().startswith(pat.lower()):
                idx = stripped.find("\n")
                if idx != -1:
                    stripped = stripped[idx+1:].strip()

        valid_starts = ("def ", "async def ", "class ", "import ", "from ", "#", "@")
        if any(stripped.startswith(s) for s in valid_starts):
            return self._clean_extracted(stripped)

        for i, line in enumerate(stripped.splitlines()):
            if line.strip().startswith(("def ", "async def ", "class ")):
                return self._clean_extracted("\n".join(stripped.splitlines()[i:]))

        return None

    def _clean_extracted(self, code: str) -> Optional[str]:
        """Remove trailing non-code lines (explanations after the function body)."""
        if not code or not code.strip():
            return None
        lines = code.splitlines()
        # Strategy: try progressively shorter versions until it parses
        for end in range(len(lines), 0, -1):
            candidate = "\n".join(lines[:end]).strip()
            if not candidate:
                continue
            try:
                import ast as _ast
                _ast.parse(candidate)
                return candidate
            except SyntaxError:
                continue
        return code.strip() or None

    def _is_valid_python(self, source: str) -> bool:
        """Return True if source parses as valid Python"""
        if not source or not source.strip():
            return False
        try:
            ast.parse(source)
            return True
        except SyntaxError:
            return False