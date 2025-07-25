# ui/voice_openfile_page.py
import json
import logging
import os
import subprocess
import sys

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

from .busy_dialog import BusyDialog
from .table_settings import TableSettings


class ScanWorker(QObject):
    finished = pyqtSignal(object)  # Signal to emit results or exception

    def __init__(self, command):
        super().__init__()
        self.command = command

    def run(self):
        try:
            if not self.command:
                raise RuntimeError("UWP scan is only supported on Windows.")

            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            process = subprocess.Popen(
                ['powershell', '-ExecutionPolicy', 'Bypass', '-Command', self.command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            stdout_bytes, stderr_bytes = process.communicate()

            stdout = stdout_bytes.decode('utf-8', errors='ignore')
            stderr = stderr_bytes.decode('utf-8', errors='ignore')

            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, self.command, output=stdout, stderr=stderr)

            if not stdout or not stdout.strip():
                apps_data = []
            else:
                import base64
                apps_data = []
                lines = stdout.strip().splitlines()
                for line in lines:
                    if not line.strip():
                        continue
                    parts = line.strip().split('\t', 1)
                    if len(parts) == 2:
                        try:
                            name_b64, appid_b64 = parts
                            name = base64.b64decode(name_b64).decode('utf-8')
                            appid = base64.b64decode(appid_b64).decode('utf-8')
                            apps_data.append({"name": name, "appid": appid})
                        except (base64.B64DecodeError, UnicodeDecodeError) as e:
                            logging.warning(f"Skipping malformed Base64 line from PowerShell: {line}. Error: {e}")

            self.finished.emit(apps_data)

        except Exception as e:
            self.finished.emit(e)


class UWPAppDialog(QDialog):
    CACHE_DIR = "cache"
    CACHE_FILE = os.path.join(CACHE_DIR, "uwp_apps_cache.json")

    def __init__(self, parent=None, texts=None):
        super().__init__(parent)
        self.texts = texts
        self.setWindowTitle("Select Application")
        self.setMinimumSize(450, 400)

        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        # Set a font known to have good Unicode support on Windows
        font = QFont("Segoe UI", 9)
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
        if os.path.exists(self.CACHE_FILE):
            self.load_from_cache()
        else:
            self.scan_and_cache_apps()

    def load_from_cache(self):
        self.list_widget.clear()
        try:
            with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                apps = json.load(f)

            if not apps:
                return  # No warning, just show an empty list

            for app_info in apps:
                name = app_info.get("name")
                appid = app_info.get("appid")
                logging.debug(f"Adding to UWP list: Name='{name}'")
                item = QListWidgetItem(name)  # No icon
                item.setData(Qt.UserRole, appid)
                self.list_widget.addItem(item)

        except (IOError, json.JSONDecodeError) as e:
            logging.error(f"Failed to load UWP app cache: {e}")
            # If cache is corrupted, allow user to rescan
            QMessageBox.critical(self, "Cache Error",
                                   f"Could not read the cache file: {e}\n\nClick 'Refresh List' to try rebuilding it.")

    def scan_and_cache_apps(self):
        self.list_widget.clear()
        self.busy_dialog = BusyDialog(self, self.texts, "Scanning for applications...")
        self.busy_dialog.open()  # Use open() for non-blocking display

        command = ""
        if sys.platform == 'win32':
            win_ver = sys.getwindowsversion()
            if win_ver.major == 6 and win_ver.minor == 2:
                logging.info("Running on Windows 8.0, using Get-AppxPackage.")
                command = """
                    Get-AppxPackage | ForEach-Object {
                        $name = $_.Name;
                        if ($_.InstallLocation -and (Get-AppxPackageManifest $_).Package.Applications.Application.Id) {
                            $appId = ($_.PackageFamilyName + "!" + (Get-AppxPackageManifest $_).Package.Applications.Application.Id);
                            $nameBase64 = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($name));
                            $idBase64 = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($appId));
                            Write-Output "$($nameBase64)`t$($idBase64)";
                        }
                    }
                """
            else:
                logging.info("Running on Windows 8.1 or newer, using Get-StartApps.")
                command = """
                    Get-StartApps | ForEach-Object {
                        $name = $_.Name -replace "`t", " ";
                        $id = $_.AppID;
                        if ($name -and $id) {
                            $nameBase64 = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($name));
                            $idBase64 = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($id));
                            Write-Output "$($nameBase64)`t$($idBase64)"
                        }
                    }
                """

        if not command:
            logging.warning("UWP scan is only supported on Windows.")
            QMessageBox.warning(self, "Unsupported OS", "Application scanning is only available on Windows.")
            self.busy_dialog.close()
            return

        self.thread = QThread()
        self.worker = ScanWorker(command)
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
            logging.error(f"An error occurred during scan: {result}")
            if isinstance(result, FileNotFoundError):
                 QMessageBox.critical(self, "Error", "PowerShell not found.")
            elif isinstance(result, subprocess.CalledProcessError):
                 QMessageBox.critical(self, "PowerShell Error", f"The scanning script failed to run.\n\nError: {result.stderr}")
            else:
                 QMessageBox.critical(self, "Error", f"An unexpected error occurred: {result}")
            return

        try:
            apps_data = result
            os.makedirs(self.CACHE_DIR, exist_ok=True)
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(apps_data, f, indent=4, ensure_ascii=False)

            self.load_from_cache()
        except Exception as e:
            logging.error(f"Failed to process or cache scan results: {e}")
            QMessageBox.critical(self, "Error", f"Failed to process results: {e}")

    def selected_app(self):
        selected_item = self.list_widget.currentItem()
        if selected_item:
            name = selected_item.text()
            appid = selected_item.data(Qt.UserRole)
            return name, appid
        return None, None


# Delegate for selecting a file in the 'path' column
class PathDelegate(QStyledItemDelegate):
    def __init__(self, parent):
        super().__init__(parent)
    def createEditor(self, parent, option, index):
        import os

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
                finish_edit()  # Immediately finish editing and save
        btn.clicked.connect(choose_file)

        def finish_edit():
            path = edit.text().strip()
            if path:
                if not os.path.isfile(path):
                    msg_title = texts.get('file_not_found_title', 'File not found')
                    msg_text = texts.get(
                        'file_not_found_text',
                        'File does not exist or is not accessible:\n{path}\nPlease choose an existing file.'
                    ).replace('{path}', path)
                    QMessageBox.warning(
                        container,
                        msg_title,
                        msg_text
                    )
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
        elif hasattr(editor, 'btn'):
            editor.btn.setText(value)
            editor.btn.setToolTip(value)
        elif isinstance(editor, QLineEdit):
            editor.setText(value)
    def setModelData(self, editor, model, index):
        if hasattr(editor, 'edit'):
            path = editor.edit.text().strip()
            model.setData(index, path, 0)
        elif hasattr(editor, 'btn'):
            path = editor.btn.property('selected_path')
            if path:
                model.setData(index, path, 0)
            else:
                btn_text = editor.btn.text()
                if btn_text:
                    model.setData(index, btn_text, 0)
        elif isinstance(editor, QLineEdit):
            model.setData(index, editor.text(), 0)

# Delegate for arguments
class ArgsDelegate(QStyledItemDelegate):
    def __init__(self, parent):
        super().__init__(parent)
    def createEditor(self, parent, option, index):
        return QLineEdit(parent)
    def setEditorData(self, editor, index):
        value = index.model().data(index, 0)
        editor.setText(value)
    def setModelData(self, editor, model, index):
        model.setData(index, editor.text(), 0)

class VoiceOpenfilePage(TableSettings):
    def __init__(self, texts, parent=None, settings_manager=None):
        columns = ["path", "args", "trigger", "is_uwp"]
        self.texts = texts
        super().__init__(parent, settings_manager, settings_key="commands_openfile", columns=columns)
        self.table.setColumnHidden(self.columns.index("is_uwp"), True)
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

        # Fuzzy Match Openfile Threshold UI
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
        args_col = self.columns.index("args")
        self.table.setItemDelegateForColumn(path_col, PathDelegate(self.table))
        self.table.setItemDelegateForColumn(args_col, ArgsDelegate(self.table))

        btn_layout = QHBoxLayout()
        self.add_openfile_btn = QPushButton(texts.get('voice_openfile_add', 'Add Launch'))
        self.add_uwp_app_btn = QPushButton(texts.get('voice_openfile_add_uwp', 'Select Program'))
        self.clear_sel_btn = QPushButton(texts.get('commands_clear_selection', 'Delete selected'))
        btn_layout.addWidget(self.add_openfile_btn)
        btn_layout.addWidget(self.add_uwp_app_btn)
        btn_layout.addWidget(self.clear_sel_btn)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        # Check for Windows 8.0
        is_win8_or_later = False
        if sys.platform == 'win32':
            win_ver = sys.getwindowsversion()
            # Windows 8.0 is version 6.2. Windows 10 is 10.0.
            if win_ver.major > 6 or (win_ver.major == 6 and win_ver.minor >= 2):
                is_win8_or_later = True

        if not is_win8_or_later:
            self.add_uwp_app_btn.hide()

        self.add_openfile_btn.clicked.connect(self.add_openfile_row)
        self.add_uwp_app_btn.clicked.connect(self.open_uwp_app_dialog)
        self.clear_sel_btn.clicked.connect(self.clear_selection)

        self.lang_combo.currentTextChanged.connect(self._load_commands_for_lang)
        self._load_commands_for_lang(self.lang_combo.currentText())

    def open_uwp_app_dialog(self):
        dialog = UWPAppDialog(self, texts=self.texts)
        if dialog.exec_() == QDialog.Accepted:
            name, appid = dialog.selected_app()
            if name and appid:
                self.add_uwp_app_row(name, appid)

    def add_uwp_app_row(self, name, appid):
        from PyQt5.QtWidgets import QTableWidgetItem
        row = self.table.rowCount()
        self.table.insertRow(row)

        path_item = QTableWidgetItem("explorer.exe")
        path_item.setFlags(path_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, self.columns.index("path"), path_item)

        # The appid from Get-StartApps is the complete identifier.
        # We just need to prefix it with the shell command.
        args_text = rf"shell:Appsfolder\{appid}"

        args_item = QTableWidgetItem(args_text)
        args_item.setFlags(args_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, self.columns.index("args"), args_item)

        self.table.setItem(
            row, self.columns.index("trigger"), QTableWidgetItem(name))

        is_uwp_item = QTableWidgetItem("true")
        is_uwp_item.setFlags(is_uwp_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, self.columns.index("is_uwp"), is_uwp_item)

        self.table.editItem(
            self.table.item(row, self.columns.index("trigger")))

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
            'fuzzy_match_openfile': self.fuzzy_spin.value(),
            self.settings_key: commands_settings,
        }
        return settings

    def add_openfile_row(self):
        from PyQt5.QtWidgets import QTableWidgetItem
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(""))  # path
        self.table.setItem(row, 1, QTableWidgetItem(""))  # args
        self.table.setItem(row, 2, QTableWidgetItem(""))  # trigger
        self.table.setItem(row, 3, QTableWidgetItem("false")) # is_uwp
        self.table.editItem(self.table.item(row, 0))

    def _load_commands_for_lang(self, lang):
        self.load_table_values(section_key=lang)
        path_col = self.columns.index("path")
        args_col = self.columns.index("args")
        is_uwp_col = self.columns.index("is_uwp")

        for row in range(self.table.rowCount()):
            # Set tooltip for path
            path_item = self.table.item(row, path_col)
            if path_item:
                path_item.setToolTip(path_item.text())

            # Check if it's a UWP app and disable editing
            is_uwp_item = self.table.item(row, is_uwp_col)
            if is_uwp_item and is_uwp_item.text() == "true":
                if path_item:
                    path_item.setFlags(path_item.flags() & ~Qt.ItemIsEditable)
                args_item = self.table.item(row, args_col)
                if args_item:
                    args_item.setFlags(args_item.flags() & ~Qt.ItemIsEditable)
