"""Entry point for development: launches the main Scribe application."""
import logging
import os
import sys

# NOTE: onnxruntime must be imported BEFORE PyQt5 on Windows, otherwise its
# native DLL fails to load (Qt DLLs shadow the MSVC runtime it needs).
# The import is optional — the app works without it (rules-only punctuation).
# DLL lookup: point Windows at the bundled onnxruntime dir first (frozen),
# same chdir idea the app already uses for non-ASCII model paths.
try:
    import ctypes as _ct0  # noqa: F401  (kept for _pin below)
except Exception:
    pass

try:
    import os as _os
    import sys as _sys

    def _pin(_dlldir, _names):
        # Load exact bundled binaries by full path: no search order involved,
        # the loaded module is then reused by every dependent DLL.
        try:
            import ctypes as _ct
        except Exception:
            return
        for _n in _names:
            try:
                _p = _os.path.join(_dlldir, _n)
                if _os.path.exists(_p):
                    _ct.WinDLL(_p)
            except Exception:
                pass

    _mei = getattr(_sys, '_MEIPASS', None)
    if _mei:
        # Pinned MSVC runtime first: the bundled copy must win over any
        # older system/3rd-party one (e.g. Qt's 14.26 or inbox copies).
        _pin(_mei, ('vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140.dll', 'msvcp140_1.dll'))
    _candidates = []
    if _mei:
        _candidates.append(_mei)
        _candidates.append(_os.path.join(_mei, 'onnxruntime', 'capi'))
    for _d in _candidates:
        try:
            if _d and _os.path.isdir(_d):
                _os.add_dll_directory(_d)
        except Exception:
            pass
    # Deterministic preload by full path: bypasses DLL search order entirely
    # (frozen onefile extracts to a temp dir that is not on the search path).
    # Plus PATH prepend: the oldest mechanism, picked up by every loader.
    _preloaded = False
    for _d in _candidates:
        try:
            if _d and _os.path.isdir(_d):
                _os.environ['PATH'] = _d + _os.pathsep + _os.environ.get('PATH', '')
        except Exception:
            pass
    for _d in _candidates:
        try:
            _main = _os.path.join(_d, 'onnxruntime.dll')
            if _d and _os.path.exists(_main):
                import ctypes as _ct
                _ct.WinDLL(_main)
                _preloaded = True
                break
        except Exception:
            pass
    import onnxruntime  # noqa: F401
except Exception:
    pass

# Check if running under Wayland and set QT_QPA_PLATFORM accordingly
if os.environ.get('XDG_SESSION_TYPE') == 'wayland':
    #os.environ['QT_QPA_PLATFORM'] = 'wayland'
    print("Not work under Wayland yet.")
    exit(1)

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from scribe.app_initializer import initialize_app
from scribe.application import Application
from scribe.logging_config import setup_logging
from scribe.ui.styles import DEFAULT_APP_STYLE
from scribe.utils import get_data_dir, get_models_path, migrate_data_dir, resource_path

if __name__ == '__main__':
    # Set AppUserModelID for correct icon display in the Windows taskbar
    if sys.platform == 'win32':
        import ctypes
        myappid = 'Scribe.1' # any unique ID
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    # Create QApplication before any Qt widgets!
    qt_app = QApplication(sys.argv)
    qt_app.setWindowIcon(QIcon(resource_path('resources/icon.ico')))

    # Load and apply global styles
    qt_app.setStyleSheet(DEFAULT_APP_STYLE)
    # Centralized initialization: settings, language, translations, model path, etc.
    # All mutable data lives in one absolute directory (see get_data_dir):
    # %LOCALAPPDATA%\Scribe for an installed build, the exe folder when
    # portable.flag is present, the repository root when running from source.
    # Migration from older layouts runs once, before anything creates models/.
    data_dir = get_data_dir()
    migrated = migrate_data_dir(data_dir)
    settings_path = os.path.join(data_dir, 'settings.json')
    models_dir = get_models_path()
    settings_manager, settings, ui_lang, texts, recognition_language, model_path = initialize_app(settings_path, models_dir)
    # Ensure the punctuation model for the recognition language is present
    # (covers existing installs updated to a version with punctuation).
    # Skipped silently when disabled, unknown language, or offline.
    try:
        from scribe.model_manager import ensure_punctuation_model
        ensure_punctuation_model(models_dir, recognition_language, texts, settings_manager)
    except Exception:
        pass
    # Setup logging with log_to_file and log_level parameters from settings.
    # The log lives in the data dir, so it never depends on the CWD.
    setup_logging(
        log_to_file=settings.get('log_to_file', False),
        log_file_path=os.path.join(data_dir, 'app.log'),
        log_level=settings.get('log_level', 'INFO')
    )
    logger = logging.getLogger(__name__)
    logger.info(f"Data dir: {data_dir}")
    for entry in migrated:
        logger.info(f"Migrated {entry}")
    # Even with file logging off, leave the resolved path in app.log: it is the
    # first thing needed to diagnose "where did my settings go".
    if not settings.get('log_to_file', False):
        try:
            with open(os.path.join(data_dir, 'app.log'), 'a', encoding='utf-8') as f:
                f.write(f"[INFO] Data dir: {data_dir}\n")
                for entry in migrated:
                    f.write(f"[INFO] Migrated {entry}\n")
        except OSError:
            pass
    # Create and run the main application object
    app = Application(settings_manager, settings, ui_lang, texts, recognition_language, model_path)
    app.run()
