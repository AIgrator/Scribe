# ui/voice_hotkeys_page.py
from PyQt5.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QSpinBox, QStyledItemDelegate, QVBoxLayout

from .hotkey_line_edit import HotkeyLineEdit
from .table_settings import TableSettings


class HotkeyDelegate(QStyledItemDelegate):
    def __init__(self, parent, texts):
        super().__init__(parent)
        self.texts = texts
    def createEditor(self, parent, option, index):
        return HotkeyLineEdit(self.texts, index.model().data(index, 0), parent)
    def setEditorData(self, editor, index):
        value = index.model().data(index, 0)
        editor.set_hotkey(value)
    def setModelData(self, editor, model, index):
        model.setData(index, editor.text(), 0)

class VoiceHotkeysPage(TableSettings):
    def __init__(self, texts, parent=None, settings_manager=None):
        columns = ["hotkey", "trigger"]
        self.texts = texts
        super().__init__(parent, settings_manager, settings_key="commands_hotkey", columns=columns)
        self.languages = self._get_installed_languages()
        self.init_ui()
    def _get_installed_languages(self):
        langs = []
        if self.settings_manager is not None:
            models = self.settings_manager.get('models', {})
            langs = list(models.keys())
        return langs
    def init_ui(self):
        texts = self.texts
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(QLabel(texts.get('voice_hotkeys_title', 'Voice Hotkeys')))
        lang_layout = QHBoxLayout()
        lang_label = QLabel(texts.get('replacements_language_label', 'Replacement language:'))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(self.languages)
        current_lang = None
        if self.settings_manager is not None:
            current_lang = self.settings_manager.get('language', None)
        if current_lang and current_lang in self.languages:
            self.lang_combo.setCurrentIndex(self.languages.index(current_lang))
        lang_layout.addWidget(lang_label)
        lang_layout.addWidget(self.lang_combo)

        # Fuzzy Match Hotkey Threshold UI
        fuzzy_label = QLabel(texts['fuzzy_match_label'])
        self.fuzzy_spin = QSpinBox()
        self.fuzzy_spin.setRange(80, 100)
        self.fuzzy_spin.setSingleStep(1)
        self.fuzzy_spin.setValue(self.settings_manager.get('fuzzy_match_hotkey', 90) if self.settings_manager else 90)
        self.fuzzy_spin.setToolTip(texts['fuzzy_match_hint'])
        fuzzy_label.setToolTip(texts['fuzzy_match_hint'])
        lang_layout.addSpacing(16)
        lang_layout.addWidget(fuzzy_label)
        lang_layout.addWidget(self.fuzzy_spin)

        lang_layout.addStretch()
        main_layout.addLayout(lang_layout)
        main_layout.addWidget(self.table)
        hotkey_col = self.columns.index("hotkey")
        self.table.setItemDelegateForColumn(hotkey_col, HotkeyDelegate(self.table, texts))
        btn_layout = QHBoxLayout()
        self.add_hotkey_btn = QPushButton(texts.get('voice_hotkeys_add', 'Add Hotkey'))
        self.clear_sel_btn = QPushButton(texts.get('commands_clear_selection', 'Delete selected'))
        btn_layout.addWidget(self.add_hotkey_btn)
        btn_layout.addWidget(self.clear_sel_btn)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        # The fuzzy_spin.valueChanged connection is removed to prevent multiple saves.
        self.add_hotkey_btn.clicked.connect(self.add_hotkey_row)
        self.clear_sel_btn.clicked.connect(self.clear_selection)
        # Load data for the current language when the window opens
        self.lang_combo.currentTextChanged.connect(self._load_commands_for_lang)
        self._load_commands_for_lang(self.lang_combo.currentText())

    def get_settings(self):
        """Get all settings from this page."""
        lang = self.lang_combo.currentText()

        table_data = []
        for row in range(self.table.rowCount()):
            row_data = {}
            is_row_empty = True
            for col_idx, col_name in enumerate(self.columns):
                item = self.table.item(row, col_idx)
                value = item.text().strip() if item else ""
                row_data[col_name] = value
                if value:
                    is_row_empty = False
            if not is_row_empty:
                table_data.append(row_data)

        commands_settings = self.settings_manager.get(self.settings_key, {})
        commands_settings[lang] = table_data

        settings = {
            'fuzzy_match_hotkey': self.fuzzy_spin.value(),
            self.settings_key: commands_settings,
        }
        return settings

    def add_hotkey_row(self):
        from PyQt5.QtWidgets import QTableWidgetItem
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(""))  # hotkey
        self.table.setItem(row, 1, QTableWidgetItem(""))  # trigger
        self.table.editItem(self.table.item(row, 0))
    def _load_commands_for_lang(self, lang):
        self.load_table_values(section_key=lang)
