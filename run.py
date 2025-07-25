"""Entry point for development: launches the main Scribe application."""
import os
import sys

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from scribe.app_initializer import initialize_app
from scribe.application import Application
from scribe.logging_config import setup_logging
from scribe.ui.styles import DEFAULT_APP_STYLE
from scribe.utils import get_app_data_path, get_models_path

if __name__ == '__main__':
    # Set AppUserModelID for correct icon display in the Windows taskbar
    if sys.platform == 'win32':
        import ctypes
        myappid = 'Scribe.1' # any unique ID
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    # Create QApplication before any Qt widgets!
    qt_app = QApplication(sys.argv)
    qt_app.setWindowIcon(QIcon('resources/icon.ico'))

    # Load and apply global styles
    qt_app.setStyleSheet(DEFAULT_APP_STYLE)
    # Centralized initialization: settings, language, translations, model path, etc.
    app_data_path = get_app_data_path()
    settings_path = os.path.join(app_data_path, 'settings.json')
    models_dir = get_models_path()
    settings_manager, settings, ui_lang, texts, recognition_language, model_path = initialize_app(settings_path, models_dir)
    # Setup logging with log_to_file and log_level parameters from settings
    setup_logging(
        log_to_file=settings.get('log_to_file', False),
        log_level=settings.get('log_level', 'INFO')
    )
    # Create and run the main application object
    app = Application(settings_manager, settings, ui_lang, texts, recognition_language, model_path)
    app.run()
