# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import logging
import os
import threading
from typing import Optional
from de4py.engines.onyx.pipeline import Pipeline

logger = logging.getLogger(__name__)


class OnyxAlpha:
    def deobfuscate(self, file_path: str, ai_overrides: Optional[dict] = None) -> str:
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

        filename = os.path.basename(file_path)

        pipeline_kwargs = {}
        if ai_overrides:
            for key in ("use_llm", "annotate", "ai_explain", "ai_simplify"):
                if key in ai_overrides:
                    pipeline_kwargs[key] = ai_overrides[key]

        try:
            pipeline = Pipeline(**pipeline_kwargs)
            
            result = pipeline.run(source, filename=filename)
        except RecursionError:
            logger.error("[Onyx] FATAL: RecursionError — source is too deeply nested")
            return (
                f"# de4py Onyx-Alpha: RecursionError\n"
                f"# The source code is too deeply nested for safe processing.\n"
                f"# Original code preserved below:\n\n{source}"
            )
        except MemoryError:
            logger.error("[Onyx] FATAL: MemoryError — source is too large")
            return (
                f"# de4py Onyx-Alpha: MemoryError\n"
                f"# The system ran out of memory while processing.\n"
                f"# Original code preserved below:\n\n{source}"
            )
        except KeyboardInterrupt:
            raise  # let the user cancel
        except Exception as e:
            logger.error("[Onyx] FATAL: Unhandled pipeline error: %s", e)
            return (
                f"# de4py Onyx-Alpha: Internal error\n"
                f"# {type(e).__name__}: {e}\n"
                f"# Original code preserved below:\n\n{source}"
            )
        
        if not result.success:
            return (
                f"de4py Onyx-Alpha failed (Syntax Error in output)\n{'-'*40}\n"
                f"Log: {result.log}\n{'-'*40}\n"
                f"Original code preserved:\n\n{result.original}"
            )
            
        header = [
            "# Cleaned by de4py Onyx-Alpha",
            f"# Engines used: {', '.join(result.log) if result.log else 'None'}",
            f"# Triage Score: {result.triage.score:.1f}/10.0" if result.triage else "",
            "\n"
        ]
        
        if result.ai_summary:
            summary_block = "\n".join(
                f"# {line}" if line else "#"
                for line in result.ai_summary.splitlines()
            )
            header.append(f"# {'='*50} AI REVIEW START {'='*50}")
            header.append(f"# AI Analysis:\n{summary_block}")
            header.append(f"# {'='*50} AI REVIEW END {'='*51}")
        
        return "\n".join(header) + "\n" + result.cleaned
