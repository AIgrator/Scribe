# app_initializer.py
"""Module for application initialization: first launch, language selection, model check and download."""
import os
import sys

from PyQt5.QtWidgets import QDialog, QMessageBox

from scribe.model_manager import LanguageSelectDialog, ModelDownloadDialog, ModelManager
from scribe.settings_manager import SettingsManager
from scribe.utils import get_specific_model_path

# Key for storing the current model
CURRENT_MODEL_KEY = 'current_model'

def initialize_app(settings_path, models_dir, lang=None):
    """Application initialization: settings, UI language, recognition language, model path.
    Returns: (settings_manager, settings, ui_language, texts, recognition_language, model_path).
    """  # noqa: D205
    # Determine supported languages using TranslationManager
    from scribe.translation_manager import TranslationManager
    supported_lang_list = TranslationManager.get_supported_languages()
    supported_languages = {lang_code: {} for lang_code in supported_lang_list}
    SettingsManager.create_default_settings_if_needed(settings_path, supported_languages)
    settings_manager = SettingsManager()
    settings = settings_manager.all()
    sys_lang = None
    try:
        import locale
        sys_lang = locale.getdefaultlocale()[0]
        if sys_lang:
            sys_lang = sys_lang.split('_')[0]
    except Exception:
        sys_lang = None
    ui_language = settings.get('ui_language', lang or sys_lang or 'en')
    if ui_language not in supported_languages:
        ui_language = 'en'
    # Use TranslationManager or similar for texts; fallback to empty dict
    try:
        from scribe.translation_manager import TranslationManager
        texts = TranslationManager(ui_language)
    except Exception:
        texts = {}

    model_manager = ModelManager(models_dir)
    chosen_rec_lang = settings.get('language', '')

    if not model_manager.has_models() or not chosen_rec_lang:
        sys_lang = model_manager.get_system_language()
        try:
            models_json = model_manager.fetch_models_json()
        except Exception as e:
            QMessageBox.critical(None, texts['vosk_error_title'], str(e))
            sys.exit(1)
        all_langs = model_manager.get_languages(models_json)
        dlg = LanguageSelectDialog(all_langs, texts, system_lang=sys_lang)
        if dlg.exec_() != QDialog.Accepted:
            sys.exit(0)
        chosen_rec_lang = dlg.get_selected_language()
        settings_manager.set('language', chosen_rec_lang)
        lang_models = model_manager.get_models_for_language(models_json, chosen_rec_lang)
        if not lang_models:
            QMessageBox.critical(None, texts['vosk_error_title'], f"No models for language: {chosen_rec_lang}")
            sys.exit(1)
        dlg = ModelDownloadDialog(models_json, lang_models, models_dir, texts, settings_manager=settings_manager)
        if dlg.exec_() != QDialog.Accepted:
            sys.exit(0)
        # After downloading and extracting the model — find the name of the new model and save it in settings
        lang_dir = os.path.join(models_dir, chosen_rec_lang)
        model_name = None
        if os.path.exists(lang_dir):
            subdirs = [d for d in os.listdir(lang_dir) if os.path.isdir(os.path.join(lang_dir, d))]
            subdirs = [d for d in subdirs if os.path.exists(os.path.join(lang_dir, d, 'am', 'final.mdl'))]
            if subdirs:
                subdirs.sort(key=lambda d: os.path.getmtime(os.path.join(lang_dir, d)), reverse=True)
                model_name = subdirs[0]
                settings_manager.set(CURRENT_MODEL_KEY, model_name)

    recognition_language = settings_manager.get('language', chosen_rec_lang)
    model_name = settings_manager.get(CURRENT_MODEL_KEY, None)

    # Use the centralized function to get the model path
    model_path = get_specific_model_path(recognition_language, model_name)

    # If no valid model path is found, repeat the selection/download process.
    if not model_path:
        sys_lang = model_manager.get_system_language()
        try:
            models_json = model_manager.fetch_models_json()
        except Exception as e:
            QMessageBox.critical(None, texts['vosk_error_title'], str(e))
            sys.exit(1)
        all_langs = model_manager.get_languages(models_json)
        dlg = LanguageSelectDialog(all_langs, texts, system_lang=sys_lang)
        if dlg.exec_() != QDialog.Accepted:
            sys.exit(0)
        chosen_rec_lang = dlg.get_selected_language()
        settings_manager.set('language', chosen_rec_lang)
        lang_models = model_manager.get_models_for_language(models_json, chosen_rec_lang)
        if not lang_models:
            QMessageBox.critical(None, texts['vosk_error_title'], f"No models for language: {chosen_rec_lang}")
            sys.exit(1)
        dlg = ModelDownloadDialog(models_json, lang_models, models_dir, texts, settings_manager=settings_manager)
        if dlg.exec_() != QDialog.Accepted:
            sys.exit(0)

        lang_dir = os.path.join(models_dir, chosen_rec_lang)
        model_name = None
        if os.path.exists(lang_dir):
            subdirs = [d for d in os.listdir(lang_dir) if os.path.isdir(os.path.join(lang_dir, d))]
            subdirs = [d for d in subdirs if os.path.exists(os.path.join(lang_dir, d, 'am', 'final.mdl'))]
            if subdirs:
                subdirs.sort(key=lambda d: os.path.getmtime(os.path.join(lang_dir, d)), reverse=True)
                model_name = subdirs[0]
                settings_manager.set(CURRENT_MODEL_KEY, model_name)

                # Get the path again with the newly downloaded model
                recognition_language = chosen_rec_lang
                model_path = get_specific_model_path(recognition_language, model_name)

    if not model_path:
        QMessageBox.critical(
            None,
            texts['vosk_error_title'],
            texts['vosk_error_body'].format(os.path.join(models_dir, recognition_language))
        )
        sys.exit(1)

    return settings_manager, settings, ui_language, texts, recognition_language, model_path
