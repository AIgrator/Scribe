# ui/hotkeys_page.py
from PyQt5.QtWidgets import QFormLayout, QGroupBox, QLabel, QWidget

from .hotkey_line_edit import HotkeyLineEdit


class HotkeysPageWidget(QWidget):
    def __init__(self, texts, settings_modes, parent=None, settings_manager=None):
        super().__init__(parent)
        self.texts = texts
        self.hotkey_inputs = {}
        self.settings_manager = settings_manager
        layout = QFormLayout(self)
        layout.setSpacing(10)
        self.setLayout(layout)

        # Group for operation modes
        self.modes_groupbox = QGroupBox(self.texts.get('hotkey_modes_group', 'Modes'))
        modes_layout = QFormLayout()
        self.modes_groupbox.setLayout(modes_layout)
        # Standard hotkeys
        self.add_hotkey_row(
            'transcribe_mode',
            self.texts.get('hotkey_transcribe_mode', 'Start/stop transcription'),
            settings_modes.get('transcribe_mode', 'Ctrl+Shift+Q'),
            parent_layout=modes_layout
        )
        self.add_hotkey_row(
            'command_mode',
            self.texts.get('hotkey_command_mode', 'Start/stop command mode'),
            settings_modes.get('command_mode', 'Ctrl+Alt+Q'),
            parent_layout=modes_layout
        )
        layout.addRow(self.modes_groupbox)

        # Hotkeys for switching models
        # Get the list of models and their hotkeys from settings_manager
        models = []
        if self.settings_manager is not None:
            models_dict = self.settings_manager.get('models', {})
            for lang_models in models_dict.values():
                for model in lang_models:
                    name = model.get('name')
                    if name:
                        models.append(name)
        # Do not add label and model hotkeys during initialization, only via update_hotkeys()

    def add_hotkey_row(self, key, label_text, hotkey_text, parent_layout=None):
        label = QLabel(label_text)
        hotkey_input = HotkeyLineEdit(self.texts, hotkey_text)
        self.hotkey_inputs[key] = hotkey_input
        if parent_layout is not None:
            parent_layout.addRow(label, hotkey_input)
        else:
            self.layout().addRow(label, hotkey_input)

    def get_modes(self):
        # Only modes (without models)
        return {k: v.text() for k, v in self.hotkey_inputs.items() if k in ('transcribe_mode', 'command_mode')}

    def get_models_hotkeys(self):
        # Only hotkeys for models
        return {k: v.text() for k, v in self.hotkey_inputs.items() if k not in ('transcribe_mode', 'command_mode')}

    def update_hotkeys(self):
        # Completely recreates hotkey inputs for models (e.g., after adding/removing a model)
        layout = self.layout()
        section_label_text = self.texts.get('hotkey_models_section', 'Switch model (by hotkey):')

        # Remove all rows except the first (modes group)
        rows_to_remove = list(range(1, layout.rowCount()))
        for i in reversed(rows_to_remove):
            label_item = layout.itemAt(i, 0)
            edit_item = layout.itemAt(i, 1)
            if label_item:
                w = label_item.widget()
                if w:
                    layout.removeWidget(w)
                    w.deleteLater()
            if edit_item:
                w = edit_item.widget()
                if w:
                    layout.removeWidget(w)
                    w.deleteLater()

        # Clear hotkey_inputs of models
        for key in list(self.hotkey_inputs.keys()):
            if key not in ('transcribe_mode', 'command_mode'):
                self.hotkey_inputs.pop(key)

        # Add new rows for all models from settings_manager
        if self.settings_manager is not None:
            models_dict = self.settings_manager.get('models', {})
            models_hotkeys = self.settings_manager.get('models_hotkeys', {})
            models = []
            for lang_models in models_dict.values():
                for model in lang_models:
                    name = model.get('name')
                    if name:
                        models.append(name)
            if models:
                layout.addRow(QLabel(section_label_text))
            for model_name in models:
                label = model_name
                self.add_hotkey_row(model_name, label, models_hotkeys.get(model_name, ''))
