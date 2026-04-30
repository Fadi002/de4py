# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from typing import Callable, List, Dict, Optional
from de4py.core.interfaces import Deobfuscator, Analyzer


# ── Legacy Adapter ────────────────────────────────────────────────────────────

class LegacyDeobfuscatorAdapter(Deobfuscator):
    """
    Wraps a plain callable (path → str) as a full Deobfuscator implementation.

    Used to integrate the legacy regex-detected deobfuscators into the
    modern engine registry without rewriting them.
    """

    def __init__(self, name: str, deobfuscate_func: Callable[[str], str], description: str = ""):
        self._name = name
        self._func = deobfuscate_func
        self._description = description

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description or f"Legacy deobfuscator: {self._name}"

    @property
    def version(self) -> str:
        return "1.0.0"

    def deobfuscate(self, file_path: str) -> str:
        try:
            return self._func(file_path)
        except Exception as e:
            return f"Error deobfuscating with {self.name}: {e}"


# ── Engine Manager ────────────────────────────────────────────────────────────

class EngineManager:
    """Manages registration and retrieval of deobfuscators and analyzers."""

    def __init__(self):
        self._deobfuscators: Dict[str, Deobfuscator] = {}
        self._analyzers: Dict[str, Analyzer] = {}
        self._legacy_obfuscators = self._load_legacy_obfuscators()
        self.load_legacy_engines()

        try:
            from de4py.engines.onyx.engine import OnyxAlpha
            self.register_deobfuscator(OnyxAlpha())
        except ImportError as e:
            print(f"Failed to load Onyx engine: {e}")

    def register_deobfuscator(self, deobfuscator: Deobfuscator) -> None:
        self._deobfuscators[deobfuscator.name.lower()] = deobfuscator

    def register_analyzer(self, analyzer: Analyzer) -> None:
        self._analyzers[analyzer.name.lower()] = analyzer

    def get_deobfuscator(self, name: str) -> Optional[Deobfuscator]:
        return self._deobfuscators.get(name.lower())

    def get_all_deobfuscators(self) -> List[Deobfuscator]:
        return list(self._deobfuscators.values())

    def load_legacy_engines(self) -> None:
        """Register all legacy regex-detected deobfuscators."""
        for name, regex, func in self._legacy_obfuscators:
            adapter = LegacyDeobfuscatorAdapter(name, func, description=f"Regex: {regex.pattern}")
            self.register_deobfuscator(adapter)

    def auto_detect(self, content: str) -> Optional[Deobfuscator]:
        """Return the first deobfuscator whose regex matches *content*, or None."""
        for name, regex, _ in self._legacy_obfuscators:
            if regex.search(content):
                return self.get_deobfuscator(name)
        return None

    @staticmethod
    def _load_legacy_obfuscators():
        try:
            from de4py.engines.legacy.detector import obfuscators
            return tuple(obfuscators)
        except ImportError as e:
            print(f"Failed to load legacy engines: {e}")
            return ()
