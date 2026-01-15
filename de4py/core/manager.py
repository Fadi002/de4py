import re
import pkgutil
import importlib
from typing import List, Dict, Optional, Type
from de4py.core.interfaces import BaseEngine, Deobfuscator, Analyzer
from de4py.engines.adapter import LegacyDeobfuscatorAdapter

class EngineManager:
    """Manages registration and retrieval of deobfuscators and analyzers."""

    def __init__(self):
        self._deobfuscators: Dict[str, Deobfuscator] = {}
        self._analyzers: Dict[str, Analyzer] = {}
        self.load_legacy_engines()

    def register_deobfuscator(self, deobfuscator: Deobfuscator):
        self._deobfuscators[deobfuscator.name.lower()] = deobfuscator

    def register_analyzer(self, analyzer: Analyzer):
        self._analyzers[analyzer.name.lower()] = analyzer

    def get_deobfuscator(self, name: str) -> Optional[Deobfuscator]:
        return self._deobfuscators.get(name.lower())

    def get_all_deobfuscators(self) -> List[Deobfuscator]:
        return list(self._deobfuscators.values())

    def load_legacy_engines(self):
        """Loads legacy deobfuscators from de4py.engines.legacy.detector"""
        try:
            from de4py.engines.legacy.detector import obfuscators
            for name, regex, func in obfuscators:
                adapter = LegacyDeobfuscatorAdapter(name, func, description=f"Regex: {regex.pattern}")
                self.register_deobfuscator(adapter)
        except ImportError as e:
            print(f"Failed to load legacy engines: {e}")

    def auto_detect(self, content: str) -> Optional[Deobfuscator]:
        """Tries to match content against loaded legacy regexes."""
        try:
            from de4py.engines.legacy.detector import obfuscators
            for name, regex, func in obfuscators:
                if regex.search(content):
                    return self.get_deobfuscator(name)
        except ImportError:
            pass
        return None
