# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import ast
import re
import textwrap
import requests
import json
from typing import Optional, List, Tuple


# --- Constants ----------------------------------------------------------------

OLLAMA_BASE_URL = "http://localhost:11434"
GENERATE_URL    = f"{OLLAMA_BASE_URL}/api/generate"
TAGS_URL        = f"{OLLAMA_BASE_URL}/api/tags"

# Maximum source length to send to the LLM per chunk
MAX_CHUNK_CHARS = 3000


# --- Prompts ------------------------------------------------------------------

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

# --- Engine -------------------------------------------------------------------

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
                print(f"[LLM] Error: Ollama returned status {response.status_code}")
                return False

            data = response.json()
            models = [m.get("name", "") for m in data.get("models", [])]

            model_base = self.model.split(":")[0]
            if not any(model_base in m for m in models):
                print(f"[LLM] Model '{self.model}' not found. Downloading now (this may take a few minutes)...")
                pull_response = requests.post(
                    f"{OLLAMA_BASE_URL}/api/pull",
                    json={"name": self.model, "stream": False},
                    timeout=10000
                )
                if pull_response.status_code == 200:
                    print(f"[LLM] Successfully downloaded {self.model}!")
                    return True
                else:
                    print(f"[LLM] Failed to download model: {pull_response.text}")
                    return False

            return True
        except requests.exceptions.ConnectionError:
            print(f"[LLM] Warning: Could not connect to Ollama at {OLLAMA_BASE_URL}")
            print(f"[LLM] Start it with: ollama serve")
            return False
        except requests.exceptions.Timeout:
            print(f"[LLM] Warning: Connection to Ollama timed out")
            return False
        except Exception as e:
            print(f"[LLM] Error checking Ollama: {e}")
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
        print(f"[LLM] Found {total} top-level functions to deobfuscate")

        source_lines = source.splitlines(keepends=True)

        for idx, (fn_source, fn_node, start_line, end_line) in enumerate(
            reversed(functions), 1
        ):
            display_idx = total - idx + 1
            if len(fn_source) > MAX_CHUNK_CHARS:
                print(
                    f"[LLM] [{display_idx}/{total}] Skipping {fn_node.name!r} "
                    f"— too large ({len(fn_source)} chars)"
                )
                continue

            print(f"[LLM] [{display_idx}/{total}] Deobfuscating function: {fn_node.name!r}...")
            renamed = self._call_llm(fn_source, "rename")

            if renamed and renamed != fn_source and self._is_structurally_valid(renamed, fn_node):
                renamed = self._match_indentation(fn_source, renamed)
                source_lines[start_line:end_line] = [renamed + "\n"]
                fn_source = renamed
                print(f"[LLM] [{display_idx}/{total}] Renamed successfully")
            else:
                if renamed and renamed != fn_source:
                    print(
                        f"[LLM] [{display_idx}/{total}] Rename rejected "
                        f"(structural mismatch or invalid Python)"
                    )
                else:
                    print(f"[LLM] [{display_idx}/{total}] No changes or rename failed")

            if annotate:
                print(f"[LLM] [{display_idx}/{total}] Adding annotations to: {fn_node.name!r}...")
                annotated = self._call_llm(fn_source, "annotate")
                if annotated and self._is_valid_python(annotated):
                    annotated = self._match_indentation(fn_source, annotated)
                    source_lines[start_line:end_line] = [annotated + "\n"]
                    print(f"[LLM] [{display_idx}/{total}] Annotations added")

        return "".join(source_lines)

    def fix_syntax(self, code: str, error_msg: str) -> str:
        """Attempt to fix syntax errors using the LLM."""
        if not self.available:
            return code
            
        max_input_chars = int(self.num_ctx * 0.8)
        if len(code) > max_input_chars:
            return code
            
        prompt = FIX_SYNTAX_PROMPT.format(error=error_msg, code=code)
        
        print(f"[LLM] Requesting syntax fix from Ollama ({self.model})...")
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
            breakpoint()
            fixed_code = self._extract_python(raw)
            if fixed_code and self._is_valid_python(fixed_code):
                print("[LLM] Syntax successfully fixed by LLM")
                return fixed_code
            else:
                print("[LLM] LLM failed to fix syntax")
                return code
        except Exception as e:
            print(f"[LLM] Error during syntax fix: {e}")
            return code

    # --- Source extraction ----------------------------------------------------

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

    # --- Structural validation ------------------------------------------------

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
            print(f"[LLM] Structural reject: expected 1 function, got {len(fn_nodes)}")
            return False

        renamed_fn = fn_nodes[0]
        orig_args  = len(original_node.args.args)
        new_args   = len(renamed_fn.args.args)
        if orig_args != new_args:
            print(
                f"[LLM] Structural reject: parameter count changed "
                f"({orig_args} → {new_args})"
            )
            return False

        orig_returns = sum(
            1 for n in ast.walk(original_node) if isinstance(n, ast.Return)
        )
        new_returns  = sum(
            1 for n in ast.walk(renamed_fn)    if isinstance(n, ast.Return)
        )
        if orig_returns > 0 and new_returns == 0:
            print(
                f"[LLM] Structural reject: all return statements removed "
                f"(original had {orig_returns})"
            )
            return False

        return True

    # --- Indentation normalisation --------------------------------------------

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

    # --- LLM call -------------------------------------------------------------

    def _call_llm(self, code: str, task: str) -> Optional[str]:
        """Make a single Ollama API call for the given task."""
        max_input_chars = int(self.num_ctx * 0.8)
        if len(code) > max_input_chars:
            code = code[:max_input_chars]

        prompt_template = RENAME_PROMPT if task == "rename" else ANNOTATE_PROMPT
        prompt = prompt_template.format(code=code)

        print(f"[LLM] Requesting {task} from Ollama ({self.model})...")
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
            print(f"[LLM] Response received")
            return self._extract_python(raw)
        except requests.Timeout:
            print(f"[LLM] Timeout — function too complex for {self.model} on CPU")
            return None
        except Exception as e:
            print(f"[LLM] Error: {e}")
            return None

    def _extract_python(self, raw: str) -> Optional[str]:
        """Extract clean Python code from the LLM's raw response."""
        if not raw or not raw.strip():
            return None

        if "```python" in raw:
            parts = raw.split("```python")
            if len(parts) > 1:
                code = parts[1].split("```")[0].strip()
                return code if code else None

        if "```" in raw:
            parts = raw.split("```")
            if len(parts) > 1:
                code = parts[1].strip()
                if code.startswith("python\n"):
                    code = code[7:]
                return code if code else None

        stripped = raw.strip()

        valid_starts = ("def ", "async def ", "class ", "import ", "from ", "#", "@")
        if any(stripped.startswith(s) for s in valid_starts):
            return stripped

        return None

    def _is_valid_python(self, source: str) -> bool:
        """Return True if source parses as valid Python"""
        if not source or not source.strip():
            return False
        try:
            ast.parse(source)
            return True
        except SyntaxError:
            return False