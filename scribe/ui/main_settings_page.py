# ui/main_settings_page.py
import logging

from PyQt5.QtWidgets import QFormLayout, QWidget

from .mode_control_widget import ModeControlWidget
from .styles import HINT_LABEL_STYLE

logger = logging.getLogger(__name__)

class MainSettingsPageWidget(QWidget):
    def __init__(self, tray_app, texts, settings_manager, parent=None):
        super().__init__(parent)
        self.tray_app = tray_app
        self.texts = texts
        self.settings_manager = settings_manager
        self.settings = self.settings_manager.all()

        layout = QFormLayout(self)
        layout.setSpacing(10)

        from PyQt5.QtWidgets import QComboBox, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
        self.mode_buttons_group = QGroupBox(self.texts.get('modes_control', 'Modes control'))
        self.mode_buttons_group_layout = QVBoxLayout(self.mode_buttons_group)

        tray_colors = self.settings.get('tray_color', self.settings_manager.DEFAULTS.get('tray_color', {}))
        self.mode_controls = ModeControlWidget(self.texts, self.settings_manager, tray_colors=tray_colors)
        self.mode_controls.transcribe_clicked.connect(self.toggle_transcribe_mode)
        self.mode_controls.command_clicked.connect(self.toggle_command_mode)

        self.mode_buttons_group_layout.addWidget(self.mode_controls)

        # Auto-stop timeout selector
        self.auto_stop_label = QLabel(self.texts.get('auto_stop_label', 'Auto-stop listening:'))
        self.auto_stop_select = QComboBox()

        self.timeout_options = [
            (self.texts.get('auto_stop_never', 'Never'), 0),
            (self.texts.get('auto_stop_10s', '10 seconds'), 10),
            (self.texts.get('auto_stop_30s', '30 seconds'), 30),
            (self.texts.get('auto_stop_1m', '1 minute'), 60),
            (self.texts.get('auto_stop_5m', '5 minutes'), 300),
            (self.texts.get('auto_stop_10m', '10 minutes'), 600),
        ]

        for text, seconds in self.timeout_options:
            self.auto_stop_select.addItem(text, seconds)

        current_timeout = self.settings.get('auto_stop_timeout', 0)
        for i, (_, seconds) in enumerate(self.timeout_options):
            if seconds == current_timeout:
                self.auto_stop_select.setCurrentIndex(i)
                break

        self.auto_stop_select.currentIndexChanged.connect(self._on_auto_stop_changed)

        auto_stop_layout = QHBoxLayout()
        auto_stop_layout.addWidget(self.auto_stop_label)
        auto_stop_layout.addWidget(self.auto_stop_select)
        auto_stop_layout.addStretch()
        self.mode_buttons_group_layout.addLayout(auto_stop_layout)

        layout.addRow(self.mode_buttons_group)

        # Connect to the controller reloaded signal to keep the widget in sync
        if self.tray_app and hasattr(self.tray_app, 'controller_reloaded'):
            self.tray_app.controller_reloaded.connect(self._on_controller_reloaded)

        # Set the initial state of buttons and colors
        self._update_button_state()

        # Group "CPU load (blocksize)"
        from PyQt5.QtWidgets import QButtonGroup, QGroupBox, QLabel, QRadioButton
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
        # Set current value from settings
        blocksize_val = self.settings.get('blocksize', 4000)
        if blocksize_val == 4000:
            self.blocksize_radio_4000.setChecked(True)
        elif blocksize_val == 8000:
            self.blocksize_radio_8000.setChecked(True)
        else:
            self.blocksize_radio_16000.setChecked(True)
        def on_blocksize_changed():
            val = self.blocksize_buttons.checkedId()
            self.settings_manager.set('blocksize', val)
        self.blocksize_buttons.buttonClicked.connect(on_blocksize_changed)

        # Group for interface and mode color settings
        from PyQt5.QtWidgets import QGroupBox, QHBoxLayout
        color_group = QGroupBox(self.texts.get('tray_color_group', 'Interface and mode colors'))
        color_layout = QHBoxLayout(color_group)
        from PyQt5.QtGui import QColor
        def rgb2qcolor(rgb):
            return QColor(*rgb) if isinstance(rgb, (list, tuple)) and len(rgb) == 3 else QColor(255,255,255)
        tray_color = self.settings.get('tray_color', self.settings_manager.DEFAULTS.get('tray_color', {}))
        self.text_color_btn = QPushButton(self.texts.get('tray_text_color', 'Text color'))
        self.text_color_btn.setStyleSheet(f"background: {rgb2qcolor(tray_color.get('text_color', [255,255,255])).name()};")
        self.text_color_btn.clicked.connect(lambda: self._pick_color('text_color', self.text_color_btn))
        color_layout.addWidget(self.text_color_btn)
        self.transcribe_color_btn = QPushButton(self.texts.get('tray_transcribe_color', 'Transcription color'))
        self.transcribe_color_btn.setStyleSheet(f"background: {rgb2qcolor(tray_color.get('transcribe_color', [255,106,0])).name()};")
        self.transcribe_color_btn.clicked.connect(lambda: self._pick_color('transcribe_color', self.transcribe_color_btn))
        color_layout.addWidget(self.transcribe_color_btn)
        self.command_color_btn = QPushButton(self.texts.get('tray_command_color', 'Command color'))
        self.command_color_btn.setStyleSheet(f"background: {rgb2qcolor(tray_color.get('command_color', [72,0,255])).name()};")
        self.command_color_btn.clicked.connect(lambda: self._pick_color('command_color', self.command_color_btn))
        color_layout.addWidget(self.command_color_btn)
        layout.addRow(color_group)

        layout.addRow(self.blocksize_group)

        # Interface language selector
        from PyQt5.QtWidgets import QCheckBox, QComboBox, QLabel
        self.language_select = QComboBox()
        # Get supported languages dynamically via TranslationManager
        from scribe.translation_manager import TranslationManager
        supported_lang_list = TranslationManager.get_supported_languages()
        for code in supported_lang_list:
            # We get the human-readable name of the language from the translations, otherwise we use code.upper()
            name = self.texts.get(f'language_native_{code}', code.upper())
            self.language_select.addItem(name, code)
        current_lang = self.settings.get('ui_language', 'en')
        if current_lang in supported_lang_list:
            self.language_select.setCurrentIndex(supported_lang_list.index(current_lang))
        layout.addRow(self.texts.get('ui_language_label', 'Interface language'), self.language_select)

        # Group "File recording"
        from PyQt5.QtWidgets import QGroupBox, QPushButton, QVBoxLayout
        file_group = QGroupBox(self.texts.get('file_record_group', 'File recording'))
        file_group_layout = QVBoxLayout(file_group)
        # Checkbox
        self.transcribe_to_file_checkbox = QCheckBox(self.texts.get('transcribe_to_file', 'Save transcription to file'))
        self.transcribe_to_file_checkbox.setChecked(self.settings.get('transcribe_to_file', False))
        self.transcribe_to_file_checkbox.setToolTip(
            self.texts.get(
                'transcribe_to_file_hint',
                'Only final results will be saved to a text file named by the current Unix timestamp.'
            )
        )
        file_group_layout.addWidget(self.transcribe_to_file_checkbox)
        # Button to open folder
        self.open_records_button = QPushButton(self.texts.get('open_records_folder', 'Open records folder'))
        self.open_records_button.clicked.connect(self.open_records_folder)
        file_group_layout.addWidget(self.open_records_button)
        layout.addRow(file_group)


        # Logging Group
        from PyQt5.QtWidgets import QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel, QVBoxLayout
        logging_group = QGroupBox(self.texts.get('logging_group', 'Logging'))
        logging_layout = QVBoxLayout(logging_group)
        # Checkbox
        self.log_to_file_checkbox = QCheckBox(self.texts.get('log_to_file', 'Log program activity to file'))
        self.log_to_file_checkbox.setChecked(self.settings.get('log_to_file', False))
        self.log_to_file_checkbox.stateChanged.connect(self._on_log_to_file_changed)
        logging_layout.addWidget(self.log_to_file_checkbox)
        from PyQt5.QtWidgets import QLabel
        log_restart_label = QLabel(self.texts.get('restart_hint', 'Changes will take effect after restarting the program.'))
        log_restart_label.setStyleSheet(HINT_LABEL_STYLE)
        logging_layout.addWidget(log_restart_label)
        # Log level selector
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
        log_level_label = QLabel(self.texts.get('log_level_label', 'Log level'))
        log_level_layout = QHBoxLayout()
        log_level_layout.addWidget(log_level_label)
        log_level_layout.addWidget(self.log_level_select)
        logging_layout.addLayout(log_level_layout)
        layout.addRow(logging_group)

    def _on_auto_stop_changed(self, index):
        timeout_seconds = self.auto_stop_select.itemData(index)
        self.settings_manager.set('auto_stop_timeout', timeout_seconds)

    def _on_controller_reloaded(self, new_controller):
        """Handles the controller reload signal by reconnecting signals."""
        logger.debug("[MainSettingsPage] Controller reloaded, reconnecting signals.")
        self._update_button_state()

    def _update_button_state(self):
        """Connects to the current controller's signals and updates the button state."""
        controller = self._get_controller()
        if controller:
            recognizer = getattr(controller, 'recognizer', None)
            if recognizer and hasattr(recognizer, 'recognition_state_changed'):
                # Disconnect first to avoid duplicate connections
                try:
                    recognizer.recognition_state_changed.disconnect(self.mode_controls.update_state)
                except TypeError:
                    pass # Not connected
                recognizer.recognition_state_changed.connect(self.mode_controls.update_state)

            # Update the state immediately
            self.mode_controls.update_state(
                getattr(controller, 'running', False),
                getattr(recognizer, 'mode', None)
            )

    def _get_controller(self):
        if self.tray_app and hasattr(self.tray_app, 'controller'):
            return self.tray_app.controller
        return None

    def toggle_transcribe_mode(self):
        controller = self._get_controller()
        if controller:
            controller.switch_to_transcribe_mode()

    def toggle_command_mode(self):
        controller = self._get_controller()
        if controller:
            controller.switch_to_command_mode()

    def _pick_color(self, key, btn):
        tray_color = self.settings.get('tray_color', self.settings_manager.DEFAULTS.get('tray_color', {})).copy()
        current = tray_color.get(key, [255,255,255])
        from PyQt5.QtGui import QColor
        from PyQt5.QtWidgets import QColorDialog
        color = QColorDialog.getColor(QColor(*current), self, self.texts.get('select_color', 'Выберите цвет'))
        if color.isValid():
            rgb = [color.red(), color.green(), color.blue()]
            tray_color[key] = rgb
            self.settings_manager.set('tray_color', tray_color)
            btn.setStyleSheet(f"background: {color.name()};")

    def open_records_folder(self):
        import os
        import subprocess
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        records_dir = os.path.join(base_dir, 'records')
        if not os.path.exists(records_dir):
            os.makedirs(records_dir, exist_ok=True)
        # Open folder in Explorer (Windows)
        try:
            subprocess.Popen(f'explorer "{records_dir}"')
        except Exception as e:
            logger.error(f"Failed to open records folder: {e}")
    def get_transcribe_to_file(self):
        return self.transcribe_to_file_checkbox.isChecked()

    def get_ui_language(self):
        return self.language_select.currentData()

    def _on_log_to_file_changed(self, state):
        self.settings_manager.set('log_to_file', bool(state))

    def _on_log_level_changed(self, idx):
        level = self.log_level_select.currentData()
        self.settings_manager.set('log_level', level)
