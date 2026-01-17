"""
de4py Localization Module
"""

from .manager import TranslationManager

# Singleton instance
translation_manager = TranslationManager()

# Convenience helpers
def tr(key: str, **kwargs) -> str:
    """Translate a key with optional placeholder substitution."""
    return translation_manager.tr(key, **kwargs)

def ntr(key: str, count: int, **kwargs) -> str:
    """Translate a key with plural form selection."""
    return translation_manager.ntr(key, count, **kwargs)

def format_number(value: float) -> str:
    """Format a number according to current locale."""
    return translation_manager.format_number(value)

def format_date(date) -> str:
    """Format a date according to current locale."""
    return translation_manager.format_date(date)

__all__ = [
    'translation_manager',
    'tr',
    'ntr',
    'format_number',
    'format_date',
    'TranslationManager',
]
