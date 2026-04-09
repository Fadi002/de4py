# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import os
import sys
from de4py.core.interfaces import Deobfuscator
from de4py.engines.onyx.pipeline import Pipeline


class OnyxAlpha(Deobfuscator):
    @property
    def name(self) -> str:
        return "de4py Onyx-Alpha"

    @property
    def description(self) -> str:
        return "Multi-pass pipeline: triage, string decoding, AST cleaning, and rule-based renaming. Uses Ollama local LLM for extreme cases."

    @property
    def version(self) -> str:
        return "1.0.0"

    def deobfuscate(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            return f"Error: File not found: {file_path}"

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
        except Exception as e:
            return f"Error reading file: {e}"

        def _feed():
            try:
                from de4py.engines.onyx.feeder import feed_sample_bg
                feed_sample_bg(file_path)
            except Exception:
                pass
        
        import threading
        threading.Thread(target=_feed, daemon=True).start()

        filename = os.path.basename(file_path)
        
        # Build the pipeline — wrapped in a top-level guard so the app never crashes
        try:
            pipeline = Pipeline(
                use_llm=True,
                llm_model="qwen2.5-coder:1.5b",
                llm_threshold=7.0
            )
            
            result = pipeline.run(source, filename=filename)
        except RecursionError:
            print("[Onyx] FATAL: RecursionError — source is too deeply nested")
            return (
                f"# de4py Onyx-Alpha: RecursionError\n"
                f"# The source code is too deeply nested for safe processing.\n"
                f"# Original code preserved below:\n\n{source}"
            )
        except MemoryError:
            print("[Onyx] FATAL: MemoryError — source is too large")
            return (
                f"# de4py Onyx-Alpha: MemoryError\n"
                f"# The system ran out of memory while processing.\n"
                f"# Original code preserved below:\n\n{source}"
            )
        except KeyboardInterrupt:
            raise  # let the user cancel
        except Exception as e:
            print(f"[Onyx] FATAL: Unhandled pipeline error: {e}")
            return (
                f"# de4py Onyx-Alpha: Internal error\n"
                f"# {type(e).__name__}: {e}\n"
                f"# Original code preserved below:\n\n{source}"
            )
        
        # Build the output text shown in the UI
        if not result.success:
            return (
                f"de4py Onyx-Alpha failed (Syntax Error in output)\n{'-'*40}\n"
                f"Log: {result.log}\n{'-'*40}\n"
                f"Original code preserved:\n\n{result.original}"
            )
            
        header = [
            f"# Cleaned by de4py Onyx-Alpha",
            f"# Engines used: {', '.join(result.log) if result.log else 'None'}",
            f"# Triage Score: {result.triage.score:.1f}/10.0" if result.triage else "",
            "\n"
        ]
        
        return "\n".join(header) + "\n" + result.cleaned
