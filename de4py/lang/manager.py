# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.


import os
import json
import logging
from functools import lru_cache
from typing import Dict, Any, Optional
from datetime import datetime

from PySide6.QtCore import QObject, Signal, QLocale, Qt
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)

_LOCALE_MAP = {
    "en": QLocale(QLocale.Language.English, QLocale.Country.UnitedStates),
    "ar": QLocale(QLocale.Language.Arabic, QLocale.Country.SaudiArabia),
    "es": QLocale(QLocale.Language.Spanish, QLocale.Country.Spain),
    "fr": QLocale(QLocale.Language.French, QLocale.Country.France),
    "de": QLocale(QLocale.Language.German, QLocale.Country.Germany),
    "ru": QLocale(QLocale.Language.Russian, QLocale.Country.Russia),
    "zh-cn": QLocale(QLocale.Language.Chinese, QLocale.Country.China),
    "zh-tw": QLocale(QLocale.Language.Chinese, QLocale.Country.Taiwan),
    "pt": QLocale(QLocale.Language.Portuguese, QLocale.Country.Portugal),
    "ja": QLocale(QLocale.Language.Japanese, QLocale.Country.Japan),
    "ko": QLocale(QLocale.Language.Korean, QLocale.Country.RepublicOfKorea),
    "it": QLocale(QLocale.Language.Italian, QLocale.Country.Italy),
    "hi": QLocale(QLocale.Language.Hindi, QLocale.Country.India),
    "tr": QLocale(QLocale.Language.Turkish, QLocale.Country.Turkey),
    "nl": QLocale(QLocale.Language.Dutch, QLocale.Country.Netherlands),
    "vi": QLocale(QLocale.Language.Vietnamese, QLocale.Country.Vietnam),
    "th": QLocale(QLocale.Language.Thai, QLocale.Country.Thailand),
    "fa": QLocale(QLocale.Language.Persian, QLocale.Country.Iran),
    "he": QLocale(QLocale.Language.Hebrew, QLocale.Country.Israel),
}


class TranslationManager(QObject):
    
    language_changed = Signal(str)
    
    _instance: Optional['TranslationManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        
        self._current_lang = "en"
        self._translations: Dict[str, Any] = {}
        self._fallback_translations: Dict[str, Any] = {}
        self._available_languages: Optional[Dict[str, str]] = None
        self._locale = QLocale(QLocale.Language.English)
        
        self._locales_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            "locales"
        )
        
        self._load_fallback()
        
        self._initialized = True
    
    @property
    def current_language(self) -> str:
        return self._current_lang
    
    @property
    def is_rtl(self) -> bool:
        return self._translations.get("IS_RTL", False)
    
    def _load_fallback(self):
        fallback_path = os.path.join(self._locales_dir, "en.json")
        try:
            if os.path.exists(fallback_path):
                self._fallback_translations = self._load_json_file(fallback_path)
                logger.debug("Loaded English fallback translations")
        except Exception as e:
            logger.error(f"Failed to load fallback translations: {e}")
            self._fallback_translations = {}

    @staticmethod
    @lru_cache(maxsize=64)
    def _load_json_file(file_path: str) -> Dict[str, Any]:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def _normalize_lang_code(lang_code: str) -> str:
        return lang_code.lower().replace("_", "-")
    
    def load_language(self, lang_code: str) -> bool:
        normalized_lang_code = self._normalize_lang_code(lang_code)
        lang_file = os.path.join(self._locales_dir, f"{normalized_lang_code}.json")
        
        try:
            if os.path.exists(lang_file):
                self._translations = self._load_json_file(lang_file)
                logger.info(f"Loaded translations for: {normalized_lang_code}")
            else:
                logger.warning(f"Translation file not found: {lang_file}")
                self._translations = self._fallback_translations.copy()
            
            self._current_lang = normalized_lang_code
            self._update_locale(normalized_lang_code)
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {lang_file}: {e}")
            self._translations = self._fallback_translations.copy()
            return False
        except Exception as e:
            logger.error(f"Failed to load language {lang_code}: {e}")
            self._translations = self._fallback_translations.copy()
            return False
    
    def set_language(self, lang_code: str) -> bool:
        if lang_code == self._current_lang:
            return True
        
        success = self.load_language(lang_code)
        if success:
            self._apply_layout_direction()
            self.language_changed.emit(self._current_lang)
        
        return success
    
    def _update_locale(self, lang_code: str):
        self._locale = _LOCALE_MAP.get(lang_code, _LOCALE_MAP["en"])
    
    def _apply_layout_direction(self):
        app = QApplication.instance()
        if app:
            if self.is_rtl:
                app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            else:
                app.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    
    def tr(self, key: str, **kwargs) -> str:
        value = self._get_nested_value(self._translations, key)
        
        if value is None or value == "":
            value = self._get_nested_value(self._fallback_translations, key)
        
        if value is None:
            logger.debug(f"Translation not found: {key}")
            return key
        
        # Handle non-string values (like plural dicts)
        if isinstance(value, dict):
            # For dict values without count, return 'other' form or first value
            return str(value.get('other', value.get(list(value.keys())[0], key)))
        
        result = str(value)
        for name, val in kwargs.items():
            result = result.replace(f"{{{name}}}", str(val))
        
        return result
    
    def ntr(self, key: str, count: int, **kwargs) -> str:
        plural_obj = self._get_nested_value(self._translations, key)
        if plural_obj is None:
            plural_obj = self._get_nested_value(self._fallback_translations, key)
        
        if not isinstance(plural_obj, dict):
            return self.tr(key, count=count, **kwargs)
        
        form = self._get_plural_form(count, self._current_lang)
        
        value = plural_obj.get(form, plural_obj.get('other', str(count)))
        
        if not value:
             fallback_obj = self._get_nested_value(self._fallback_translations, key)
             if isinstance(fallback_obj, dict):
                 value = fallback_obj.get(form, fallback_obj.get('other', str(count)))
        
        result = str(value)
        result = result.replace("{count}", str(count))
        for name, val in kwargs.items():
            result = result.replace(f"{{{name}}}", str(val))
        
        return result
    
    def _get_plural_form(self, count: int, lang: str) -> str:
        if lang == "ar":
            # Arabic has complex plural rules
            if count == 0:
                return "zero"
            elif count == 1:
                return "one"
            elif count == 2:
                return "two"
            elif 3 <= count % 100 <= 10:
                return "few"
            elif 11 <= count % 100 <= 99:
                return "many"
            else:
                return "other"
        else:
            # Simple English/Spanish rules
            if count == 1:
                return "one"
            else:
                return "other"
    
    def _get_nested_value(self, data: Dict, key: str) -> Any:
        # First try direct key lookup (flat structure)
        if key in data:
            return data[key]
        
        # Try nested lookup
        keys = key.split('.')
        current = data
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None
        return current
    
    def format_number(self, value: float) -> str:
        return self._locale.toString(value, 'f', 2)
    
    def format_date(self, date: datetime, format_type: str = "short") -> str:
        from PySide6.QtCore import QDate
        
        qdate = QDate(date.year, date.month, date.day)
        
        if format_type == "short":
            return self._locale.toString(qdate, QLocale.FormatType.ShortFormat)
        elif format_type == "long":
            return self._locale.toString(qdate, QLocale.FormatType.LongFormat)
        else:
            return self._locale.toString(qdate, format_type)
    
    def format_currency(self, value: float, symbol: str = "$") -> str:
        formatted = self.format_number(value)
        if self.is_rtl:
            return f"{formatted} {symbol}"
        return f"{symbol}{formatted}"
    
    def get_available_languages(self) -> Dict[str, str]:
        if self._available_languages is not None:
            return self._available_languages

        available = {}
        try:
            if not os.path.exists(self._locales_dir):
                return {"en": "English"} # Should check fallback though

            for filename in os.listdir(self._locales_dir):
                if filename.endswith(".json"):
                    lang_code = os.path.splitext(filename)[0]
                    file_path = os.path.join(self._locales_dir, filename)
                    
                    try:
                        data = self._load_json_file(file_path)
                        lang_name = data.get("LANG_NAME", lang_code)
                        available[lang_code] = lang_name
                    except Exception:
                        # Skip malformed files
                        continue
        except Exception as e:
            logger.error(f"Error scanning locales: {e}")
            
        # Ensure at least English is present if fallback loaded
        if "en" not in available and self._fallback_translations:
            available["en"] = "English"

        self._available_languages = available
        return self._available_languages
