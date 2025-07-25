# translation_manager.py
import json
import os
from typing import Any, Dict


class TranslationManager:
    @staticmethod
    def get_supported_languages(translations_dir=None):
        """Returns a list of supported language codes by checking .json files in resources/translations."""
        if translations_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            translations_dir = os.path.join(base_dir, 'translations')
        supported_languages = {}
        if os.path.exists(translations_dir):
            for fname in os.listdir(translations_dir):
                if fname.endswith('.json'):
                    lang_code = fname.split('.')[0]
                    supported_languages[lang_code] = {}
        return list(supported_languages.keys())

    def __init__(self, lang_code: str = None, translations_dir: str = None):
        # Always resolve translations_dir relative to project root, not current file
        if translations_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            translations_dir = os.path.join(base_dir, 'translations')
        self.translations_dir = os.path.abspath(translations_dir)
        # Default to English if not specified
        if lang_code is None:
            lang_code = 'en'
        self.lang_code = lang_code
        self.translations = self._load_translations(lang_code)

    def _load_translations(self, lang_code: str) -> Dict[str, str]:
        path = os.path.join(self.translations_dir, f'{lang_code}.json')
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Translation file not found: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def __getitem__(self, key: str) -> str:
        return self.translations[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.translations.get(key, default)

    def set_language(self, lang_code: str):
        self.lang_code = lang_code
        self.translations = self._load_translations(lang_code)

    def keys(self):
        return self.translations.keys()

    def values(self):
        return self.translations.values()

    def items(self):
        return self.translations.items()
