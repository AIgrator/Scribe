# hotkey_manager.py
import logging

import keyboard
from PyQt5.QtCore import QObject

logger = logging.getLogger(__name__)

class HotkeyManager(QObject):
    """HotkeyManager — a separate class for managing voice input hotkeys."""

    def __init__(self, settings_manager, controller):
        super().__init__()
        self.settings_manager = settings_manager
        self.controller = controller
        self._hotkey_refs = {}
        self.register_hotkeys()
        # Subscribe to settings changes
        self.settings_manager.settings_changed.connect(self.on_settings_changed)

    def on_settings_changed(self, new_settings):
        # Check if the mode hotkey has changed
        new_modes = new_settings.get('modes', self.settings_manager.DEFAULTS['modes'])
        if getattr(self, '_last_registered_modes', None) != new_modes:
            self.register_hotkeys()
            self._last_registered_modes = new_modes

    def register_hotkeys(self):
        # Remove all old hotkeys
        if hasattr(self, '_hotkey_refs'):
            for ref in self._hotkey_refs.values():
                try:
                    keyboard.remove_hotkey(ref)
                except Exception:
                    pass
            self._hotkey_refs.clear()
        else:
            self._hotkey_refs = {}
        modes = self.settings_manager.get('modes', {})
        # Transcription mode
        transcribe_hotkey = modes.get('transcribe_mode', 'Ctrl+Shift+Q')
        self._hotkey_refs['transcribe'] = keyboard.add_hotkey(transcribe_hotkey, self.controller.switch_to_transcribe_mode)
        logger.info(f"Press {transcribe_hotkey} for transcription mode.")
        # Command mode
        command_hotkey = modes.get('command_mode', 'Ctrl+Alt+Q')
        self._hotkey_refs['command'] = keyboard.add_hotkey(command_hotkey, self.controller.switch_to_command_mode)
        logger.info(f"Press {command_hotkey} for command mode.")

        # Hotkeys for switching models
        models_dict = self.settings_manager.get('models', {})
        models_hotkeys = self.settings_manager.get('models_hotkeys', {})
        model_names = set()
        for lang_models in models_dict.values():
            for model in lang_models:
                name = model.get('name')
                if name:
                    model_names.add(name)
        for model_name in model_names:
            hotkey = models_hotkeys.get(model_name, '')
            if hotkey:
                def make_switch_model(model_name):
                    return lambda: self._switch_model(model_name)
                self._hotkey_refs[f'model_{model_name}'] = keyboard.add_hotkey(hotkey, make_switch_model(model_name))
                logger.info(f"Press {hotkey} to select model: {model_name}")

        self._last_registered_modes = modes.copy()

    def _switch_model(self, model_name):
        # Changes the current model and language via settings_manager (similar to selection via the models window)
        logger.info(f"Switching to model: {model_name}")
        models_dict = self.settings_manager.get('models', {})
        model_lang = None
        # Find the language for this model (same as in the models window)
        for lang, lang_models in models_dict.items():
            for model in lang_models:
                if model.get('name') == model_name:
                    model_lang = model.get('language', lang)
                    break
            if model_lang:
                break
        if model_lang is None:
            logger.error(f"Failed to determine language for model {model_name}")
            return
        self.settings_manager.set('current_model', model_name)
        self.settings_manager.set('language', model_lang)

    def clear(self):
        """Removes all hotkeys and breaks references to controller to prevent memory leaks."""
        if hasattr(self, '_hotkey_refs'):
            for ref in self._hotkey_refs.values():
                try:
                    keyboard.remove_hotkey(ref)
                except Exception:
                    pass
            self._hotkey_refs.clear()
        self.controller = None
        logger.info("All hotkeys removed and controller reference cleared")
