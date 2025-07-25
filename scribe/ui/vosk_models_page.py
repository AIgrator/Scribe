# ui/vosk_models_page.py

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAbstractItemView, QHBoxLayout, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from scribe.model_manager import LanguageSelectDialog, ModelDownloadDialog, ModelManager
from scribe.utils import get_models_path


class VoskModelsPageWidget(QWidget):
    def __init__(self, settings_manager, texts, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.texts = texts
        self.model_manager = ModelManager(get_models_path())
        self.models_dict = self.settings_manager.get('models', {})
        self.layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.NoContextMenu)
        self.table.setDragDropOverwriteMode(False)
        self.table.setDragDropMode(QAbstractItemView.NoDragDrop)
        self.table.setDefaultDropAction(Qt.IgnoreAction)
        self.table.setDropIndicatorShown(False)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.layout.addWidget(self.table)
        btn_hbox = QHBoxLayout()
        self.delete_button = QPushButton(self.texts.get('vosk_models_delete', 'Delete selected model'))
        self.delete_button.clicked.connect(self.delete_selected_model)
        self.delete_button.setEnabled(False)
        btn_hbox.addWidget(self.delete_button)
        self.download_button = QPushButton(self.texts.get('vosk_models_download', 'Download new models'))
        self.download_button.clicked.connect(self.open_download_dialog)
        btn_hbox.addWidget(self.download_button)
        self.layout.addLayout(btn_hbox)
        # "Set as current" button
        self.set_current_button = QPushButton(self.texts.get('vosk_models_set_current', 'Set selected model as current'))
        self.set_current_button.clicked.connect(self.set_selected_as_current)
        self.set_current_button.setEnabled(False)
        self.layout.addWidget(self.set_current_button)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        # Initialize table on first open
        self.update_table()

        # Subscribe to settings changes to update the table highlighting
        self.settings_manager.settings_changed.connect(self._on_settings_changed)

        # Update model hotkeys on the hotkeys page if the settings window is open
        parent = self.parent()
        # Search for SettingsWindow in parents
        while parent is not None:
            if hasattr(parent, 'hotkeys_page'):
                if hasattr(parent.hotkeys_page, 'update_hotkeys'):
                    parent.hotkeys_page.update_hotkeys()
                break
            parent = parent.parent() if hasattr(parent, 'parent') else None

    def _on_settings_changed(self, new_settings):
        """Called when settings are changed from anywhere in the application. Updates the table to reflect the current model."""
        self.update_table()
    def set_selected_as_current(self):
        row = self.table.currentRow()
        if row < 0:
            return
        all_models = self._get_all_models()
        if not all_models or row >= len(all_models):
            return
        model = all_models[row]
        model_name = model.get('name')
        model_lang = model.get('language')
        # Just update settings, model loading will happen in the controller
        self.settings_manager.set('current_model', model_name)
        self.settings_manager.set('language', model_lang)
        self.update_table()


    def open_download_dialog(self):
        # Get the list of models from github (or locally if offline)
        try:
            models_json = self.model_manager.fetch_models_json()
        except Exception:
            QMessageBox.warning(self, self.texts.get('vosk_models_download_error_title', 'Download error'),
                                self.texts.get('vosk_models_download_error_msg', 'Failed to get the list of models.'))
            return
        # Get the list of languages
        languages = self.model_manager.get_languages(models_json)
        # Language selection dialog
        system_lang = self.model_manager.get_system_language()
        lang_dialog = LanguageSelectDialog(languages, self.texts, self, system_lang=system_lang)
        if not lang_dialog.exec_():
            return
        selected_lang = lang_dialog.get_selected_language()
        if not selected_lang:
            return
        # Model selection and download dialog
        lang_models = self.model_manager.get_models_for_language(models_json, selected_lang)
        models_dir = self.model_manager.models_dir
        dlg = ModelDownloadDialog(models_json, lang_models, models_dir, self.texts, settings_manager=self.settings_manager, parent=self)
        if dlg.exec_():
            # After successful download — update the list of models
            self.models_dict = self.settings_manager.get('models', {})
            self.update_table()

    def update_table(self):
        # Ensure models_dict is a dictionary
        self.models_dict = self.settings_manager.get('models', {})
        if not isinstance(self.models_dict, dict):
            self.models_dict = {}
        all_models = self._get_all_models()
        current_model = self.settings_manager.get('current_model', None)
        self.table.clear()
        # Determine fields for the table (at least name/language)
        default_fields = ['name', 'language']
        fields = list(all_models[0].keys()) if all_models else default_fields
        self.table.setColumnCount(len(fields))
        self.table.setHorizontalHeaderLabels([self.texts.get(f'vosk_models_{f}', f) for f in fields])
        if not all_models:
            # Show one row "No models"
            self.table.setRowCount(1)
            for col, _field in enumerate(fields):
                if col == 0:
                    item = QTableWidgetItem(self.texts.get('vosk_models_no_models', 'No models'))
                    item.setFlags(Qt.ItemIsEnabled)  # View only
                else:
                    item = QTableWidgetItem("")
                    item.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(0, col, item)
            self.delete_button.setEnabled(False)
            self.set_current_button.setEnabled(False)
            return
        self.table.setRowCount(len(all_models))
        highlight_row = -1
        for row, model in enumerate(all_models):
            is_current = (model.get('name') == current_model)
            for col, _field in enumerate(fields):
                value = str(model.get(_field, ''))
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                # Всегда только просмотр, без редактирования
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                if is_current:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setToolTip(value + f"\n{self.texts.get('vosk_models_current_hint', 'Current model')}")
                self.table.setItem(row, col, item)
            if is_current:
                highlight_row = row
        self.table.setMouseTracking(True)
        name_col = fields.index('name') if 'name' in fields else 0
        self.table.resizeColumnsToContents()
        for col in range(self.table.columnCount()):
            if col != name_col:
                self.table.setColumnWidth(col, 120)
        self.delete_button.setEnabled(False)
        # Do not select the current model row so it cannot be selected
        # The "Set as current" button is active only if a non-current model is selected
        selected = self.table.currentRow()
        self.set_current_button.setEnabled(selected >= 0 and (highlight_row != selected))

    def _get_all_models(self):
        # Collect all models from self.models_dict for all languages
        all_models = []
        for lang_models in self.models_dict.values():
            all_models.extend(lang_models)
        return all_models

    def on_selection_changed(self):
        selected = self.table.selectedItems()
        row = self.table.currentRow()
        all_models = self._get_all_models()
        current_model = self.settings_manager.get('current_model', None)
        enable_delete = False
        enable_set = False
        if selected and row >= 0 and row < len(all_models):
            model_name = all_models[row].get('name')
            if model_name != current_model:
                enable_delete = True
                enable_set = True
        self.delete_button.setEnabled(enable_delete)
        self.set_current_button.setEnabled(enable_set)

    def delete_selected_model(self):
        row = self.table.currentRow()
        if row < 0:
            return
        all_models = self._get_all_models()
        if not all_models or row >= len(all_models):
            return
        model = all_models[row]
        model_name = model.get('name')
        lang = model.get('language')
        # Delete from disk with error handling
        models_dir = get_models_path()
        error = None
        try:
            ModelManager.delete_model_folder(models_dir, lang, model_name)
        except Exception as e:
            error = str(e)
        # Remove from settings
        models = self.models_dict.get(lang, [])
        models = [m for m in models if m.get('name') != model_name]
        if models:
            self.models_dict[lang] = models
        else:
            self.models_dict.pop(lang, None)
        self.settings_manager.set('models', self.models_dict)

        # Remove hotkey for this model from models_hotkeys
        models_hotkeys = self.settings_manager.get('models_hotkeys', {})
        if model_name in models_hotkeys:
            models_hotkeys.pop(model_name)
            self.settings_manager.set('models_hotkeys', models_hotkeys)
        # If the deleted model was selected as current_model — remove it from settings
        current_model = self.settings_manager.get('current_model', None)
        if current_model == model_name:
            self.settings_manager.set('current_model', None)
        self.update_table()
        # Error message if failed to delete from disk
        if error:
            QMessageBox.warning(self, self.texts.get('vosk_models_delete_error_title', 'Delete error'),
                                self.texts.get('vosk_models_delete_error_msg', 'Failed to delete model folder from disk:') + f"\n{error}")

