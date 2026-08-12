# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from .manager import TranslationManager

translation_manager = TranslationManager()

def tr(key: str, **kwargs) -> str:
    return translation_manager.tr(key, **kwargs)

def ntr(key: str, count: int, **kwargs) -> str:
    return translation_manager.ntr(key, count, **kwargs)

def format_number(value: float) -> str:
    return translation_manager.format_number(value)

def format_date(date) -> str:
    return translation_manager.format_date(date)

__all__ = [
    'translation_manager',
    'tr',
    'ntr',
    'format_number',
    'format_date',
    'TranslationManager',
]
