# ui/voice_openfile_page.py
import json
import logging
import os
import platform

from app_scanner import get_installed_apps
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from scribe.utils import get_data_dir

from .busy_dialog import BusyDialog
from .table_settings import TableSettings

logger = logging.getLogger(__name__)


class ScanWorker(QObject):
    finished = pyqtSignal(object)  # Signal to emit results or exception

    def __init__(self):
        super().__init__()

    def run(self):
        try:
            apps_data = get_installed_apps()
            self.finished.emit(apps_data)
            self.finished.emit(apps_data)
        except Exception as e:
            logger.error(f"Failed to scan for applications: {e}", exc_info=True)
            self.finished.emit(e)


class AppSelectionDialog(QDialog):
    def __init__(self, parent=None, texts=None):
        super().__init__(parent)
        self.texts = texts
        self.cache_dir = os.path.join(get_data_dir(), "cache")
        self.cache_file = os.path.join(self.cache_dir, "apps_cache.json")
        self.setWindowTitle("Select Application")
        self.setMinimumSize(450, 400)

        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        font = QFont("Segoe UI" if platform.system() == "Windows" else "Arial", 9)
        self.list_widget.setFont(font)
        self.list_widget.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self.list_widget)

        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.refresh_button = button_box.addButton(
            "Refresh List", QDialogButtonBox.ActionRole)
        self.refresh_button.clicked.connect(self.scan_and_cache_apps)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.load_apps()

    def load_apps(self):
        if os.path.exists(self.cache_file):
            self.load_from_cache()
        else:
            self.scan_and_cache_apps()

    def load_from_cache(self):
        self.list_widget.clear()
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                apps = json.load(f)

            if not apps:
                return

            for app_info in sorted(apps, key=lambda x: x.get('name', '').lower()):
                name = app_info.get("name")
                item = QListWidgetItem(name)
                # Store the entire app dictionary as a JSON string in the item's data
                item.setData(Qt.UserRole, json.dumps(app_info))
                self.list_widget.addItem(item)

        except (IOError, json.JSONDecodeError) as e:
            logging.error(f"Failed to load app cache: {e}")
            QMessageBox.critical(self, "Cache Error",
                                   f"Could not read the cache file: {e}\n\nClick 'Refresh List' to try rebuilding it.")

    def scan_and_cache_apps(self):
        self.list_widget.clear()
        self.busy_dialog = BusyDialog(self, self.texts, "Scanning for applications...")
        self.busy_dialog.open()

        self.thread = QThread()
        self.worker = ScanWorker()
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_scan_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def on_scan_finished(self, result):
        self.busy_dialog.close()

        if isinstance(result, Exception):
            logger.error(f"An error occurred during scan: {result}")
            QMessageBox.critical(self, "Error", f"An unexpected error occurred during scan: {result}")
            return

        try:
            apps_data = result
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(apps_data, f, indent=4, ensure_ascii=False)

            self.load_from_cache()
        except Exception as e:
            logging.error(f"Failed to process or cache scan results: {e}")
            QMessageBox.critical(self, "Error", f"Failed to process results: {e}")

    def selected_app(self):
        selected_item = self.list_widget.currentItem()
        if selected_item:
            app_info_str = selected_item.data(Qt.UserRole)
            return json.loads(app_info_str)
        return None


# Delegate for selecting a file in the 'path' column
class PathDelegate(QStyledItemDelegate):
    def __init__(self, parent):
        super().__init__(parent)
    def createEditor(self, parent, option, index):
        from PyQt5.QtWidgets import QMessageBox
        texts = getattr(parent.parent(), 'texts', None) or getattr(parent, 'texts', None) or {}
        container = QWidget(parent)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit(container)
        edit.setPlaceholderText(texts.get('file_path_placeholder', 'File path...'))
        btn = QPushButton('...')
        btn.setFixedWidth(28)
        btn.setSizePolicy(btn.sizePolicy().Fixed, btn.sizePolicy().Fixed)
        layout.addWidget(edit)
        layout.addWidget(btn)
        container.btn = btn
        container.edit = edit

        def choose_file():
            file_dialog_title = texts.get('file_dialog_title', 'Choose file')
            path, _ = QFileDialog.getOpenFileName(container, file_dialog_title)
            if path:
                edit.setText(path)
                btn.setToolTip(path)
                btn.setProperty('selected_path', path)
                finish_edit()
        btn.clicked.connect(choose_file)

        def finish_edit():
            path = edit.text().strip()
            if path:
                if not os.path.exists(path):
                    msg_title = texts.get('file_not_found_title', 'File not found')
                    msg_text = texts.get(
                        'file_not_found_text',
                        'File does not exist or is not accessible:\n{path}\nPlease choose an existing file.'
                    ).replace('{path}', path)
                    QMessageBox.warning(container, msg_title, msg_text)
                    return
                btn.setToolTip(path)
                btn.setProperty('selected_path', path)
            self.commitData.emit(container)
            self.closeEditor.emit(container, QStyledItemDelegate.NoHint)
        edit.editingFinished.connect(finish_edit)
        return container
    def setEditorData(self, editor, index):
        value = index.model().data(index, 0)
        if hasattr(editor, 'edit'):
            editor.edit.setText(value)
            editor.btn.setToolTip(value)
        elif isinstance(editor, QLineEdit):
            editor.setText(value)
    def setModelData(self, editor, model, index):
        path = ""
        if hasattr(editor, 'edit'):
            path = editor.edit.text().strip()
        elif isinstance(editor, QLineEdit):
            path = editor.text().strip()
        model.setData(index, path, 0)


class VoiceOpenfilePage(TableSettings):
    def __init__(self, texts, parent=None, settings_manager=None):
        columns = ["trigger", "path", "args", "app_info"]
        self.texts = texts
        super().__init__(parent, settings_manager, settings_key="commands_openfile", columns=columns)
        self.table.setColumnHidden(self.columns.index("app_info"), True)
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
        main_layout.addWidget(QLabel(texts.get('voice_openfile_title', 'Voice Program Launch')))
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

        fuzzy_label = QLabel(texts.get('fuzzy_match_label', 'Fuzzy match threshold (%)'))
        self.fuzzy_spin = QSpinBox()
        self.fuzzy_spin.setRange(80, 100)
        self.fuzzy_spin.setSingleStep(1)
        self.fuzzy_spin.setValue(self.settings_manager.get('fuzzy_match_openfile', 90) if self.settings_manager else 90)
        self.fuzzy_spin.setToolTip(texts.get('fuzzy_match_hint', 'Range: 80–100. Higher is stricter. Default is 90.'))
        fuzzy_label.setToolTip(texts.get('fuzzy_match_hint', 'Range: 80–100. Higher is stricter. Default is 90.'))
        lang_layout.addSpacing(16)
        lang_layout.addWidget(fuzzy_label)
        lang_layout.addWidget(self.fuzzy_spin)
        lang_layout.addStretch()
        main_layout.addLayout(lang_layout)
        main_layout.addWidget(self.table)

        path_col = self.columns.index("path")
        self.table.setItemDelegateForColumn(path_col, PathDelegate(self.table))

        btn_layout = QHBoxLayout()
        self.add_manual_btn = QPushButton(texts.get('voice_openfile_add', 'Add Manually'))
        self.add_app_btn = QPushButton(texts.get('voice_openfile_add_uwp', 'Select Program'))
        self.clear_sel_btn = QPushButton(texts.get('commands_clear_selection', 'Delete selected'))
        btn_layout.addWidget(self.add_manual_btn)
        btn_layout.addWidget(self.add_app_btn)
        btn_layout.addWidget(self.clear_sel_btn)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        self.add_manual_btn.clicked.connect(self.add_manual_row)
        self.add_app_btn.clicked.connect(self.open_app_selection_dialog)
        self.clear_sel_btn.clicked.connect(self.clear_selection)

        self.lang_combo.currentTextChanged.connect(self._load_commands_for_lang)
        self._load_commands_for_lang(self.lang_combo.currentText())

    def open_app_selection_dialog(self):
        dialog = AppSelectionDialog(self, texts=self.texts)
        if dialog.exec_() == QDialog.Accepted:
            app_info = dialog.selected_app()
            if app_info:
                self.add_app_row(app_info)

    def add_app_row(self, app_info):
        from PyQt5.QtWidgets import QTableWidgetItem
        row = self.table.rowCount()
        self.table.insertRow(row)

        name = app_info.get("name", "Unknown")
        path = app_info.get("path", "")
        display_path = name if platform.system() == "Windows" and "appid" in app_info else path
        app_info_str = json.dumps(app_info)

        trigger_item = QTableWidgetItem(name)
        path_item = QTableWidgetItem(display_path)
        path_item.setFlags(path_item.flags() & ~Qt.ItemIsEditable) # Path is read-only for scanned apps
        args_item = QTableWidgetItem("")
        app_info_item = QTableWidgetItem(app_info_str)

        self.table.setItem(row, self.columns.index("trigger"), trigger_item)
        self.table.setItem(row, self.columns.index("path"), path_item)
        self.table.setItem(row, self.columns.index("args"), args_item)
        self.table.setItem(row, self.columns.index("app_info"), app_info_item)

        self.table.editItem(trigger_item)

    def add_manual_row(self):
        from PyQt5.QtWidgets import QTableWidgetItem
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, self.columns.index("trigger"), QTableWidgetItem(""))
        self.table.setItem(row, self.columns.index("path"), QTableWidgetItem(""))
        self.table.setItem(row, self.columns.index("args"), QTableWidgetItem(""))
        self.table.setItem(row, self.columns.index("app_info"), QTableWidgetItem(""))
        self.table.editItem(self.table.item(row, self.columns.index("path")))

    def _load_commands_for_lang(self, lang):
        self.load_table_values(section_key=lang)
        app_info_col = self.columns.index("app_info")
        path_col = self.columns.index("path")

        for row in range(self.table.rowCount()):
            path_item = self.table.item(row, path_col)
            if path_item:
                path_item.setToolTip(path_item.text())

            app_info_item = self.table.item(row, app_info_col)
            if app_info_item and app_info_item.text():
                if path_item:
                    path_item.setFlags(path_item.flags() & ~Qt.ItemIsEditable)

    def get_settings(self):
        lang = self.lang_combo.currentText()
        table_data = []
        for row in range(self.table.rowCount()):
            row_data = {}
            is_row_empty = True
            for col_idx, col_name in enumerate(self.columns):
                item = self.table.item(row, col_idx)
                value = item.text().strip() if item else ""
                row_data[col_name] = value
                if value and col_name != "app_info":
                    is_row_empty = False
            if not is_row_empty:
                table_data.append(row_data)

        commands_settings = self.settings_manager.get(self.settings_key, {})
        commands_settings[lang] = table_data

        return {
            'fuzzy_match_openfile': self.fuzzy_spin.value(),
            self.settings_key: commands_settings,
        }
