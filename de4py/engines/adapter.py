# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from typing import Callable, Any, Dict
from de4py.core.interfaces import Deobfuscator

PROJECT_SIGNATURE = "de4py-core-signature-7f3a91"

class LegacyDeobfuscatorAdapter(Deobfuscator):
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
