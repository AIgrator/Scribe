# tray_app.py
import logging
import webbrowser

from PyQt5.QtCore import QCoreApplication, QObject, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import QAction, QActionGroup, QApplication, QMenu, QSystemTrayIcon

from scribe.audio_devices import AudioDevices
from scribe.ui.about_dialog import AboutDialog

logger = logging.getLogger(__name__)

class TrayApp(QObject):
    """Manages the system tray icon and its context menu.Delegates all actions to the main Application instance."""

    update_tray_ui_signal = pyqtSignal()

    def __init__(self, application):
        super().__init__()
        self.app = QApplication.instance()
        self.application = application
        self.texts = application.texts
        self.settings_manager = application.settings_manager
        self.about_dialog = None

        self.tray = QSystemTrayIcon()
        self.menu = QMenu()
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_tray_activated)

        self.update_tray_ui_signal.connect(self._update_tray_ui_slot)
        self._build_menu()
        self._update_tray_icon()
        self.tray.show()

    def _show_about_dialog(self):
        """Shows the 'About' dialog."""
        if not self.about_dialog:
            self.about_dialog = AboutDialog(self.texts)
        self.about_dialog.show()
        self.about_dialog.activateWindow()

    def _on_tray_activated(self, reason):
        """Handles tray icon activation events."""
        # Do nothing if a model is currently being loaded
        if getattr(self.application, 'is_loading_model', False):
            return

        if reason == QSystemTrayIcon.Trigger:  # Left-click
            main_window_settings = self.settings_manager.get('main_window', {})
            if main_window_settings.get('open_on_tray_click', True):
                self.application.show_main_window()

    def hide(self):
        """Hides the tray icon."""
        self.tray.hide()

    def update_tray_ui(self):
        """Safely updates the menu and tray icon from the main thread."""
        if QThread.currentThread() != QCoreApplication.instance().thread():
            self.update_tray_ui_signal.emit()
            return

        # This part runs only on the main thread
        self._build_menu()
        self._update_tray_icon()
        # After building the menu, ensure it's disabled if we are in a loading state.
        if getattr(self.application, 'is_loading_model', False):
            self.set_menu_enabled(False)

    def _update_tray_ui_slot(self):
        # This is the slot for cross-thread updates. It just calls the main method.
        self.update_tray_ui()

    def _update_tray_icon(self):
        """Updates the tray icon's color and tooltip based on the application state."""
        size = 32
        # Check for loading state first
        if getattr(self.application, 'is_loading_model', False):
            self.tray.setToolTip(self.texts.get('busy_loading_model', 'Loading model, please wait...'))
            pixmap = QPixmap(size, size)
            pixmap.fill(QColor(128, 128, 128))  # Gray color for loading
            painter = QPainter(pixmap)
            font = QFont('Arial', 16, QFont.Bold)
            painter.setFont(font)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(pixmap.rect(), 0x84, "...")  # 0x84 = Qt.AlignCenter
            painter.end()
            self.tray.setIcon(QIcon(pixmap))
            return  # Exit early

        settings = self.settings_manager.all()
        lang_code = settings.get('language', 'en').upper()

        tray_color_settings = settings.get('tray_color', self.settings_manager.DEFAULTS.get('tray_color', {}))
        def get_color(key, default):
            val = tray_color_settings.get(key, default)
            return QColor(*val) if isinstance(val, (list, tuple)) and len(val) == 3 else QColor(*default)

        bg_color = QColor(0, 0, 0)
        text_color = get_color('text_color', (255, 255, 255))

        mode = None
        running = False
        if self.application.controller:
            recognizer = getattr(self.application.controller, 'recognizer', None)
            running = getattr(self.application.controller, 'running', False)
            mode = getattr(recognizer, 'mode', None)

        if running:
            if mode == 'transcribe':
                bg_color = get_color('transcribe_color', (255, 106, 0))
            elif mode == 'command':
                bg_color = get_color('command_color', (72, 0, 255))

        pixmap = QPixmap(size, size)
        pixmap.fill(bg_color)
        painter = QPainter(pixmap)
        font = QFont('Arial', 16, QFont.Bold)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(pixmap.rect(), 0x84, lang_code)  # 0x84 = Qt.AlignCenter
        painter.end()
        self.tray.setIcon(QIcon(pixmap))

        # Tooltip
        model_name = settings.get('current_model', '')
        lang_full = self.texts.get(f'language_native_{lang_code.lower()}', lang_code)

        mode_str = ""
        if running:
            mode_key = f'mode_{mode}' if mode else ''
            mode_default = f'Mode: {mode}' if mode else ''
            mode_str = self.texts.get(mode_key, mode_default)

        record_str = ""
        if settings.get('transcribe_to_file', False):
            record_str = self.texts.get('recording_on', 'Recording to file: ON')

        tooltip_lines = [self.texts['app_name'], f"{lang_full} ({lang_code})", f"Model: {model_name}"]
        if mode_str:
            tooltip_lines.append(mode_str)
        if record_str:
            tooltip_lines.append(record_str)

        self.tray.setToolTip("\n".join(tooltip_lines))

    def _build_menu(self):
        """Builds or rebuilds the tray menu, connecting actions to the Application instance."""
        self.menu.clear()
        settings = self.settings_manager.all()

        # Mode Control Menu
        self._build_mode_menu(settings)

        # Model Selection Menu
        self._build_model_menu(settings)

        # Microphone Selection Menu
        self._build_mic_menu()

        self.menu.addSeparator()

        # Settings Action
        action_settings = QAction(self.texts.get('settings', 'Settings'), self.app)
        action_settings.triggered.connect(self.application.show_settings)
        self.menu.addAction(action_settings)

        # Main Window Action
        action_main_window = QAction(self.texts.get('open_main_window', 'Open main window'), self.app)
        action_main_window.triggered.connect(self.application.show_main_window)
        self.menu.addAction(action_main_window)

        # Documentation Action
        self.action_documentation = QAction(self.texts.get('documentation', 'Documentation'), self.app)
        self.action_documentation.triggered.connect(lambda: webbrowser.open('https://aigrator.github.io/Scribe/'))
        self.menu.addAction(self.action_documentation)

        self.menu.addSeparator()

        # About Action
        self.action_about = QAction(self.texts.get('about', 'About'), self.app)
        self.action_about.triggered.connect(self._show_about_dialog)
        self.menu.addAction(self.action_about)

        # Exit Action
        self.action_exit = QAction(self.texts['exit'], self.app)
        self.action_exit.triggered.connect(self.application.exit_app)
        self.menu.addAction(self.action_exit)

    def set_menu_enabled(self, enabled):
        """Enables or disables all menu items except for exceptions."""
        exceptions = [
            self.action_documentation,
            self.action_about,
            self.action_exit
        ]
        for action in self.menu.actions():
            if action not in exceptions and not action.isSeparator():
                action.setEnabled(enabled)
            # Also handle sub-menus
            if action.menu():
                for sub_action in action.menu().actions():
                    sub_action.setEnabled(enabled)

    def _build_mode_menu(self, settings):
        mode_menu = QMenu(self.texts.get('modes_control', 'Mode Control'), self.menu)

        tray_color_settings = settings.get('tray_color', self.settings_manager.DEFAULTS.get('tray_color', {}))
        def get_color(key, default):
            val = tray_color_settings.get(key, default)
            return QColor(*val) if isinstance(val, (list, tuple)) and len(val) == 3 else QColor(*default)

        transcribe_color = get_color('transcribe_color', (255, 106, 0))
        command_color = get_color('command_color', (72, 0, 255))

        current_mode = None
        running = False
        if self.application.controller:
            current_mode = getattr(self.application.controller.recognizer, 'mode', None)
            running = self.application.controller.running

        def make_color_icon(color: QColor, size=16):
            pixmap = QPixmap(size, size)
            pixmap.fill(QColor(0, 0, 0, 0))
            painter = QPainter(pixmap)
            painter.setRenderHint(painter.Antialiasing)
            painter.setBrush(color)
            painter.setPen(QColor(0, 0, 0, 0))
            painter.drawEllipse(0, 0, size-1, size-1)
            painter.end()
            return QIcon(pixmap)

        # Transcribe Action
        transcribe_active = current_mode == 'transcribe' and running
        transcribe_text = self.texts.get('transcribe_stop' if transcribe_active else 'transcribe_start')
        action_transcribe = QAction(transcribe_text, self.app, checkable=True)
        action_transcribe.setChecked(transcribe_active)
        if transcribe_active:
            action_transcribe.setIcon(make_color_icon(transcribe_color))

        def on_transcribe():
            if self.application.controller:
                if transcribe_active:
                    self.application.controller.stop()
                else:
                    self.application.controller.switch_to_transcribe_mode()
        action_transcribe.triggered.connect(on_transcribe)
        mode_menu.addAction(action_transcribe)

        # Command Action
        command_active = current_mode == 'command' and running
        command_text = self.texts.get('command_stop' if command_active else 'command_start')
        action_command = QAction(command_text, self.app, checkable=True)
        action_command.setChecked(command_active)
        if command_active:
            action_command.setIcon(make_color_icon(command_color))

        def on_command():
            if self.application.controller:
                if command_active:
                    self.application.controller.stop()
                else:
                    self.application.controller.switch_to_command_mode()
        action_command.triggered.connect(on_command)
        mode_menu.addAction(action_command)

        self.menu.addMenu(mode_menu)

    def _build_model_menu(self, settings):
        model_menu = QMenu(self.texts.get('model_select', 'Select model'), self.menu)
        model_action_group = QActionGroup(self.app)
        model_action_group.setExclusive(True)

        models_dict = settings.get('models', {})
        current_model = settings.get('current_model', None)
        current_lang = settings.get('language', 'ru')

        for lang, lang_models in models_dict.items():
            for model in lang_models:
                model_name = model.get('name')
                action = QAction(f"{model_name} ({lang})", self.app, checkable=True)
                action.triggered.connect(
                    lambda checked, n=model_name, lang_code=lang: self.application.switch_model(n, lang_code)
                )
                if model_name == current_model and lang == current_lang:
                    action.setChecked(True)
                model_action_group.addAction(action)
                model_menu.addAction(action)
        self.menu.addMenu(model_menu)

    def _build_mic_menu(self):
        mic_menu = QMenu(self.texts['mic_select'], self.menu)
        mic_action_group = QActionGroup(self.app)
        mic_action_group.setExclusive(True)

        devices = AudioDevices.get_input_devices(wasapi_only=True)
        if not devices:
            no_mic_action = QAction(self.texts['mics_not_found'], self.app)
            no_mic_action.setEnabled(False)
            mic_menu.addAction(no_mic_action)
        else:
            for device_name in devices:
                action = QAction(device_name, self.app, checkable=True)
                action.triggered.connect(
                    lambda checked, name=device_name: self.application.controller.change_microphone(name)
                )
                if self.application.controller and device_name == self.application.controller.device_name:
                    action.setChecked(True)
                mic_action_group.addAction(action)
                mic_menu.addAction(action)
        self.menu.addMenu(mic_menu)
