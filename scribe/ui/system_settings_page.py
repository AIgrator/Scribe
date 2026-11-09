# ui/system_settings_page.py
import logging

from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from scribe import autostart
from scribe.translation_manager import TranslationManager
from scribe.utils import get_data_dir

from .styles import HINT_LABEL_STYLE

logger = logging.getLogger(__name__)


class SystemSettingsPageWidget(QWidget):
    """System-level settings: performance, language, recording, logs, startup."""

    def __init__(self, texts, settings_manager, parent=None):
        super().__init__(parent)
        self.texts = texts
        self.settings_manager = settings_manager
        self.settings = self.settings_manager.all()

        layout = QFormLayout(self)
        layout.setSpacing(10)

        self._build_blocksize_group(layout)
        self._build_language_selector(layout)
        self._build_file_group(layout)
        self._build_logging_group(layout)
        self._build_autostart_group(layout)

    def _build_blocksize_group(self, layout):
        self.blocksize_group = QGroupBox(self.texts.get('blocksize_group', 'CPU load'))
        blocksize_layout = QHBoxLayout(self.blocksize_group)
        self.blocksize_buttons = QButtonGroup(self)
        self.blocksize_radio_4000 = QRadioButton(self.texts.get('blocksize_high', 'High'))
        self.blocksize_radio_8000 = QRadioButton(self.texts.get('blocksize_medium', 'Medium'))
        self.blocksize_radio_16000 = QRadioButton(self.texts.get('blocksize_low', 'Low'))
        self.blocksize_buttons.addButton(self.blocksize_radio_4000, 4000)
        self.blocksize_buttons.addButton(self.blocksize_radio_8000, 8000)
        self.blocksize_buttons.addButton(self.blocksize_radio_16000, 16000)
        blocksize_layout.addWidget(QLabel(self.texts.get('blocksize_label', 'Load:')))
        blocksize_layout.addWidget(self.blocksize_radio_4000)
        blocksize_layout.addWidget(self.blocksize_radio_8000)
        blocksize_layout.addWidget(self.blocksize_radio_16000)

        blocksize_val = self.settings.get('blocksize', 4000)
        if blocksize_val == 4000:
            self.blocksize_radio_4000.setChecked(True)
        elif blocksize_val == 8000:
            self.blocksize_radio_8000.setChecked(True)
        else:
            self.blocksize_radio_16000.setChecked(True)
        self.blocksize_buttons.buttonClicked.connect(self._on_blocksize_changed)
        layout.addRow(self.blocksize_group)

    def _build_language_selector(self, layout):
        self.language_select = QComboBox()
        supported_lang_list = TranslationManager.get_supported_languages()
        for code in supported_lang_list:
            name = self.texts.get(f'language_native_{code}', code.upper())
            self.language_select.addItem(name, code)
        current_lang = self.settings.get('ui_language', 'en')
        if current_lang in supported_lang_list:
            self.language_select.setCurrentIndex(supported_lang_list.index(current_lang))
        layout.addRow(self.texts.get('ui_language_label', 'Interface language'), self.language_select)

    def _build_file_group(self, layout):
        file_group = QGroupBox(self.texts.get('file_record_group', 'File recording'))
        file_group_layout = QVBoxLayout(file_group)
        self.transcribe_to_file_checkbox = QCheckBox(
            self.texts.get('transcribe_to_file', 'Save transcription to file')
        )
        self.transcribe_to_file_checkbox.setChecked(self.settings.get('transcribe_to_file', False))
        self.transcribe_to_file_checkbox.setToolTip(
            self.texts.get(
                'transcribe_to_file_hint',
                'Only final results will be saved to a text file named by the current Unix timestamp.'
            )
        )
        file_group_layout.addWidget(self.transcribe_to_file_checkbox)

        self.open_records_button = QPushButton(
            self.texts.get('open_records_folder', 'Open records folder')
        )
        self.open_records_button.clicked.connect(self.open_records_folder)
        file_group_layout.addWidget(self.open_records_button)
        layout.addRow(file_group)

    def _build_logging_group(self, layout):
        logging_group = QGroupBox(self.texts.get('logging_group', 'Logging'))
        logging_layout = QVBoxLayout(logging_group)
        self.log_to_file_checkbox = QCheckBox(
            self.texts.get('log_to_file', 'Log program activity to file')
        )
        self.log_to_file_checkbox.setChecked(self.settings.get('log_to_file', False))
        self.log_to_file_checkbox.stateChanged.connect(self._on_log_to_file_changed)
        logging_layout.addWidget(self.log_to_file_checkbox)

        log_restart_label = QLabel(
            self.texts.get('restart_hint', 'Changes will take effect after restarting the program.')
        )
        log_restart_label.setStyleSheet(HINT_LABEL_STYLE)
        logging_layout.addWidget(log_restart_label)

        log_levels = [
            ('DEBUG', self.texts.get('log_level_debug', 'Debug')),
            ('INFO', self.texts.get('log_level_info', 'Info')),
            ('WARNING', self.texts.get('log_level_warning', 'Warning')),
            ('ERROR', self.texts.get('log_level_error', 'Error')),
            ('CRITICAL', self.texts.get('log_level_critical', 'Critical')),
        ]
        self.log_level_select = QComboBox()
        for code, name in log_levels:
            self.log_level_select.addItem(name, code)
        current_level = self.settings.get('log_level', 'INFO')
        idx = next((i for i, (code, _) in enumerate(log_levels) if code == current_level), 1)
        self.log_level_select.setCurrentIndex(idx)
        self.log_level_select.currentIndexChanged.connect(self._on_log_level_changed)

        log_level_layout = QHBoxLayout()
        log_level_layout.addWidget(QLabel(self.texts.get('log_level_label', 'Log level')))
        log_level_layout.addWidget(self.log_level_select)
        logging_layout.addLayout(log_level_layout)
        layout.addRow(logging_group)

    def _build_autostart_group(self, layout):
        if not autostart.is_supported():
            return

        autostart_group = QGroupBox(self.texts.get('autostart_group', 'Startup'))
        autostart_layout = QVBoxLayout(autostart_group)
        self.autostart_checkbox = QCheckBox(
            self.texts.get('autostart', 'Start Scribe when I sign in')
        )
        self.autostart_checkbox.setChecked(autostart.is_enabled())
        self.autostart_checkbox.stateChanged.connect(self._on_autostart_toggled)
        autostart_layout.addWidget(self.autostart_checkbox)

        autostart_hint = QLabel(
            self.texts.get(
                'autostart_hint',
                'Scribe will start automatically after you sign in to your computer.'
            )
        )
        autostart_hint.setStyleSheet(HINT_LABEL_STYLE)
        autostart_layout.addWidget(autostart_hint)
        layout.addRow(autostart_group)

    def _on_blocksize_changed(self):
        self.settings_manager.set('blocksize', self.blocksize_buttons.checkedId())

    def _on_log_to_file_changed(self, state):
        self.settings_manager.set('log_to_file', bool(state))

    def _on_log_level_changed(self, idx):
        self.settings_manager.set('log_level', self.log_level_select.currentData())

    def _on_autostart_toggled(self, state):
        enabled = bool(state)
        try:
            autostart.set_enabled(enabled)
        except Exception as e:
            logger.error(f"Failed to change autostart: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                self.texts.get('autostart_error_title', 'Startup'),
                self.texts.get(
                    'autostart_error',
                    'Failed to change the autostart setting:\n{}'
                ).format(e),
            )
            self.autostart_checkbox.blockSignals(True)
            self.autostart_checkbox.setChecked(not enabled)
            self.autostart_checkbox.blockSignals(False)

    def open_records_folder(self):
        import os
        import subprocess

        records_dir = os.path.join(get_data_dir(), 'records')
        if not os.path.exists(records_dir):
            os.makedirs(records_dir, exist_ok=True)
        try:
            subprocess.Popen(f'explorer "{records_dir}"')
        except Exception as e:
            logger.error(f"Failed to open records folder: {e}")

    def get_transcribe_to_file(self):
        return self.transcribe_to_file_checkbox.isChecked()

    def get_ui_language(self):
        return self.language_select.currentData()
