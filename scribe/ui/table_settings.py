# ui/table_settings.py
from PyQt5.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem, QWidget


class TableSettings(QWidget):

    def __init__(self, parent=None, settings_manager=None, settings_key=None, columns=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.settings_key = settings_key  # Key in settings.json (e.g., 'replaces')
        self.columns = columns or ["Field 1", "Field 2"]  # Headers for UI
        self.init_table()

    def init_table(self):
        self.table = QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.AllEditTriggers)

    def load_table_values(self, section_key=None):
        # section_key — for example, language ('en'), if the table is nested
        self.table.setRowCount(0)
        items = []
        if self.settings_manager is not None:
            data = self.settings_manager.get(self.settings_key, {})
            if section_key is not None:
                items = data.get(section_key, [])
            else:
                items = data
        for item in items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col in range(self.table.columnCount()):
                # Use column names as keys
                key = self.columns[col]
                value = item.get(key, '')
                table_item = QTableWidgetItem(value)
                # Set tooltip for all cells
                table_item.setToolTip(value)
                self.table.setItem(row, col, table_item)

    def save_table_values(self, section_key=None):
        # Universal saving of table values to settings_manager
        if self.settings_manager is None:
            return
        rows = self.table.rowCount()
        cols = self.table.columnCount()
        items = []
        for i in range(rows):
            item = {}
            empty = True
            for col in range(cols):
                key = self.columns[col]
                value = self.table.item(i, col).text() if self.table.item(i, col) else ''
                # Convert to lowercase for single keys in hotkey (commands_hotkey)
                if self.settings_key == 'commands_hotkey' and key == 'hotkey':
                    # If it's a single key (without +), convert to lowercase
                    if value and '+' not in value and len(value) < 20:
                        value = value.lower()
                item[key] = value
                if value:
                    empty = False
            if not empty:
                items.append(item)

        # Save only in the format: key -> {language: [items]} if section_key is set, otherwise just a list
        if section_key is not None:
            data = self.settings_manager.get(self.settings_key, {})
            data[section_key] = items
            self.settings_manager.set(self.settings_key, data)
        else:
            self.settings_manager.set(self.settings_key, items)

    def add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col in range(self.table.columnCount()):
            self.table.setItem(row, col, QTableWidgetItem(""))
        # Automatically scroll down so the new row is visible
        self.table.scrollToBottom()

    def clear_selection(self):
        for idx in sorted(set(i.row() for i in self.table.selectedIndexes()), reverse=True):
            self.table.removeRow(idx)

    def refresh_languages(self, languages, current_lang=None):
        """Updates the list of languages in the combobox (if it exists) and selects the current language.

        languages: list of languages (e.g., ["ru", "en"])
        current_lang: language to select by default (if any).
        """
        if not hasattr(self, 'lang_combo'):
            return
        self.lang_combo.clear()
        self.lang_combo.addItems(languages)
        if current_lang and current_lang in languages:
            self.lang_combo.setCurrentIndex(languages.index(current_lang))

    def showEvent(self, event):
        # Automatically update the list of languages each time the tab is shown
        if hasattr(self, 'lang_combo') and self.settings_manager is not None:
            models = self.settings_manager.get('models', {})
            langs = list(models.keys())
            current_lang = self.settings_manager.get('language', None)
            self.refresh_languages(langs, current_lang)
        super().showEvent(event)
