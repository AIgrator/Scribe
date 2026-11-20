# ui/main_settings_page.py
import logging

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QColorDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .mode_control_widget import ModeControlWidget

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

        self.mode_buttons_group = QGroupBox(self.texts.get('modes_control', 'Modes control'))
        self.mode_buttons_group_layout = QVBoxLayout(self.mode_buttons_group)

        tray_colors = self.settings.get('tray_color', self.settings_manager.DEFAULTS.get('tray_color', {}))
        self.mode_controls = ModeControlWidget(self.texts, self.settings_manager, tray_colors=tray_colors)
        self.mode_controls.transcribe_clicked.connect(self.toggle_transcribe_mode)
        self.mode_controls.command_clicked.connect(self.toggle_command_mode)

        self.mode_buttons_group_layout.addWidget(self.mode_controls)

        # Auto-stop timeout: minutes + seconds, plus one-click presets.
        self.auto_stop_label = QLabel(self.texts.get('auto_stop_label', 'Auto-stop listening:'))
        self._auto_stop_updating = False

        self.auto_stop_minutes = QSpinBox()
        self.auto_stop_minutes.setRange(0, 60)
        self.auto_stop_minutes.setSuffix(
            ' ' + self.texts.get('auto_stop_minutes', 'min'))
        self.auto_stop_minutes.setToolTip(
            self.texts.get('auto_stop_minutes_hint',
                           'Minutes before listening stops. 0 minutes and 0 seconds means Never.'))
        self.auto_stop_minutes.valueChanged.connect(self._on_auto_stop_changed)

        self.auto_stop_seconds = QSpinBox()
        self.auto_stop_seconds.setRange(0, 59)
        self.auto_stop_seconds.setSuffix(
            ' ' + self.texts.get('auto_stop_seconds', 'sec'))
        self.auto_stop_seconds.setToolTip(
            self.texts.get('auto_stop_seconds_hint',
                           'Additional seconds before listening stops.'))
        self.auto_stop_seconds.valueChanged.connect(self._on_auto_stop_changed)

        self.auto_stop_hint = QLabel()
        self.auto_stop_hint.setStyleSheet("color: gray;")

        auto_stop_layout = QHBoxLayout()
        auto_stop_layout.addWidget(self.auto_stop_label)
        auto_stop_layout.addWidget(self.auto_stop_minutes)
        auto_stop_layout.addWidget(self.auto_stop_seconds)
        auto_stop_layout.addWidget(self.auto_stop_hint)
        auto_stop_layout.addStretch()
        self.mode_buttons_group_layout.addLayout(auto_stop_layout)

        presets_layout = QHBoxLayout()
        presets_layout.addWidget(QLabel(
            self.texts.get('auto_stop_presets', 'Quick:')))
        self.auto_stop_presets = [
            (self.texts.get('auto_stop_never', 'Never'), 0),
            (self.texts.get('auto_stop_10s', '10 seconds'), 10),
            (self.texts.get('auto_stop_30s', '30 seconds'), 30),
            (self.texts.get('auto_stop_1m', '1 minute'), 60),
            (self.texts.get('auto_stop_5m', '5 minutes'), 300),
            (self.texts.get('auto_stop_10m', '10 minutes'), 600),
        ]
        for text, seconds in self.auto_stop_presets:
            button = QPushButton(text)
            button.setAutoDefault(False)
            button.setDefault(False)
            button.clicked.connect(
                lambda checked=False, value=seconds: self._apply_auto_stop_preset(value))
            presets_layout.addWidget(button)
        presets_layout.addStretch()
        self.mode_buttons_group_layout.addLayout(presets_layout)

        self._set_auto_stop_controls(
            self.settings.get('auto_stop_timeout', 0), save=False)

        layout.addRow(self.mode_buttons_group)

        # Connect to the controller reloaded signal to keep the widget in sync
        if self.tray_app and hasattr(self.tray_app, 'controller_reloaded'):
            self.tray_app.controller_reloaded.connect(self._on_controller_reloaded)

        # Set the initial state of buttons and colors
        self._update_button_state()

        # Group for interface and mode color settings
        color_group = QGroupBox(self.texts.get('tray_color_group', 'Interface and mode colors'))
        color_layout = QHBoxLayout(color_group)

        def rgb2qcolor(rgb):
            return QColor(*rgb) if isinstance(rgb, (list, tuple)) and len(rgb) == 3 else QColor(255, 255, 255)

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

    def _on_auto_stop_changed(self, _value):
        if self._auto_stop_updating:
            return
        self._save_auto_stop()

    def _apply_auto_stop_preset(self, seconds):
        """Applies a preset immediately, without scrolling the spin boxes."""
        self._set_auto_stop_controls(seconds, save=True)

    def _set_auto_stop_controls(self, total_seconds, save):
        try:
            total_seconds = max(0, int(total_seconds))
        except (TypeError, ValueError):
            total_seconds = 0
        minutes, seconds = divmod(total_seconds, 60)
        self._auto_stop_updating = True
        try:
            self.auto_stop_minutes.setValue(min(minutes, 60))
            self.auto_stop_seconds.setValue(seconds if minutes <= 60 else 0)
        finally:
            self._auto_stop_updating = False
        self._update_auto_stop_hint()
        if save:
            self._save_auto_stop()

    def _current_auto_stop_seconds(self):
        return self.auto_stop_minutes.value() * 60 + self.auto_stop_seconds.value()

    def _save_auto_stop(self):
        self._update_auto_stop_hint()
        self.settings_manager.set(
            'auto_stop_timeout', self._current_auto_stop_seconds())

    def _update_auto_stop_hint(self):
        total = self._current_auto_stop_seconds()
        if total == 0:
            self.auto_stop_hint.setText(
                self.texts.get('auto_stop_never', 'Never'))
        else:
            self.auto_stop_hint.setText("")

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
                    pass  # Not connected
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
        current = tray_color.get(key, [255, 255, 255])
        color = QColorDialog.getColor(QColor(*current), self, self.texts.get('select_color', 'Выберите цвет'))
        if color.isValid():
            rgb = [color.red(), color.green(), color.blue()]
            tray_color[key] = rgb
            self.settings_manager.set('tray_color', tray_color)
            btn.setStyleSheet(f"background: {color.name()};")
