# application.py
import gc
import logging
import os
import sys

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QApplication, QMessageBox

from scribe.controller_loader import ControllerLoader
from scribe.hotkey_manager import HotkeyManager
from scribe.model_manager import ModelManager
from scribe.tray_app import TrayApp
from scribe.ui.busy_dialog import BusyDialog
from scribe.ui.main_voice_window import MainVoiceWindow
from scribe.ui.settings_window import SettingsWindow
from scribe.utils import get_specific_model_path

logger = logging.getLogger(__name__)


class Application(QObject):
    """The main application class that orchestrates all components.

    It owns the settings, controller, windows, and the tray icon manager.
    """

    controller_reloaded = pyqtSignal(object)

    def __init__(self, settings_manager, settings, ui_lang, texts, recognition_language, model_path):
        super().__init__()
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.app.aboutToQuit.connect(self._on_about_to_quit)

        self.settings_manager = settings_manager
        self.settings = settings
        self.ui_language = ui_lang
        self.texts = texts
        self.recognition_language = recognition_language
        self.model_path = model_path

        self.settings_manager.settings_changed.connect(self.on_settings_changed)

        self.settings_window = None
        self._main_voice_window = None
        self.controller = None
        self.hotkey_manager = None
        self._controller_loader_version = 0
        self._controller_loader = None
        self._busy_dialog = None

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        models_dir = os.path.join(base_dir, "models")
        self.model_manager = ModelManager(models_dir)
        self.inserter_type = self.settings.get('inserter_type', self.settings_manager.DEFAULTS['inserter_type'])

        # The TrayApp is now a component owned by the Application
        self.tray_app = TrayApp(self)
        self.tray_app.update_tray_ui()

        # Load the controller asynchronously
        self.load_controller_async(self.model_path, self.inserter_type)

    def _on_about_to_quit(self):
        logger.debug("Application is about to quit. Performing cleanup.")
        if hasattr(self, '_main_voice_window') and self._main_voice_window is not None:
            if self._main_voice_window.isWidgetType():
                pos = self._main_voice_window.pos()
                main_window_settings = self.settings_manager.get('main_window', {})
                main_window_settings['position'] = {'x': pos.x(), 'y': pos.y()}
                self.settings_manager.set('main_window', main_window_settings)
                logger.info(f"Saved main window position on exit: {pos.x()}, {pos.y()}")

        if self.controller:
            self.controller.stop()

        if self.tray_app:
            self.tray_app.hide()

    def reload_ui_language(self):
        self.settings = self.settings_manager.all()
        lang = self.settings.get('ui_language', 'en')
        self.texts.set_language(lang)

        self.tray_app.update_tray_ui()

        if self._main_voice_window is not None:
            self._main_voice_window.programmatic_close()
            self._main_voice_window = None

        if self.settings_window is not None:
            self.settings_window.close()
            self.settings_window = None
            self.show_settings()

    def load_controller_async(self, model_path, inserter_type):
        if self._controller_loader and self._controller_loader.isRunning():
            logger.debug('Waiting for previous ControllerLoader to finish...')
            self._controller_loader.quit()
            self._controller_loader.wait(2000)
            logger.debug('Previous ControllerLoader finished')

        self._controller_loader_version += 1
        current_version = self._controller_loader_version

        self._busy_dialog = BusyDialog(texts=self.texts)
        self._busy_dialog.show()

        loader = ControllerLoader(model_path, inserter_type, self.settings_manager)

        def on_loaded(controller, error):
            if current_version != self._controller_loader_version:
                logger.debug('Ignoring outdated ControllerLoader result.')
                return
            self._on_controller_loaded(controller, error)

        loader.finished.connect(on_loaded)
        self._controller_loader = loader
        loader.start()

    def _on_controller_loaded(self, controller, error):
        logger.info(f"Controller loading finished. Error: {error}")
        if self._busy_dialog:
            self._busy_dialog.close()

        if error:
            QMessageBox.critical(None, self.texts.get('busy_loading_model_error_title', 'Model loading error'), str(error))
            self.exit_app()
            return

        was_running = False
        if self.controller:
            logger.info("Old controller exists. Starting cleanup to prevent issues on Windows 7.")
            was_running = self.controller.running
            self.controller.stop()

            # 1. Destroy the HotkeyManager first, as it holds a strong reference to the controller.
            if self.hotkey_manager:
                logger.debug("Clearing and deleting old HotkeyManager.")
                self.hotkey_manager.clear()
                self.hotkey_manager.deleteLater()
                self.hotkey_manager = None

            # 2. Explicitly disconnect all signals from the old controller.
            logger.debug("Disconnecting all signals from old controller.")
            try:
                self.controller.microphone_changed.disconnect()
                self.controller.state_changed.disconnect()
            except (TypeError, RuntimeError) as e:
                logger.warning(f"Could not disconnect all signals from old controller: {e}")

            # 3. Remove the reference and suggest garbage collection.
            logger.debug("Deleting old controller instance.")
            del self.controller
            self.controller = None
            gc.collect()
            logger.info("Old controller cleanup complete.")

        self.controller = controller
        self.controller.microphone_changed.connect(self.tray_app.update_tray_ui)
        self.controller.state_changed.connect(self.tray_app.update_tray_ui)

        self.hotkey_manager = HotkeyManager(self.settings_manager, self.controller)
        self.model_path = self.settings.get('model_path', self.model_path)
        self.recognition_language = self.settings.get('language', self.recognition_language)

        if was_running:
            self.controller.start()
            logger.info("Restarting new controller as old one was running.")

        self.tray_app.update_tray_ui()
        self.controller_reloaded.emit(self.controller)

    def on_settings_changed(self, new_settings):
        self.settings = new_settings
        self.tray_app.update_tray_ui()

        new_inserter_type = self.settings.get('inserter_type', self.settings_manager.DEFAULTS['inserter_type'])
        new_model_name = self.settings.get('current_model', None)
        new_language = self.settings.get('language', None)

        # Use the centralized function to get the new model path
        new_model_path = get_specific_model_path(new_language, new_model_name)

        reload_model = False
        # self.model_path might be None on first run, handle this case
        current_abs_path = os.path.abspath(self.model_path) if self.model_path else None
        new_abs_path = os.path.abspath(new_model_path) if new_model_path else None

        if new_model_path and new_abs_path != current_abs_path:
            reload_model = True

        # Also reload if language changed but model path somehow didn't (e.g. same model name for different lang)
        if new_language != self.recognition_language:
            reload_model = True

        if reload_model and new_model_path:
            logger.info("Reloading controller due to model/language change.")
            self.load_controller_async(new_model_path, new_inserter_type)
        elif new_inserter_type != self.inserter_type and self.controller:
            self.inserter_type = new_inserter_type
            self.controller.set_inserter_type(self.inserter_type)

        if self.hotkey_manager:
            self.hotkey_manager.on_settings_changed(new_settings)

        if self.controller and hasattr(self.controller.recognizer, '_load_replacements'):
            self.controller.recognizer._load_replacements()

    def switch_model(self, model_name, lang):
        self.settings_manager.set_many({
            'language': lang,
            'current_model': model_name
        })

    def show_main_window(self):
        if not hasattr(self, '_main_voice_window') or self._main_voice_window is None:
            self._main_voice_window = MainVoiceWindow(self, self.controller, self.texts, self.settings_manager)
            self.controller_reloaded.connect(self._main_voice_window._on_controller_reloaded)

        window = self._main_voice_window
        settings = self.settings_manager.all()
        main_window_settings = settings.get('main_window', {})
        always_on_top = main_window_settings.get('always_on_top', False)

        from PyQt5.QtCore import Qt
        window.setWindowFlag(Qt.WindowStaysOnTopHint, always_on_top)
        window.show()
        window.activateWindow()
        window.raise_()

    def show_settings(self):
        old_lang = self.settings.get('ui_language', 'en')
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self, self.texts, self.settings_manager, parent=None)

            def on_settings_window_closed():
                new_lang = self.settings_manager.all().get('ui_language', 'en')
                if new_lang != old_lang:
                    self.reload_ui_language()
                self.settings_window = None

            self.settings_window.finished.connect(on_settings_window_closed)

        self.settings_window.show()
        self.settings_window.activateWindow()
        self.settings_window.raise_()

    def exit_app(self):
        logger.debug("Exit requested. Calling app.quit().")
        self.app.quit()

    def run(self):
        if self.settings.get('main_window', {}).get('show_on_startup', True):
            self.show_main_window()
        sys.exit(self.app.exec_())
