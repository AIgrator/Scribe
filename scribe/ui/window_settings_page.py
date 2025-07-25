# ui/window_settings_page.py
from PyQt5.QtWidgets import QButtonGroup, QCheckBox, QGroupBox, QHBoxLayout, QLabel, QRadioButton, QVBoxLayout, QWidget

from .styles import HINT_LABEL_STYLE


class WindowSettingsPageWidget(QWidget):
    def __init__(self, texts, settings_manager, parent=None):
        super().__init__(parent)
        self.texts = texts
        self.settings_manager = settings_manager
        self.settings = self.settings_manager.all()
        self.main_window_settings = self.settings.get('main_window', {})

        layout = QVBoxLayout(self)
        # Show main window
        self.show_main_window_checkbox = QCheckBox(self.texts.get('main_window_show_on_startup', 'Show main window on startup'))
        self.show_main_window_checkbox.setChecked(self.main_window_settings.get('show_on_startup', True))
        self.show_main_window_checkbox.stateChanged.connect(self._on_show_main_window_changed)
        layout.addWidget(self.show_main_window_checkbox)
        # Always on top
        self.always_on_top_checkbox = QCheckBox(self.texts.get('always_on_top', 'Always on top'))
        self.always_on_top_checkbox.setChecked(self.main_window_settings.get('always_on_top', False))
        self.always_on_top_checkbox.stateChanged.connect(self._on_always_on_top_changed)
        layout.addWidget(self.always_on_top_checkbox)

        # Add a restart note for always on top
        always_on_top_hint_label = QLabel(self.texts.get('restart_hint', 'Changes will take effect after restarting the program.'))
        always_on_top_hint_label.setStyleSheet(HINT_LABEL_STYLE)
        layout.addWidget(always_on_top_hint_label)

        # Close: to tray or exit (grouped)
        self.close_behavior_group = QGroupBox(self.texts.get('main_window_close_behavior_label', 'When closing main window:'))
        close_behavior_layout = QVBoxLayout(self.close_behavior_group) # Changed to QVBoxLayout

        radio_buttons_layout = QHBoxLayout() # New QHBoxLayout for radio buttons
        self.close_group = QButtonGroup(self)
        self.close_to_tray_radio = QRadioButton(self.texts.get('close_to_tray', 'Minimize to tray'))
        self.close_exit_radio = QRadioButton(self.texts.get('close_exit', 'Exit program'))
        radio_buttons_layout.addWidget(self.close_to_tray_radio)
        radio_buttons_layout.addWidget(self.close_exit_radio)
        self.close_group.addButton(self.close_to_tray_radio, 0)
        self.close_group.addButton(self.close_exit_radio, 1)
        close_behavior = self.main_window_settings.get('close_behavior', 'tray')
        if close_behavior == 'exit':
            self.close_exit_radio.setChecked(True)
        else:
            self.close_to_tray_radio.setChecked(True)
        self.close_group.buttonClicked.connect(self._on_close_behavior_changed)

        close_behavior_layout.addLayout(radio_buttons_layout) # Add QHBoxLayout to QVBoxLayout

        # Add a restart note
        restart_hint_label = QLabel(self.texts.get('restart_hint', 'Changes will take effect after restarting the program.'))
        restart_hint_label.setStyleSheet(HINT_LABEL_STYLE)
        close_behavior_layout.addWidget(restart_hint_label)

        layout.addWidget(self.close_behavior_group)

        # Window size settings group
        self.size_group = QGroupBox(self.texts.get('window_size_group', 'Window size'))
        size_layout = QHBoxLayout(self.size_group)
        self.size_btn_group = QButtonGroup(self)
        self.size_small_radio = QRadioButton(self.texts.get('window_size_small', 'Small'))
        self.size_medium_radio = QRadioButton(self.texts.get('window_size_medium', 'Medium'))
        self.size_large_radio = QRadioButton(self.texts.get('window_size_large', 'Large'))
        size_layout.addWidget(QLabel(self.texts.get('window_size_label', 'Size:')))
        size_layout.addWidget(self.size_small_radio)
        size_layout.addWidget(self.size_medium_radio)
        size_layout.addWidget(self.size_large_radio)
        self.size_btn_group.addButton(self.size_small_radio, 0)
        self.size_btn_group.addButton(self.size_medium_radio, 1)
        self.size_btn_group.addButton(self.size_large_radio, 2)
        # Determine the selected size from the settings
        size_value = self.main_window_settings.get('size_mode', 'medium')
        if size_value == 'small':
            self.size_small_radio.setChecked(True)
        elif size_value == 'medium':
            self.size_medium_radio.setChecked(True)
        else:
            self.size_large_radio.setChecked(True)
        self.size_btn_group.buttonClicked.connect(self._on_size_mode_changed)
        layout.addWidget(self.size_group)

        # Checkbox to display the sound indicator (WaveformWidget)
        self.show_waveform_checkbox = QCheckBox(self.texts.get('show_waveform', 'Show audio indicator'))
        self.show_waveform_checkbox.setChecked(self.main_window_settings.get('show_waveform', True))
        self.show_waveform_checkbox.stateChanged.connect(self._on_show_waveform_changed)
        layout.addWidget(self.show_waveform_checkbox)

        # Theme settings group
        self.theme_group = QGroupBox(self.texts.get('theme_settings_group', 'Theme'))
        theme_layout = QHBoxLayout(self.theme_group)
        self.theme_btn_group = QButtonGroup(self)
        self.theme_light_radio = QRadioButton(self.texts.get('theme_light', 'Light'))
        self.theme_dark_radio = QRadioButton(self.texts.get('theme_dark', 'Dark'))
        self.theme_auto_radio = QRadioButton(self.texts.get('theme_auto', 'Auto (System)'))
        theme_layout.addWidget(self.theme_light_radio)
        theme_layout.addWidget(self.theme_dark_radio)
        theme_layout.addWidget(self.theme_auto_radio)
        self.theme_btn_group.addButton(self.theme_light_radio, 0)
        self.theme_btn_group.addButton(self.theme_dark_radio, 1)
        self.theme_btn_group.addButton(self.theme_auto_radio, 2)
        theme_value = self.main_window_settings.get('theme', 'auto')
        if theme_value == 'light':
            self.theme_light_radio.setChecked(True)
        elif theme_value == 'dark':
            self.theme_dark_radio.setChecked(True)
        else:
            self.theme_auto_radio.setChecked(True)
        self.theme_btn_group.buttonClicked.connect(self._on_theme_changed)
        layout.addWidget(self.theme_group)

        # Open on tray click
        self.open_on_tray_click_checkbox = QCheckBox(self.texts.get('open_on_tray_click_label', 'Open window on tray icon click'))
        self.open_on_tray_click_checkbox.setChecked(self.main_window_settings.get('open_on_tray_click', True))
        self.open_on_tray_click_checkbox.stateChanged.connect(self._on_open_on_tray_click_changed)
        layout.addWidget(self.open_on_tray_click_checkbox)

        layout.addStretch()


    def _on_open_on_tray_click_changed(self, state):
        self.main_window_settings['open_on_tray_click'] = bool(state)
        self.settings_manager.set('main_window', self.main_window_settings)

    def _on_show_waveform_changed(self, state):
        self.main_window_settings['show_waveform'] = bool(state)
        self.settings_manager.set('main_window', self.main_window_settings)

    def _on_theme_changed(self, btn):
        if self.theme_light_radio.isChecked():
            val = 'light'
        elif self.theme_dark_radio.isChecked():
            val = 'dark'
        else:
            val = 'auto'
        self.main_window_settings['theme'] = val
        self.settings_manager.set('main_window', self.main_window_settings)

    def _on_theme_changed(self, btn):
        if self.theme_light_radio.isChecked():
            val = 'light'
        elif self.theme_dark_radio.isChecked():
            val = 'dark'
        else:
            val = 'auto'
        self.main_window_settings['theme'] = val
        self.settings_manager.set('main_window', self.main_window_settings)

    def _on_show_main_window_changed(self, state):
        self.main_window_settings['show_on_startup'] = bool(state)
        self.settings_manager.set('main_window', self.main_window_settings)

    def _on_always_on_top_changed(self, state):
        self.main_window_settings['always_on_top'] = bool(state)
        self.settings_manager.set('main_window', self.main_window_settings)

    def _on_close_behavior_changed(self, btn):
        val = 'exit' if self.close_exit_radio.isChecked() else 'tray'
        self.main_window_settings['close_behavior'] = val
        self.settings_manager.set('main_window', self.main_window_settings)

    def _on_size_mode_changed(self, btn):
        if self.size_small_radio.isChecked():
            val = 'small'
        elif self.size_medium_radio.isChecked():
            val = 'medium'
        else:
            val = 'large'
        self.main_window_settings['size_mode'] = val
        self.settings_manager.set('main_window', self.main_window_settings)
