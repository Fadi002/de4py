"""
Translation Manager
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from PySide6.QtCore import QObject, Signal, QLocale, Qt
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)


class TranslationManager(QObject):
    """
    Singleton translation manager for the de4py application.
    
    Signals:
        language_changed(str): Emitted when language is changed, with new language code
    """
    
    # Signal emitted when language changes (new_language_code)
    language_changed = Signal(str)
    
    # Signal emitted when language changes (new_language_code)
    language_changed = Signal(str)
    
    _instance: Optional['TranslationManager'] = None
    
    def __new__(cls):
        """Ensure singleton pattern."""
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
        self._locale = QLocale(QLocale.Language.English)
        
        # Determine locales directory path
        self._locales_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            "locales"
        )
        
        # Load English as fallback
        self._load_fallback()
        
        self._initialized = True
    
    @property
    def current_language(self) -> str:
        """Get the current language code."""
        return self._current_lang
    
    @property
    def is_rtl(self) -> bool:
        """Check if current language is RTL based on loaded metadata."""
        return self._translations.get("IS_RTL", False)
    
    def _load_fallback(self):
        """Load English translations as fallback."""
        fallback_path = os.path.join(self._locales_dir, "en.json")
        try:
            if os.path.exists(fallback_path):
                with open(fallback_path, 'r', encoding='utf-8') as f:
                    self._fallback_translations = json.load(f)
                logger.debug("Loaded English fallback translations")
        except Exception as e:
            logger.error(f"Failed to load fallback translations: {e}")
            self._fallback_translations = {}
    
    def load_language(self, lang_code: str) -> bool:
        """
        Load translations for the specified language.
        
        Args:
            lang_code: ISO 639-1 language code (e.g., 'en', 'ar', 'es')
            
        Returns:
            True if loaded successfully, False otherwise
        """
        lang_file = os.path.join(self._locales_dir, f"{lang_code}.json")
        
        try:
            if os.path.exists(lang_file):
                with open(lang_file, 'r', encoding='utf-8') as f:
                    self._translations = json.load(f)
                logger.info(f"Loaded translations for: {lang_code}")
            else:
                logger.warning(f"Translation file not found: {lang_file}")
                # Fallback to English if not found, but keep code if it's English
                if lang_code != "en":
                     self._translations = self._fallback_translations.copy()
                     # Try to see if it's just missing file but maybe valid code?
                     # No, if file missing, we revert to fallback content but what about current_lang?
                     # Let's fallback gracefully.
                else:
                    self._translations = self._fallback_translations.copy()
            
            self._current_lang = lang_code
            self._update_locale(lang_code)
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
        """
        Change language at runtime and emit signal.
        
        Args:
            lang_code: ISO 639-1 language code
            
        Returns:
            True if changed successfully
        """
        if lang_code == self._current_lang:
            return True
        
        success = self.load_language(lang_code)
        if success:
            # Update application layout direction for RTL
            self._apply_layout_direction()
            # Emit signal for UI updates
            self.language_changed.emit(self._current_lang)
        
        return success
    
    def _update_locale(self, lang_code: str):
        """Update QLocale for formatting."""
        locale_map = {
            "en": QLocale(QLocale.Language.English, QLocale.Country.UnitedStates),
            "ar": QLocale(QLocale.Language.Arabic, QLocale.Country.SaudiArabia),
            "es": QLocale(QLocale.Language.Spanish, QLocale.Country.Spain),
            "fr": QLocale(QLocale.Language.French, QLocale.Country.France),
            "de": QLocale(QLocale.Language.German, QLocale.Country.Germany),
            "ru": QLocale(QLocale.Language.Russian, QLocale.Country.Russia),
            "zh_cn": QLocale(QLocale.Language.Chinese, QLocale.Country.China),
            "zh_tw": QLocale(QLocale.Language.Chinese, QLocale.Country.Taiwan),
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
        self._locale = locale_map.get(lang_code, QLocale(QLocale.Language.English))
    
    def _apply_layout_direction(self):
        """Apply RTL or LTR layout direction to the application."""
        app = QApplication.instance()
        if app:
            if self.is_rtl:
                app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            else:
                app.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    
    def tr(self, key: str, **kwargs) -> str:
        """
        Translate a key with optional placeholder substitution.
        
        Args:
            key: Translation key (e.g., 'nav.home')
            **kwargs: Placeholder values (e.g., name="User")
            
        Returns:
            Translated string, or fallback, or raw key if not found
        
        Example:
            tr("msg.welcome", name="John")  # "Welcome, John!"
        """
        # Try current language
        value = self._get_nested_value(self._translations, key)
        
        # Fallback to English
        if value is None:
            value = self._get_nested_value(self._fallback_translations, key)
        
        # Final fallback: return the key itself
        if value is None:
            logger.debug(f"Translation not found: {key}")
            return key
        
        # Handle non-string values (like plural dicts)
        if isinstance(value, dict):
            # For dict values without count, return 'other' form or first value
            return str(value.get('other', value.get(list(value.keys())[0], key)))
        
        # Substitute placeholders
        result = str(value)
        for name, val in kwargs.items():
            result = result.replace(f"{{{name}}}", str(val))
        
        return result
    
    def ntr(self, key: str, count: int, **kwargs) -> str:
        """
        Translate a key with plural form selection.
        
        Plural forms follow CLDR rules:
        - 'zero': count == 0
        - 'one': count == 1
        - 'two': count == 2
        - 'few': count in 3..10 (for Arabic)
        - 'many': count in 11..99 (for Arabic)
        - 'other': fallback
        
        Args:
            key: Translation key pointing to a plural object
            count: The count to determine plural form
            **kwargs: Additional placeholder values
            
        Returns:
            Translated string with correct plural form
            
        Example:
            ntr("plural.files", count=5)  # "5 files"
        """
        # Get the plural object
        plural_obj = self._get_nested_value(self._translations, key)
        if plural_obj is None:
            plural_obj = self._get_nested_value(self._fallback_translations, key)
        
        if not isinstance(plural_obj, dict):
            # Not a plural key, treat as regular
            return self.tr(key, count=count, **kwargs)
        
        # Determine plural form
        form = self._get_plural_form(count, self._current_lang)
        
        # Get the translation for this form
        value = plural_obj.get(form, plural_obj.get('other', str(count)))
        
        # Substitute placeholders including count
        result = str(value)
        result = result.replace("{count}", str(count))
        for name, val in kwargs.items():
            result = result.replace(f"{{{name}}}", str(val))
        
        return result
    
    def _get_plural_form(self, count: int, lang: str) -> str:
        """
        Determine plural form based on count and language.
        
        Implements simplified CLDR plural rules.
        """
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
        """
        Get a value from nested dict using dot notation.
        
        Args:
            data: Dictionary to search
            key: Dot-separated key (e.g., 'screen.home.title')
            
        Returns:
            Value if found, None otherwise
        """
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
        """
        Format a number according to current locale.
        
        Example:
            en: 1,234.56
            ar: ١٬٢٣٤٫٥٦
            es: 1.234,56
        """
        return self._locale.toString(value, 'f', 2)
    
    def format_date(self, date: datetime, format_type: str = "short") -> str:
        """
        Format a date according to current locale.
        
        Args:
            date: datetime object to format
            format_type: 'short', 'long', or custom format string
            
        Returns:
            Formatted date string
        """
        from PySide6.QtCore import QDate
        
        qdate = QDate(date.year, date.month, date.day)
        
        if format_type == "short":
            return self._locale.toString(qdate, QLocale.FormatType.ShortFormat)
        elif format_type == "long":
            return self._locale.toString(qdate, QLocale.FormatType.LongFormat)
        else:
            return self._locale.toString(qdate, format_type)
    
    def format_currency(self, value: float, symbol: str = "$") -> str:
        """
        Format a currency value according to current locale.
        
        Args:
            value: Numeric value
            symbol: Currency symbol
            
        Returns:
            Formatted currency string
        """
        formatted = self.format_number(value)
        if self.is_rtl:
            return f"{formatted} {symbol}"
        return f"{symbol}{formatted}"
    
    def get_available_languages(self) -> Dict[str, str]:
        """
        Get dictionary of available languages by scanning the locales directory.
        
        Returns:
            Dict mapping language codes to display names (e.g., {'en': 'English'})
        """
        available = {}
        try:
            if not os.path.exists(self._locales_dir):
                return {"en": "English"} # Should check fallback though

            for filename in os.listdir(self._locales_dir):
                if filename.endswith(".json"):
                    lang_code = os.path.splitext(filename)[0]
                    file_path = os.path.join(self._locales_dir, filename)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            # Use LANG_NAME if available, else code
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
            
        return available
