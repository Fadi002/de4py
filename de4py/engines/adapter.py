from typing import Callable, Any, Dict
from de4py.core.interfaces import Deobfuscator

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
