# model_manager.py
import locale
import os
import zipfile

import requests
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QCheckBox, QDialog, QHBoxLayout, QLabel, QListWidget, QMessageBox, QProgressBar, QPushButton, QVBoxLayout, QWidget

from scribe.utils import resource_path

VOSK_MODELS_JSON_URL = "https://raw.githubusercontent.com/AIgrator/VoskModels/refs/heads/main/vosk_models.json"

class ExtractThread(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, zip_path, extract_to):
        super().__init__()
        self.zip_path = zip_path
        self.extract_to = extract_to

    def run(self):
        try:
            if not os.path.exists(self.extract_to):
                os.makedirs(self.extract_to)
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.extract_to)
            self.finished.emit(self.zip_path)
        except Exception as e:
            self.error.emit(str(e))

class DownloadThread(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url, dest_path):
        super().__init__()
        self.url = url
        self.dest_path = dest_path

    def run(self):
        try:
            with requests.get(self.url, stream=True) as response:
                response.raise_for_status()  # выбросит исключение при ошибке (4xx/5xx)

                total = int(response.headers.get('Content-Length', 0))
                downloaded = 0

                with open(self.dest_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total:
                                percent = int(downloaded * 100 / total)
                                self.progress.emit(percent)

            self.finished.emit(self.dest_path)

        except Exception as e:
            self.error.emit(str(e))


class ModelManager:
    def __init__(self, models_dir):
        self.models_dir = models_dir
        if not os.path.exists(self.models_dir):
            os.makedirs(self.models_dir)

    def has_models(self):
        # Check for at least one model (presence of am/final.mdl in subfolders)
        for root, dirs, _files in os.walk(self.models_dir):
            if 'am' in dirs:
                if os.path.exists(os.path.join(root, 'am', 'final.mdl')):
                    return True
        return False

    def get_system_language(self):
        lang, _ = locale.getdefaultlocale()
        if lang:
            return lang.split('_')[0]
        return 'en'

    def fetch_models_json(self):
        response = requests.get(VOSK_MODELS_JSON_URL)
        response.raise_for_status()
        return response.json()

    def get_languages(self, models_json):
        # Collect unique (code, title) pairs for languages, excluding 'unknown'
        lang_map = {}
        for m in models_json:
            code = m.get('language')
            title = m.get('title') or code
            if code != "unknown" and code not in lang_map:
                lang_map[code] = title
        # Return a list of tuples (code, title)
        return sorted(lang_map.items(), key=lambda x: x[1].lower())

    def get_models_for_language(self, models_json, lang):
        # Exclude 'unknown'
        return [m for m in models_json if m['language'] == lang and m['language'] != "unknown"]

    def ensure_language_folder(self, lang):
        lang_dir = os.path.join(self.models_dir, lang)
        if not os.path.exists(lang_dir):
            os.makedirs(lang_dir)
        return lang_dir

    @staticmethod
    def extract_zip(zip_path, extract_to):
        # Explicitly create the folder for extraction if it doesn't exist
        if not os.path.exists(extract_to):
            os.makedirs(extract_to)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)

    @staticmethod
    def delete_model_folder(models_dir, lang, model_name):
        """Deletes the model folder by language and model name (only the model folder, not the language folder)."""
        model_path = os.path.join(models_dir, lang, model_name)
        if os.path.exists(model_path) and os.path.isdir(model_path):
            import shutil
            shutil.rmtree(model_path)

class ModelDownloadDialog(QDialog):
    def __init__(self, models_json, lang_models, models_dir, texts, settings_manager=None, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QIcon(resource_path('resources/icon.ico')))
        self.texts = texts
        self.setWindowTitle(self.texts['download_model_title'])
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self.selected_model = None
        self.models_json = models_json
        self.lang_models = lang_models
        self.models_dir = models_dir
        self.settings_manager = settings_manager
        self.layout = QVBoxLayout(self)
        self.label = QLabel(self.texts['download_model_label'])
        self.layout.addWidget(self.label)
        self.list_widget = QListWidget()
        self.layout.addWidget(self.list_widget)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.layout.addWidget(self.progress)
        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        self.layout.addWidget(self.status_label)

        # License agreement checkbox and label with link
        self.license_row = QWidget()
        self.license_row_layout = QHBoxLayout(self.license_row)
        self.license_row_layout.setContentsMargins(0, 0, 0, 0)
        self.license_checkbox = QCheckBox()
        self.license_checkbox.setChecked(False)
        self.license_checkbox.setVisible(False)
        self.license_checkbox.setEnabled(False)
        # Add checkbox and link in one row without extra spacing
        self.license_row_layout.addWidget(self.license_checkbox, 0)
        self.license_label = QLabel()
        self.license_label.setOpenExternalLinks(True)
        self.license_label.setVisible(False)
        self.license_row_layout.addWidget(self.license_label, 0)
        self.license_row_layout.setSpacing(0)
        self.layout.addWidget(self.license_row)
        self.license_checkbox.stateChanged.connect(self.on_selection)

        self.download_button = QPushButton(self.texts['download_model_button'])
        self.download_button.setEnabled(False)
        self.layout.addWidget(self.download_button)
        self.ok_button = QPushButton(self.texts['download_model_done'])
        self.ok_button.setVisible(False)
        self.ok_button.clicked.connect(self.accept)
        self.layout.addWidget(self.ok_button)
        self.list_widget.itemSelectionChanged.connect(self.on_selection)
        self.download_button.clicked.connect(self.start_download)
        self.list_widget.itemDoubleClicked.connect(self.start_download)
        self.populate_models()

    def populate_models(self):
        self.list_widget.clear()
        for m in self.lang_models:
            self.list_widget.addItem(f"{m['name']} ({m['size']}) - {m.get('notes','')}")
        # After filling the list, explicitly reset the selection and update the display
        self.list_widget.setCurrentRow(-1)
        self.on_selection()

    def on_selection(self):
        idx = self.list_widget.currentRow()
        has_selection = idx >= 0
        # The checkbox and label must be visible and accessible after selecting a model
        self.license_checkbox.setEnabled(has_selection)
        self.license_label.setEnabled(has_selection)
        self.license_row.setVisible(has_selection)
        if not has_selection:
            self.license_checkbox.setChecked(False)
        # The button is enabled only if an item is selected and the checkbox is checked
        enable = has_selection and self.license_checkbox.isChecked()
        self.download_button.setEnabled(enable)
        # Update license text and link
        self.update_license_checkbox()

    def update_license_checkbox(self):
        idx = self.list_widget.currentRow()
        if idx >= 0:
            model = self.lang_models[idx]
            license_name = model.get('license', '')
            license_url = self.get_license_url(license_name)
            if license_url:
                # Show both checkbox and link, checkbox text before the link
                self.license_checkbox.setText(self.texts['license_agree'])
                self.license_checkbox.setVisible(True)
                self.license_checkbox.setEnabled(True)
                self.license_label.setText(f'<a href="{license_url}">{license_name}</a>')
                self.license_label.setVisible(True)
                self.license_label.setOpenExternalLinks(True)
            else:
                self.license_checkbox.setText(self.texts['license_agree_with'].format(license_name))
                self.license_checkbox.setVisible(True)
                self.license_checkbox.setEnabled(True)
                self.license_label.setText("")
                self.license_label.setVisible(False)
        else:
            self.license_checkbox.setText(self.texts['license_agree'])
            self.license_checkbox.setVisible(False)
            self.license_checkbox.setEnabled(False)
            self.license_label.setText("")
            self.license_label.setVisible(False)

    def get_license_url(self, license_name):
        # Extended list of licenses and their links
        license_links = {
            "Apache 2.0": "https://www.apache.org/licenses/LICENSE-2.0",
            "MIT": "https://opensource.org/licenses/MIT",
            "MIT license": "https://opensource.org/licenses/MIT",
            "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/",
            "CC-BY-NC-SA 4.0": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
            "CC-BY-NC-SA": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
            "GPL v3": "https://www.gnu.org/licenses/gpl-3.0.html",
            "GPLv3.0": "https://www.gnu.org/licenses/gpl-3.0.html",
            "LGPL-3.0": "https://www.gnu.org/licenses/lgpl-3.0.html",
            "AGPL": "https://www.gnu.org/licenses/agpl-3.0.html",
            "AGPL-3.0": "https://www.gnu.org/licenses/agpl-3.0.html",
        }
        return license_links.get(license_name)

    def get_selected_model(self):
        idx = self.list_widget.currentRow()
        if idx >= 0:
            return self.lang_models[idx]
        return None

    def start_download(self):
        # Do not start downloading if the checkbox is not checked
        if not self.license_checkbox.isChecked():
            QMessageBox.warning(self, self.texts['license_warning_title'], self.texts['license_warning_text'])
            return
        self.download_button.setEnabled(False)
        self.list_widget.setEnabled(False)
        self.license_checkbox.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.status_label.setText(self.texts['download_model_status_downloading'])
        self.status_label.setVisible(True)
        model = self.get_selected_model()
        if not model:
            self.status_label.setText(self.texts['download_model_status_no_model'])
            return
        download_url = model['download_url']
        zip_name = os.path.basename(download_url)
        lang = model['language']
        lang_dir = os.path.join(self.models_dir, lang)
        if not os.path.exists(lang_dir):
            os.makedirs(lang_dir)
        zip_path = os.path.join(lang_dir, zip_name)
        self._downloaded_model_info = model  # Save info about the model being downloaded
        from .model_manager import DownloadThread
        self.thread = DownloadThread(download_url, zip_path)
        self.thread.progress.connect(self.progress.setValue)
        self.thread.finished.connect(lambda path: self.on_download_finished(path, lang_dir, lang))
        self.thread.error.connect(self.on_download_error)
        self.thread.start()

    def on_download_finished(self, zip_path, lang_dir, lang):
        import time
        self.status_label.setText(self.texts['download_model_status_extracting'] + f"\n{zip_path}")
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        # Check for archive existence, wait if needed
        attempts = 0
        while not os.path.exists(zip_path) and attempts < 10:
            time.sleep(0.2)
            attempts += 1
        if not os.path.exists(zip_path):
            self.status_label.setText(self.texts['download_model_status_no_archive'] + f"\n{zip_path}")
            self.progress.setVisible(False)
            self.ok_button.setVisible(True)
            return
        self.status_label.setText(self.texts['download_model_status_extracting'])
        self.status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # Start extraction in a separate thread
        from .model_manager import ExtractThread
        self.extract_thread = ExtractThread(zip_path, lang_dir)
        self.extract_thread.finished.connect(lambda path: self.on_extract_finished(path, lang_dir, lang))
        self.extract_thread.error.connect(self.on_extract_error)
        self.extract_thread.start()

    def on_extract_finished(self, zip_path, lang_dir, lang):
        import os
        try:
            os.remove(zip_path)
        except Exception:
            pass
        # Save info about the downloaded model in settings_manager
        if self.settings_manager is not None and hasattr(self, '_downloaded_model_info'):
            models_dict = self.settings_manager.get('models', {})
            lang_models = models_dict.get(lang, [])
            exists = any(m.get('name') == self._downloaded_model_info.get('name') for m in lang_models)
            if not exists:
                model_info = {k: v for k, v in self._downloaded_model_info.items() if k != 'download_url'}
                lang_models.append(model_info)
                models_dict[lang] = lang_models
                self.settings_manager.set('models', models_dict)

                models_hotkeys = self.settings_manager.get('models_hotkeys', {})
                model_name = model_info.get('name')
                if model_name and model_name not in models_hotkeys:
                    used_numbers = set()
                    for hotkey in models_hotkeys.values():
                        if hotkey.startswith("Ctrl+Alt+"):
                            try:
                                n = int(hotkey.split("Ctrl+Alt+")[-1])
                                if 1 <= n <= 9:
                                    used_numbers.add(n)
                            except Exception:
                                pass
                    n = None
                    for i in range(1, 10):
                        if i not in used_numbers:
                            n = i
                            break
                    if n is not None:
                        hotkey = f"Ctrl+Alt+{n}"
                        models_hotkeys[model_name] = hotkey
                        self.settings_manager.set('models_hotkeys', models_hotkeys)

        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.status_label.setText(self.texts['download_model_status_done'])
        self.status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.accept()

    def on_extract_error(self, msg):
        self.status_label.setText(self.texts['download_model_status_extract_error'] + f" {msg}")
        self.status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.progress.setVisible(False)
        self.ok_button.setVisible(True)

    def on_download_error(self, msg):
        self.status_label.setText(self.texts['download_model_status_error'] + f" {msg}")
        self.progress.setVisible(False)
        self.ok_button.setVisible(True)

class LanguageSelectDialog(QDialog):
    def __init__(self, languages, texts, parent=None, system_lang=None):
        super().__init__(parent)
        self.setWindowIcon(QIcon(resource_path('resources/icon.ico')))
        self.texts = texts
        self.setWindowTitle(self.texts['select_language_title'])
        self.setMinimumWidth(int(450))
        self.setMinimumHeight(int(300))
        self.selected_language = None
        self.layout = QVBoxLayout(self)
        self.label = QLabel(self.texts['select_language_label'])
        self.layout.addWidget(self.label)
        self.list_widget = QListWidget()
        self.layout.addWidget(self.list_widget)
        self.system_lang = system_lang
        self.system_lang_button = None
        # languages is now a list of tuples (code, title)
        self.lang_code_by_row = []
        for code, title in languages:
            self.list_widget.addItem(title)
            self.lang_code_by_row.append(code)
        # "Select system language" button, if it is in the list
        if self.system_lang and self.system_lang in [code for code, _ in languages]:
            self.system_lang_button = QPushButton(self.texts['select_language_system'].format(self.system_lang))
            self.system_lang_button.clicked.connect(self.select_system_lang)
            self.layout.addWidget(self.system_lang_button)
        self.ok_button = QPushButton(self.texts['ok'])
        self.ok_button.setEnabled(False)
        self.layout.addWidget(self.ok_button)
        self.list_widget.itemSelectionChanged.connect(self.on_selection)
        self.ok_button.clicked.connect(self.accept)
        # Double-click on a list item confirms the selection
        self.list_widget.itemDoubleClicked.connect(self.accept)

    def select_system_lang(self):
        # Find and select the system language in the list by code
        for i, code in enumerate(self.lang_code_by_row):
            if code == self.system_lang:
                self.list_widget.setCurrentRow(i)
                break

    def on_selection(self):
        self.ok_button.setEnabled(bool(self.list_widget.selectedItems()))

    def get_selected_language(self):
        idx = self.list_widget.currentRow()
        if idx >= 0:
            return self.lang_code_by_row[idx]
        return None




