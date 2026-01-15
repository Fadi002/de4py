from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple, Callable

class BaseEngine(ABC):
    """Base class for all engines (Deobfuscators, Analyzers)."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        pass

class Deobfuscator(BaseEngine):
    """Abstract base class for deobfuscators."""
    
    @abstractmethod
    def deobfuscate(self, file_path: str) -> str:
        """
        Deobfuscate the given file.
        Returns the deobfuscated code as a string.
        """
        pass

class Analyzer(BaseEngine):
    """Abstract base class for analyzers."""
    
    @abstractmethod
    def analyze(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze the given file.
        Returns a dictionary of analysis results.
        """
        pass
