# ui/settings_window.py
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QListWidget, QStackedWidget, QVBoxLayout

from scribe.utils import resource_path

from .hotkeys_page import HotkeysPageWidget
from .input_settings_page import InputSettingsPageWidget
from .main_settings_page import MainSettingsPageWidget
from .replacements_page import ReplacementsPage
from .voice_hotkeys_page import VoiceHotkeysPage
from .voice_openfile_page import VoiceOpenfilePage
from .vosk_models_page import VoskModelsPageWidget


class SettingsWindow(QDialog):
    def __init__(self, tray_app, texts, settings_manager, parent=None):
        super().__init__(parent)
        self.tray_app = tray_app
        self.texts = texts
        self.settings_manager = settings_manager
        self.settings = self.settings_manager.all()
        self.setWindowTitle(self.texts.get('settings_title', 'Settings'))
        self.setMinimumSize(600, 400)
        self.setWindowIcon(QIcon(resource_path('resources/icon.ico')))

        self.central_layout = QVBoxLayout(self)
        self.main_hbox = QHBoxLayout()

        self.category_list = QListWidget()
        self.category_list.setFixedWidth(150)
        self.main_hbox.addWidget(self.category_list)

        self.pages_stack = QStackedWidget()
        self.main_hbox.addWidget(self.pages_stack)

        self.main_page = MainSettingsPageWidget(self.tray_app, self.texts, self.settings_manager)
        self.input_page = InputSettingsPageWidget(self.texts, self.settings_manager)
        self.hotkeys_page = HotkeysPageWidget(self.texts, self.settings.get('modes', {}), settings_manager=self.settings_manager)
        self.replacements_page = ReplacementsPage(texts=self.texts, settings_manager=self.settings_manager)
        self.voice_hotkeys_page = VoiceHotkeysPage(texts=self.texts, settings_manager=self.settings_manager)
        self.voice_openfile_page = VoiceOpenfilePage(texts=self.texts, settings_manager=self.settings_manager)

        from .window_settings_page import WindowSettingsPageWidget
        self.window_settings_page = WindowSettingsPageWidget(self.texts, self.settings_manager)
        self.vosk_models_page = VoskModelsPageWidget(self.settings_manager, self.texts)

        self.add_category(self.texts.get('settings_hotkeys', 'Hotkeys'), self.hotkeys_page)
        self.add_category(self.texts.get('settings_main', 'General Settings'), self.main_page)
        self.add_category(self.texts.get('settings_input', 'Input Settings'), self.input_page)
        self.add_category(self.texts.get('settings_replacements', 'Replacements'), self.replacements_page)
        self.add_category(self.texts.get('voice_hotkeys_title', 'Voice Hotkeys'), self.voice_hotkeys_page)
        self.add_category(self.texts.get('voice_openfile_title', 'Voice Program Launch'), self.voice_openfile_page)
        self.add_category(self.texts.get('settings_models', 'Vosk Models'), self.vosk_models_page)
        self.add_category(self.texts.get('settings_main_window', 'Main Window'), self.window_settings_page)

        self.category_list.currentRowChanged.connect(self.on_category_changed)

        # OK/Cancel buttons only once
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText(self.texts.get('ok', 'OK'))
        self.buttons.button(QDialogButtonBox.Cancel).setText(self.texts.get('cancel', 'Cancel'))
        self.buttons.accepted.connect(self.save_and_accept)
        self.buttons.rejected.connect(self.reject)

        self.central_layout.addLayout(self.main_hbox)
        self.central_layout.addWidget(self.buttons)

    def on_category_changed(self, idx):
        self.pages_stack.setCurrentIndex(idx)
        # If the hotkeys page is selected — update model hotkeys
        if hasattr(self, 'hotkeys_page') and idx == self.category_list.row(
            self.category_list.findItems(
                self.texts.get('settings_hotkeys', 'Hotkeys'),
                Qt.MatchExactly
            )[0]
        ):
            self.hotkeys_page.update_hotkeys()

    def save_and_accept(self):
        # Save all standard settings
        # Merge existing modes and models_hotkeys with new ones to avoid losing hotkeys for new modes and models
        old_modes = self.settings_manager.get('modes', {})
        new_modes = self.hotkeys_page.get_modes()
        merged_modes = {**old_modes, **new_modes}
        old_models_hotkeys = self.settings_manager.get('models_hotkeys', {})
        new_models_hotkeys = self.hotkeys_page.get_models_hotkeys()
        merged_models_hotkeys = {**old_models_hotkeys, **new_models_hotkeys}
        update_dict = {
            'modes': merged_modes,
            'models_hotkeys': merged_models_hotkeys,
            'inserter_type': self.input_page.get_inserter_type(),
            'keyboard_settings': self.input_page.get_keyboard_settings(),
            'clipboard_settings': self.input_page.get_clipboard_settings(),
            'ui_language': self.main_page.get_ui_language(),
            'transcribe_to_file': self.main_page.get_transcribe_to_file(),
        }
        # Get settings from all pages and merge them
        update_dict.update(self.replacements_page.get_settings())
        update_dict.update(self.voice_hotkeys_page.get_settings())
        update_dict.update(self.voice_openfile_page.get_settings())

        self.settings_manager.update(update_dict)

        # Apply UI language immediately
        if hasattr(self.parent(), 'reload_ui_language'):
            self.parent().reload_ui_language()
        self.accept()

    def add_category(self, name, widget):
        self.category_list.addItem(name)
        if isinstance(widget, QLabel):
            widget.setAlignment(Qt.AlignCenter)
        self.pages_stack.addWidget(widget)

    def closeEvent(self, event):
        self.hide()
        event.ignore()
