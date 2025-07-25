# ui/replacements_page.py
from PyQt5.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QTableWidgetItem, QVBoxLayout

from .table_settings import TableSettings


class ReplacementsPage(TableSettings):
    def __init__(self, texts, parent=None, settings_manager=None):
        # Define columns and settings key (translatable)
        # Always use English keys for column names (find, replace)
        columns = ["find", "replace"]
        self.texts = texts
        super().__init__(parent, settings_manager, settings_key="replaces", columns=columns)
        self.languages = self._get_installed_languages()
        self.init_ui()

    def _get_installed_languages(self):
        # Get the list of languages from settings_manager -> models
        langs = []
        if self.settings_manager is not None:
            models = self.settings_manager.get('models', {})
            langs = list(models.keys())
        return langs

    def init_ui(self):
        # texts should now be passed via self.texts (DI)
        texts = self.texts
        main_layout = QVBoxLayout(self)

        # Checkboxes for enabling/disabling replacements (in one line)
        from PyQt5.QtWidgets import QCheckBox
        checkboxes_layout = QHBoxLayout()
        self.enable_replacements_cb = QCheckBox(texts.get('replacements_enable', 'Enable word replacement'))
        self.enable_partial_replacements_cb = QCheckBox(texts.get('replacements_enable_partial', 'Enable replacement in partial'))
        # Set values from settings
        if self.settings_manager is not None:
            self.enable_replacements_cb.setChecked(self.settings_manager.get('enable_replacements', True))
            self.enable_partial_replacements_cb.setChecked(self.settings_manager.get('enable_partial_replacements', True))
        # Signals for saving on change are removed to prevent multiple saves.
        # Add checkboxes to horizontal layout
        checkboxes_layout.addWidget(self.enable_replacements_cb)
        checkboxes_layout.addWidget(self.enable_partial_replacements_cb)
        checkboxes_layout.addStretch()
        main_layout.addLayout(checkboxes_layout)

        # Language selector
        lang_layout = QHBoxLayout()
        lang_label = QLabel(texts.get('replacements_language_label', 'Replacement language:'))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(self.languages)
        # By default, select the language of the current model
        current_lang = None
        if self.settings_manager is not None:
            current_lang = self.settings_manager.get('language', None)
        if current_lang and current_lang in self.languages:
            self.lang_combo.setCurrentIndex(self.languages.index(current_lang))
        lang_layout.addWidget(lang_label)
        lang_layout.addWidget(self.lang_combo)
        lang_layout.addStretch()
        main_layout.addLayout(lang_layout)

        # Table for replacements (use base method)
        main_layout.addWidget(self.table)

        # Load replacements for the selected language on initialization
        if self.languages:
            self.load_replacements_for_lang(self.lang_combo.currentText())

        # On language change — load replacements
        self.lang_combo.currentTextChanged.connect(self.load_replacements_for_lang)

        # Buttons
        btn_layout = QHBoxLayout()
        self.add_row_btn = QPushButton(texts.get('replacements_add_rows', 'Add Rows'))
        self.clear_sel_btn = QPushButton(texts.get('replacements_clear_selection', 'Clear Selection'))
        btn_layout.addWidget(self.add_row_btn)
        btn_layout.addWidget(self.clear_sel_btn)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        # Connect buttons
        self.add_row_btn.clicked.connect(self.add_row)
        self.clear_sel_btn.clicked.connect(self.clear_selection)

        # Block of special command buttons for quick insert
        commands = [
            ('[Backspace]', texts.get('replace_cmd_backspace', 'Delete previous character')),
            ('[Enter]', texts.get('replace_cmd_enter', 'Insert line break')),
            ('[Tab]', texts.get('replace_cmd_tab', 'Insert tabulation')),
            ('[Space]', texts.get('replace_cmd_space', 'Insert space')),
        ]
        from PyQt5.QtWidgets import QSizePolicy, QToolButton
        cmd_btn_layout = QHBoxLayout()
        self.cmd_buttons = []
        for cmd, tip in commands:
            btn = QToolButton()
            btn.setText(cmd)
            btn.setToolTip(tip)
            btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            btn.clicked.connect(lambda checked, c=cmd: self.insert_command_to_replace(c))
            self.cmd_buttons.append(btn)
            cmd_btn_layout.addWidget(btn)
        # Hint button "?"
        help_btn = QToolButton()
        help_btn.setText('?')
        help_btn.setToolTip(texts.get('replace_cmd_help',
            '<b>Supported special commands for replacement:</b><br>'
            '[Backspace] — delete previous character<br>'
            '[Enter] — insert line break<br>'
            '[Tab] — insert tabulation<br>'
            '[Space] — insert space<br>'
            '<i>Use square brackets, for example: hello[Enter]world</i>'
        ))
        help_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        cmd_btn_layout.addWidget(help_btn)
        cmd_btn_layout.addStretch()
        main_layout.addLayout(cmd_btn_layout)

    def get_settings(self):
        """Get all settings from this page."""
        lang = self.lang_combo.currentText()

        # Get table values
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

        # Get all 'replaces' settings and update only the current language
        replaces_settings = self.settings_manager.get(self.settings_key, {})
        replaces_settings[lang] = table_data

        settings = {
            'enable_replacements': self.enable_replacements_cb.isChecked(),
            'enable_partial_replacements': self.enable_partial_replacements_cb.isChecked(),
            self.settings_key: replaces_settings,
        }
        return settings

    def load_replacements_for_lang(self, lang):
        # Load replacements for the selected language
        self.load_table_values(section_key=lang)

    def insert_command_to_replace(self, cmd):
        # Insert special command at cursor position in active 'replace' cell if editing, otherwise at the end
        table = self.table
        row = table.currentRow()
        col = table.currentColumn()
        if col != 1 or row < 0:
            return
        item = table.item(row, col)
        if item is None:
            item = QTableWidgetItem()
            table.setItem(row, col, item)
        # Try to get editor (QLineEdit) if cell is being edited
        editor = table.indexWidget(table.currentIndex())
        if editor is None:
            # Try via focusWidget (usually QLineEdit when editing)
            from PyQt5.QtWidgets import QApplication, QLineEdit
            fw = QApplication.focusWidget()
            if isinstance(fw, QLineEdit):
                editor = fw
        if editor is not None and hasattr(editor, 'cursorPosition'):
            # Insert at cursor position
            text = editor.text()
            pos = editor.cursorPosition()
            new_text = text[:pos] + cmd + text[pos:]
            editor.setText(new_text)
            editor.setCursorPosition(pos + len(cmd))
        else:
            # If not editing — add to the end
            text = item.text() or ''
            text = text + cmd
            item.setText(text)
        table.setCurrentCell(row, col)
        table.editItem(item)
