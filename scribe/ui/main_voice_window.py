# ui/main_voice_window.py
import logging

from PyQt5.QtCore import QPoint, QSize, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter
from PyQt5.QtWidgets import QComboBox, QFrame, QHBoxLayout, QMenu, QPushButton, QVBoxLayout, QWidget

from scribe.ui.mode_control_widget import ModeControlWidget
from scribe.ui.styles import DARK_THEME_STYLESHEET, LIGHT_THEME_STYLESHEET, is_system_in_dark_mode
from scribe.utils import resource_path

logger = logging.getLogger(__name__)

class WaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.amplitudes = [0] * 64
        self.setMinimumHeight(128)
        self.setMaximumHeight(128)
        self.setSizePolicy(self.sizePolicy().Expanding, self.sizePolicy().Fixed)

    def update_wave(self, value):
        # value: float (0..1) — update wave (move left, add new value to right)
        self.amplitudes = self.amplitudes[1:] + [max(0.0, min(1.0, value))]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        n = len(self.amplitudes)

        fixed_bar_width = 3 # Desired fixed thickness of each bar in pixels

        if n > 0:
            # Total width occupied by all bars
            total_bars_width = n * fixed_bar_width
            # Total width available for gaps
            total_gap_width = w - total_bars_width
            # Width of each gap
            # If there are gaps (i.e., more than one bar), divide by (n-1)
            # Otherwise (one bar), the gap is 0
            gap_between_bars = total_gap_width / (n - 1) if n > 1 else 0
            # Make sure the gap is not negative
            gap_between_bars = max(0.0, gap_between_bars)
        else:
            fixed_bar_width = 0 # No bars to draw
            gap_between_bars = 0

        for i, amp in enumerate(self.amplitudes):
            # X position for the current bar
            x = int(i * (fixed_bar_width + gap_between_bars))

            bar_h = int(amp * (h - 8))
            y = h // 2 - bar_h // 2
            color = QColor(120, 60, 255)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(x, y, fixed_bar_width, bar_h, 2, 2)

class MainVoiceWindow(QWidget):
    def __init__(self, tray_app, controller, texts, settings_manager, parent=None):
        super().__init__(parent)
        self.setObjectName("MainVoiceWindow") # Name for applying styles
        self.tray_app = tray_app
        self.controller = controller
        self.texts = texts
        self.settings_manager = settings_manager
        self.current_theme = None
        self._is_programmatic_close = False
        self.setWindowTitle(self.texts.get('main_window_title', 'Scribe'))

        # Get scale from settings
        settings = self.settings_manager.all()
        main_window_settings = settings.get('main_window', {})
        size_mode = main_window_settings.get('size_mode', 'large')
        self.show_waveform = main_window_settings.get('show_waveform', True)
        if size_mode == 'small':
            self.scale = 0.5
        elif size_mode == 'medium':
            self.scale = 0.75
        else:
            self.scale = 1.0

        # Get base sizes from settings
        sizes = main_window_settings.get('sizes', {})
        self.base_window_width = sizes.get('window_width', 600)
        self.base_window_height = sizes.get('window_height', 250)
        self.base_waveform_height = sizes.get('waveform_height', 128)
        self.base_btn_ico_height = sizes.get('btn_ico_height', 64)
        self.base_btn_ico_width = sizes.get('btn_ico_width', 64)
        self.base_btn_height = sizes.get('btn_height', 75)
        self.base_btn_width = sizes.get('btn_width', 75)
        self.base_btn_mode_width = sizes.get('btn_mode_width', 150)
        self.base_btn_ico_mode_width = sizes.get('btn_ico_mode_width', 128)

        if self.show_waveform:
            window_height = self.base_window_height
        else:
            window_height = self.base_window_height - self.base_waveform_height

        self.setMinimumSize(int(self.base_window_width * self.scale), int(window_height * self.scale))
        self.setMaximumSize(int(self.base_window_width * self.scale), int(window_height * self.scale))
        self.setWindowIcon(QIcon(resource_path('resources/icon.ico')))
        self._init_ui()
        self._apply_theme()

        # Connect signals to update UI
        if self.controller:
            # The controller's main state_changed signal is the source of truth
            self.controller.state_changed.connect(self.mode_controls.update_state)

            recognizer = getattr(self.controller, 'recognizer', None)
            if recognizer and hasattr(recognizer, 'rms_signal'):
                recognizer.rms_signal.connect(self.voice_indicator.update_wave)

            # Connect signal from controller to update microphone
            self.controller.microphone_changed.connect(self._update_microphone_display)

            # Set initial state
            self.mode_controls.update_state(
                getattr(self.controller, 'running', False),
                getattr(recognizer, 'mode', None)
            )
            self._update_microphone_display(self.controller.device_name)

        # Apply window settings
        always_on_top = main_window_settings.get('always_on_top', False)
        close_behavior = main_window_settings.get('close_behavior', 'tray')
        flags = self.windowFlags()
        if always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self._close_behavior = close_behavior
        self.show()

        # Connect to global settings changes to update UI
        self.settings_manager.settings_changed.connect(self._on_settings_changed)

    def _apply_theme(self):
        """Applies the selected theme (light or dark) to the main window."""
        main_window_settings = self.settings_manager.get('main_window', {})
        theme_setting = main_window_settings.get('theme', 'auto')

        is_dark = False
        if theme_setting == 'auto':
            is_dark = is_system_in_dark_mode()
        elif theme_setting == 'dark':
            is_dark = True

        if self.current_theme == ('dark' if is_dark else 'light'):
            return # Theme has not changed, do nothing

        self.current_theme = 'dark' if is_dark else 'light'

        if is_dark:
            self.setStyleSheet(DARK_THEME_STYLESHEET)
            self.mic_btn.setIcon(QIcon(resource_path('resources/choose_mic_64_white.png')))
            self.model_btn.setIcon(QIcon(resource_path('resources/choose_model_64_white.png')))
            self.settings_btn.setIcon(QIcon(resource_path('resources/settings_64_white.png')))
        else:
            self.setStyleSheet(LIGHT_THEME_STYLESHEET)
            self.mic_btn.setIcon(QIcon(resource_path('resources/choose_mic_64.png')))
            self.model_btn.setIcon(QIcon(resource_path('resources/choose_model_64.png')))
            self.settings_btn.setIcon(QIcon(resource_path('resources/settings_64.png')))

        # Update theme for child widget
        if hasattr(self, 'mode_controls') and hasattr(self.mode_controls, 'update_theme'):
            self.mode_controls.update_theme(self.current_theme)

    def _on_settings_changed(self, new_settings):
        """Updates the UI when settings change, including scaling and theme."""
        logger.debug("[MainVoiceWindow] Detected external settings change, updating UI.")
        main_window_settings = new_settings.get('main_window', {})

        # Check if the theme has changed
        self._apply_theme()

        # Check if the size mode has changed
        size_mode = main_window_settings.get('size_mode', 'large')
        if size_mode == 'small':
            new_scale = 0.5
        elif size_mode == 'medium':
            new_scale = 0.75
        else:
            new_scale = 1.0

        # Check if the waveform visibility has changed
        new_show_waveform = main_window_settings.get('show_waveform', True)

        scale_changed = hasattr(self, 'scale') and self.scale != new_scale
        waveform_visibility_changed = hasattr(self, 'show_waveform') and self.show_waveform != new_show_waveform

        if scale_changed:
            self.scale = new_scale

        if waveform_visibility_changed:
            self.show_waveform = new_show_waveform

        if scale_changed or waveform_visibility_changed:
            self._apply_scale()

        self._fill_models()

    def _apply_scale(self):
        """Applies the current scale to all elements of the main window."""
        self.voice_indicator.setVisible(self.show_waveform)

        if self.show_waveform:
            window_height = self.base_window_height
        else:
            # Decrease the window height by the waveform height
            window_height = self.base_window_height - self.base_waveform_height

        self.setMinimumSize(int(self.base_window_width * self.scale), int(window_height * self.scale))
        self.setMaximumSize(int(self.base_window_width * self.scale), int(window_height * self.scale))
        self.voice_indicator.setMinimumHeight(int(self.base_waveform_height * self.scale))
        self.voice_indicator.setMaximumHeight(int(self.base_waveform_height * self.scale))
        self.mic_btn.setIconSize(QSize(int(self.base_btn_ico_width * self.scale), int(self.base_btn_ico_height * self.scale)))
        self.mic_btn.setFixedSize(int(self.base_btn_width * self.scale), int(self.base_btn_height * self.scale))
        self.model_btn.setIconSize(QSize(int(self.base_btn_ico_width * self.scale), int(self.base_btn_ico_height * self.scale)))
        self.model_btn.setFixedSize(int(self.base_btn_width * self.scale), int(self.base_btn_height * self.scale))
        self.settings_btn.setIconSize(QSize(int(self.base_btn_ico_width * self.scale), int(self.base_btn_ico_height * self.scale)))
        self.settings_btn.setFixedSize(int(self.base_btn_width * self.scale), int(self.base_btn_height * self.scale))
        self.mic_combo.setMinimumWidth(int(180 * self.scale))
        self.model_combo.setMinimumWidth(int(220 * self.scale))
        # Scale the mode buttons
        if hasattr(self, 'mode_controls') and hasattr(self.mode_controls, 'apply_scale'):
            self.mode_controls.apply_scale(self.scale)
        self.updateGeometry()

    def _on_controller_reloaded(self, new_controller):
        """Slot for handling the controller reload signal.

        Updates the controller reference and reconnects all necessary signals.
        """
        logger.debug(f"[MainVoiceWindow] Controller reloaded. Old ID: {id(self.controller)}, New ID: {id(new_controller)}")

        # Disconnect old signals if the controller existed
        if self.controller:
            recognizer = getattr(self.controller, 'recognizer', None)
            if recognizer:
                if hasattr(recognizer, 'rms_signal'):
                    try:
                        recognizer.rms_signal.disconnect(self.voice_indicator.update_wave)
                    except TypeError:
                        pass # Signal not connected, ignore
                if hasattr(recognizer, 'recognition_state_changed'):
                    try:
                        recognizer.recognition_state_changed.disconnect(self.mode_controls.update_state)
                    except TypeError:
                        pass # Signal not connected, ignore
            try:
                self.controller.microphone_changed.disconnect(self._update_microphone_display)
            except TypeError:
                pass # Signal not connected, ignore

        # Update the reference to the new controller
        self.controller = new_controller

        # Connect new signals to the new controller
        if self.controller:
            # The controller's main state_changed signal is the source of truth
            self.controller.state_changed.connect(self.mode_controls.update_state)

            recognizer = getattr(self.controller, 'recognizer', None)
            if recognizer and hasattr(recognizer, 'rms_signal'):
                recognizer.rms_signal.connect(self.voice_indicator.update_wave)

            self.controller.microphone_changed.connect(self._update_microphone_display)

            # Update the UI with the current state of the new controller
            self.mode_controls.update_state(
                getattr(self.controller, 'running', False),
                getattr(recognizer, 'mode', None)
            )
            self._update_microphone_display(self.controller.device_name)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0) # Remove margins from the main layout
        layout.setSpacing(0) # Remove spacing between widgets

        # Speech indicator - animated wave
        self.voice_indicator = WaveformWidget()
        self.voice_indicator.setVisible(self.show_waveform)
        self.voice_indicator.setMinimumHeight(int(self.base_waveform_height * self.scale))
        self.voice_indicator.setMaximumHeight(int(self.base_waveform_height * self.scale))
        layout.addWidget(self.voice_indicator)

        # Control panel
        control_panel = QFrame()
        control_panel.setObjectName("ControlPanel")
        top_controls_layout = QHBoxLayout(control_panel)
        top_controls_layout.setContentsMargins(8, 8, 8, 8) # Internal panel margins

        # Get mode colors from settings
        tray_colors = self.settings_manager.get('tray_color', {})
        # Mode control widget with color transfer
        self.mode_controls = ModeControlWidget(
            self.texts,
            self.settings_manager,
            use_icons=True,
            enable_tooltips=True,
            tray_colors=tray_colors,
            scale=self.scale,
            base_btn_mode_width=self.base_btn_mode_width,
            base_btn_mode_height=self.base_btn_height  # use the same height as for regular buttons
        )
        if hasattr(self.mode_controls, 'apply_scale'):
            self.mode_controls.apply_scale(self.scale)

        top_controls_layout.addWidget(self.mode_controls)
        top_controls_layout.addSpacing(8)

        # Microphone icon
        self.mic_btn = QPushButton()
        self.mic_btn.setIconSize(QSize(int(self.base_btn_ico_width * self.scale), int(self.base_btn_ico_height * self.scale)))
        self.mic_btn.setFixedSize(int(self.base_btn_width * self.scale), int(self.base_btn_height * self.scale))
        self.mic_btn.setToolTip(self.texts.get('mics_not_found', 'No microphones found')) # default tooltip
        top_controls_layout.addWidget(self.mic_btn)

        # List of microphones (hidden)
        self.mic_combo = QComboBox(self)
        self.mic_combo.setMinimumWidth(int(180 * self.scale))
        self.mic_combo.hide()
        # Add QComboBox right after the microphone button
        top_controls_layout.addWidget(self.mic_combo)

        # Model icon
        self.model_btn = QPushButton()
        self.model_btn.setIconSize(QSize(int(self.base_btn_ico_width * self.scale), int(self.base_btn_ico_height * self.scale)))
        self.model_btn.setFixedSize(int(self.base_btn_width * self.scale), int(self.base_btn_height * self.scale))
        self.model_btn.setToolTip(self.texts.get('no_models', 'No models found')) # default tooltip
        top_controls_layout.addWidget(self.model_btn)

        # List of models (hidden)
        self.model_combo = QComboBox(self)
        self.model_combo.setMinimumWidth(int(220 * self.scale))
        self.model_combo.hide()
        # Add QComboBox right after the model button
        top_controls_layout.addWidget(self.model_combo)

        # Settings gear button - now in the common row
        self.settings_btn = QPushButton()
        self.settings_btn.setToolTip(self.texts.get('open_settings', 'Open settings'))
        self.settings_btn.setIconSize(QSize(int(self.base_btn_ico_width * self.scale), int(self.base_btn_ico_height * self.scale)))
        self.settings_btn.setFixedSize(int(self.base_btn_width * self.scale), int(self.base_btn_height * self.scale))
        self.settings_btn.clicked.connect(self._on_settings_clicked)
        top_controls_layout.addSpacing(8)
        top_controls_layout.addWidget(self.settings_btn)

        top_controls_layout.addStretch()
        layout.addWidget(control_panel)

        self.mode_controls.transcribe_clicked.connect(self._on_transcribe_clicked)
        self.mode_controls.command_clicked.connect(self._on_command_clicked)

        # Signals to show lists over icons
        self.mic_btn.clicked.connect(self._show_mic_combo)
        self.model_btn.clicked.connect(self._show_model_combo)

        # Signals for tooltips
        self.mic_btn.enterEvent = self._mic_btn_hover_event
        self.model_btn.enterEvent = self._model_btn_hover_event

        # Filling and connecting signals for QComboBox
        self._fill_microphones()
        self.mic_combo.currentIndexChanged.connect(self._on_microphone_changed)
        self._fill_models()
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)

    def _show_mic_combo(self):
        if self.mic_combo.count() == 0:
            return

        menu = QMenu(self)
        current_index = self.mic_combo.currentIndex()

        for i in range(self.mic_combo.count()):
            text = self.mic_combo.itemText(i)
            action = menu.addAction(text)
            action.setCheckable(True)
            if i == current_index:
                action.setChecked(True)
            action.triggered.connect(lambda checked=False, index=i: self.mic_combo.setCurrentIndex(index))

        # Center menu
        menu_width = menu.sizeHint().width()
        button_width = self.mic_btn.width()
        button_pos = self.mic_btn.mapToGlobal(self.mic_btn.rect().bottomLeft())

        new_x = button_pos.x() - (menu_width / 2) + (button_width / 2)
        new_pos = QPoint(int(new_x), button_pos.y())

        menu.exec_(new_pos)

    def _show_model_combo(self):
        if self.model_combo.count() == 0:
            return

        menu = QMenu(self)
        current_index = self.model_combo.currentIndex()

        for i in range(self.model_combo.count()):
            text = self.model_combo.itemText(i)
            action = menu.addAction(text)
            action.setCheckable(True)
            if i == current_index:
                action.setChecked(True)
            action.triggered.connect(lambda checked=False, index=i: self.model_combo.setCurrentIndex(index))

        # Center menu
        menu_width = menu.sizeHint().width()
        button_width = self.model_btn.width()
        button_pos = self.model_btn.mapToGlobal(self.model_btn.rect().bottomLeft())

        new_x = button_pos.x() - (menu_width / 2) + (button_width / 2)
        new_pos = QPoint(int(new_x), button_pos.y())

        menu.exec_(new_pos)

    def _mic_btn_hover_event(self, event):
        # Show tooltip with current microphone
        self.mic_btn.setToolTip(self.mic_combo.currentText())
        QPushButton.enterEvent(self.mic_btn, event)

    def _model_btn_hover_event(self, event):
        # Show tooltip with current model
        self.model_btn.setToolTip(self.model_combo.currentText())
        QPushButton.enterEvent(self.model_btn, event)

    def _on_microphone_changed(self, idx):
        """Sends a command to the controller to change the microphone."""
        mic_name = self.mic_combo.currentText()
        if self.controller and mic_name:
            self.controller.change_microphone(mic_name)

    def _update_microphone_display(self, device_name):
        """Slot to update the microphone display in the QComboBox."""
        self.mic_combo.blockSignals(True)
        index = self.mic_combo.findText(device_name)
        if index != -1:
            self.mic_combo.setCurrentIndex(index)
            self.mic_btn.setToolTip(device_name)
        self.mic_combo.blockSignals(False)

    def _on_model_changed(self, idx):
        # Universal model change handler
        data = self.model_combo.itemData(idx)
        if data:
            model_name, lang = data
            label = f"{model_name} ({lang})"
            logger.info(f"[MainVoiceWindow] Model changed in UI: {model_name} ({lang}). Saving to settings.")
            self.settings_manager.set_many({
                'current_model': model_name,
                'language': lang
            })
            self.model_btn.setToolTip(label)

    def _fill_microphones(self):
        self.mic_combo.blockSignals(True)
        try:
            self.mic_combo.clear()
            from scribe.audio_devices import AudioDevices
            devices = AudioDevices.get_input_devices(wasapi_only=True)
            if not devices:
                self.mic_combo.addItem(self.texts.get('mics_not_found', 'No microphones found'))
                self.mic_combo.setEnabled(False)
                self.mic_btn.setToolTip(self.texts.get('mics_not_found', 'No microphones found'))
            else:
                self.mic_combo.addItems(devices)
                if devices:
                    self.mic_btn.setToolTip(devices[0])
        except Exception as e:
            self.mic_combo.addItem(self.texts.get('mics_error', 'Error getting microphones'))
            self.mic_combo.setEnabled(False)
            self.mic_btn.setToolTip(self.texts.get('mics_error', 'Error getting microphones'))
            logger.error(f"Error filling microphones: {e}")
        finally:
            self.mic_combo.blockSignals(False)

    def _fill_models(self):
        self.model_combo.blockSignals(True)
        try:
            self.model_combo.clear()
            models_dict = self.settings_manager.get('models', {})
            current_model = self.settings_manager.get('current_model')
            current_lang = self.settings_manager.get('language')
            if not models_dict:
                self.model_combo.addItem(self.texts.get('no_models', 'No models found'))
                self.model_combo.setEnabled(False)
                self.model_btn.setToolTip(self.texts.get('no_models', 'No models found'))
            else:
                for lang, lang_models in models_dict.items():
                    for model in lang_models:
                        model_name = model.get('name')
                        label = f"{model_name} ({lang})"
                        self.model_combo.addItem(label, (model_name, lang))
                if current_model and current_lang:
                    for i in range(self.model_combo.count()):
                        data = self.model_combo.itemData(i)
                        if data == (current_model, current_lang):
                            self.model_combo.setCurrentIndex(i)
                            self.model_btn.setToolTip(self.model_combo.currentText())
                            break
                elif self.model_combo.count() > 0:
                    self.model_btn.setToolTip(self.model_combo.currentText())
        except Exception as e:
            self.model_combo.addItem(self.texts.get('models_error', 'Error getting models'))
            self.model_combo.setEnabled(False)
            self.model_btn.setToolTip(self.texts.get('models_error', 'Error getting models'))
            logger.error(f"Error filling models: {e}")
        finally:
            self.model_combo.blockSignals(False)

    def _on_transcribe_clicked(self):
        if self.controller:
            self.controller.switch_to_transcribe_mode()

    def _on_command_clicked(self):
        if self.controller:
            self.controller.switch_to_command_mode()

    def _on_settings_clicked(self):
        if self.tray_app:
            self.tray_app.show_settings()

    def apply_window_settings(self):
        """Applies window settings: always on top and close behavior."""
        settings = self.settings_manager.all()
        main_window_settings = settings.get('main_window', {})
        always_on_top = main_window_settings.get('always_on_top', False)
        close_behavior = main_window_settings.get('close_behavior', 'tray')

        flags = self.windowFlags()
        if always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)

        self._close_behavior = close_behavior
        self.show()

    def programmatic_close(self):
        """Closes the window programmatically, bypassing user-defined close behavior."""
        self._is_programmatic_close = True
        self.close()

    def closeEvent(self, event):
        """Handles window close event according to settings."""
        if self._is_programmatic_close:
            event.accept()
            return

        if hasattr(self, '_close_behavior'):
            if self._close_behavior == 'tray':
                # Save window position before hiding
                pos = self.pos()
                main_window_settings = self.settings_manager.get('main_window', {})
                main_window_settings['position'] = {'x': pos.x(), 'y': pos.y()}
                self.settings_manager.set('main_window', main_window_settings)
                logger.info(f"Saved main window position on close: {pos.x()}, {pos.y()}")
                event.ignore()
                self.hide()
            elif self._close_behavior == 'exit':
                self.tray_app.exit_app()
                event.accept()
        else:
            # Default behavior if _close_behavior is not set (e.g., on first run)
            event.accept()

    def showEvent(self, event):
        """Restores position and applies scale when showing the window."""
        # Forcibly apply scale every time the window is shown.
        # This solves the problem with incorrect layout on first launch,
        # when the window is initialized with a small size.
        if hasattr(self, 'scale'):
            self._apply_scale()

        main_window_settings = self.settings_manager.get('main_window', {})
        position = main_window_settings.get('position')
        if position and 'x' in position and 'y' in position:
            self.move(position['x'], position['y'])

        super().showEvent(event)
