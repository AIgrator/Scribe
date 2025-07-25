# settings_manager.py
import json
import locale
import logging
import os

from PyQt5.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

class SettingsManager(QObject):
    DEFAULTS = {
        "modes": {  # Hotkeys for switching modes
            "transcribe_mode": "Ctrl+Shift+Q",  # Hotkey for transcribe mode
            "command_mode": "Ctrl+Alt+Q",       # Hotkey for command mode
        },
        "blocksize": 4000,  # Audio block size for processing
        "selected_microphone": None,  # Name of the selected microphone device
        "language": "",         # Recognition language (vosk model)
        "ui_language": "en",    # UI language
        "inserter_type": "keyboard",  # Text inserter type: 'keyboard' or 'clipboard'
        "current_model": "",    # Path to the current recognition model
        "models": {},            # Downloaded models: {"en": [ {...}, {...} ], "ru": [ {...} ]}
        "models_hotkeys": {},   # Hotkeys for switching models by language
        "replaces": {},         # Word/phrase replacements dictionary
        "commands_openfile": {},  # Voice commands for opening files/programs
        "commands_hotkey": {},    # Voice commands for hotkeys
        "enable_replacements": True,  # Enable word replacement for final text
        "enable_partial_replacements": True,  # Enable word replacement for partial insertions
        "keyboard_settings": {   # Settings for keyboard inserter
            "key_delay_ms": 20,         # Delay between characters (ms)
            "after_text_delay_ms": 5,  # Delay after all text is inserted (ms per character)
            "backspace_delay_ms": 10   # Delay between backspaces (ms)
        },
        "clipboard_settings": {  # Settings for clipboard inserter
            "clipboard_delay_ms": 10   # Delay between sending clipboard commands (ms)
        },
        "transcribe_to_file": False,   # Whether to write final results to file
        "log_to_file": False,          # Whether to log program activity to file
        "log_level": "DEBUG",  # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
        "tray_color": {  # Colors for tray icon states
            "text_color": [255, 255, 255],        # Color for normal text
            "transcribe_color": [255, 106, 0],    # Color for transcribe mode
            "command_color": [72, 0, 255]         # Color for command mode
        },
        "fuzzy_match_hotkey": 90,      # Threshold for fuzzy_match hotkeys (80-100, default 90)
        "fuzzy_match_openfile": 90,     # Threshold for fuzzy_match for launching programs (80-100, default 90)
        "main_window": {
            "show_on_startup": True, # Whether to show main window on startup application
            "close_behavior": "tray", # Behavior when closing main window: 'tray' or 'exit'
            "position": {}, # Position of the main window (x, y) save when closing
            "always_on_top": False, # Whether to keep main window always on top
            "show_waveform": True,  # Whether to show audio waveform indicator
            "sizes": {
                "window_width": 600,  # Default width of the main window
                "window_height": 250, # Default height of the main window
                "waveform_height": 128,  # Height of the waveform widget
                "btn_ico_height": 64,  # Height of the ico in the main window
                "btn_ico_width": 64,   # Width of the ico in the main window
                "btn_height": 75, # Height of the buttons in the main window
                "btn_width": 75,  # Width of the buttons in the main window
                "btn_mode_width": 150,  # Width of the mode buttons in the main window
                "btn_ico_mode_width": 128,  # Width of the mode buttons with icons in the main window
            },
            "size_mode": "medium",  # Size mode for the main window (small, medium, large)
            "theme": "auto",  # Theme for the main window (auto, dark, light)
            "open_on_tray_click": True # Whether to open main window on left click on tray icon
        },
        "auto_stop_timeout": 0  # Timeout in seconds for auto-stopping listening, 0 = never
    }

    @staticmethod
    def write(settings_dict, settings_file):
        """Write the settings dictionary to the settings_file with error handling."""
        try:
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings_dict, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to write settings to {settings_file}: {e}")
    @staticmethod
    def create_default_settings_if_needed(settings_file='settings.json', lang_dict=None):
        """If settings.json does not exist, create it with ui_language determined by system language or 'en'."""
        if os.path.exists(settings_file):
            return
        sys_lang = None
        try:
            sys_lang = locale.getdefaultlocale()[0]
            if sys_lang:
                sys_lang = sys_lang.split('_')[0]
        except Exception:
            sys_lang = None
        if lang_dict is None:
            lang_dict = {'en': {}}
        if sys_lang and sys_lang in lang_dict:
            ui_language = sys_lang
        else:
            ui_language = 'en'
        SettingsManager.write({"ui_language": ui_language}, settings_file)


    def __init__(self, settings_file='settings.json'):
        super().__init__()
        self.SETTINGS_FILE = settings_file
        self._settings = self._load_settings()

    def _load_settings(self):
        try:
            with open(self.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Migration for main_window settings from old flat structure
            if 'main_window_close_behavior' in data:
                main_window_settings = {
                    'show_on_startup': data.pop('show_main_window_on_startup', True),
                    'close_behavior': data.pop('main_window_close_behavior', 'tray'),
                    'geometry': data.pop('main_window_geometry', None),
                    'always_on_top': data.pop('main_window_always_on_top', False)
                }
                data['main_window'] = main_window_settings
                logger.info("Migrated old main window settings to new nested structure.")

            # Update missing fields with defaults
            for k, v in self.DEFAULTS.items():
                if k not in data:
                    data[k] = v
                elif isinstance(v, dict):
                    for sub_k, sub_v in v.items():
                        if sub_k not in data.get(k, {}):
                            data[k][sub_k] = sub_v
            return data
        except Exception:
            return self.DEFAULTS.copy()

    def get(self, key, default=None):
        return self._settings.get(key, default)

    def set(self, key, value):
        self.set_many({key: value})

    def set_many(self, settings_dict: dict):
        """Set multiple settings at once and emit a single signal."""
        self._settings.update(settings_dict)
        for key, value in settings_dict.items():
            logger.info(f"[SettingsManager] Setting '{key}' to '{value}' (part of batch).")
        logger.info("[SettingsManager] Emitting single settings_changed signal for batch update.")
        self.save()

    def update(self, data: dict):
        self._settings.update(data)
        self.save()

    settings_changed = pyqtSignal(dict)
    def save(self):
        SettingsManager.write(self._settings, self.SETTINGS_FILE)
        self.settings_changed.emit(self._settings)

    def all(self):
        return self._settings
