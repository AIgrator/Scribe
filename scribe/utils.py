# utils.py
import os
import platform
import sys


def get_app_data_path(app_name="Scribe"):
    """Get the path to the application data directory for the current OS."""
    system = platform.system()
    if system == 'Windows':
        path = os.getenv('APPDATA')
        if path is None:
            path = os.path.expanduser('~')
    elif system == 'Darwin':  # macOS
        path = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support')
    else:  # Linux and other Unix-like
        path = os.getenv('XDG_DATA_HOME', os.path.join(os.path.expanduser('~'), '.local', 'share'))

    app_path = os.path.join(path, app_name)

    if not os.path.exists(app_path):
        os.makedirs(app_path, exist_ok=True)

    return app_path


def get_models_path():
    """Get the absolute path to the models directory.

    - If frozen (PyInstaller), it's a 'models' folder next to the executable.
    - If running from source, it's a 'models' folder in the project root.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Path for bundled app
        if platform.system() == 'Windows':
            import ctypes
            # On Windows, use the Win32 API for a Unicode-safe path.
            buffer = ctypes.create_unicode_buffer(260)  # MAX_PATH
            ctypes.windll.kernel32.GetModuleFileNameW(None, buffer, 260)
            base_path = os.path.dirname(buffer.value)
        else:
            # Fallback for other systems like Linux or macOS
            base_path = os.path.dirname(os.path.abspath(sys.executable))
    else:
        # Path for development (running from source)
        base_path = os.path.abspath(".")

    models_path = os.path.join(base_path, 'models')

    # Ensure the directory exists
    os.makedirs(models_path, exist_ok=True)

    return models_path


def get_specific_model_path(language, model_name):
    """Constructs and verifies the absolute path to a specific model directory.

    Args:
        language (str): The language of the model (e.g., 'en').
        model_name (str): The name of the model folder.

    Returns:
        str or None: The absolute, verified path to the model, or None if it's invalid.

    """
    if not all([language, model_name]):
        return None

    models_dir = get_models_path()

    # Construct the potential path and normalize it.
    candidate_path = os.path.abspath(os.path.join(models_dir, language, model_name))

    # Verify that it's a valid model directory by checking for a key file.
    if os.path.exists(os.path.join(candidate_path, 'am', 'final.mdl')):
        return candidate_path

    return None


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)
