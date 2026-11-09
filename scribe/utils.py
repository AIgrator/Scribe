# utils.py
import logging
import os
import platform
import shutil
import sys

logger = logging.getLogger(__name__)

APP_NAME = 'Scribe'
PORTABLE_FLAG = 'portable.flag'


def get_app_data_path(app_name=APP_NAME):
    r"""Get the per-user data directory for the current OS (created if needed).

    On Windows this is %LOCALAPPDATA%\Scribe: writable without elevation and
    owned by the uninstaller. Other systems use their standard data location.
    """
    system = platform.system()
    if system == 'Windows':
        path = os.getenv('LOCALAPPDATA') or os.getenv('APPDATA')
        if path is None:
            path = os.path.expanduser('~')
    elif system == 'Darwin':  # macOS
        path = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support')
    else:  # Linux and other Unix-like
        path = os.getenv('XDG_DATA_HOME', os.path.join(os.path.expanduser('~'), '.local', 'share'))

    app_path = os.path.abspath(os.path.join(path, app_name))

    if not os.path.exists(app_path):
        os.makedirs(app_path, exist_ok=True)

    return app_path


def get_executable_dir():
    """Absolute directory of the running program.

    Frozen build: the folder that contains Scribe.exe.
    Running from source: the repository root (parent of the scribe package).
    """
    if getattr(sys, 'frozen', False):
        # Path for bundled app
        if platform.system() == 'Windows':
            import ctypes
            # On Windows, use the Win32 API for a Unicode-safe path.
            buffer = ctypes.create_unicode_buffer(260)  # MAX_PATH
            ctypes.windll.kernel32.GetModuleFileNameW(None, buffer, 260)
            return os.path.dirname(buffer.value)
        # Fallback for other systems like Linux or macOS
        return os.path.dirname(os.path.abspath(sys.executable))
    # Path for development (running from source)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_portable():
    """True when an empty portable.flag file sits next to the executable."""
    return os.path.isfile(os.path.join(get_executable_dir(), PORTABLE_FLAG))


def get_data_dir(app_name=APP_NAME):
    r"""Absolute folder for mutable data: settings, models, records and logs.

    - portable.flag next to the exe -> the exe folder (portable mode);
    - frozen build without the flag -> %LOCALAPPDATA%\Scribe (installed mode);
    - running from source -> the repository root, so dev data stays in place.
    """
    if getattr(sys, 'frozen', False) and not is_portable():
        data_dir = get_app_data_path(app_name)
    else:
        data_dir = get_executable_dir()

    data_dir = os.path.abspath(data_dir)
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _legacy_data_dirs(data_dir):
    """Folders that may contain data written by an older Scribe version."""
    data_dir = os.path.abspath(data_dir)
    candidates = [get_executable_dir()]
    if platform.system() == 'Windows':
        roaming = os.getenv('APPDATA')
        if roaming:
            candidates.append(os.path.join(roaming, APP_NAME))

    result = []
    for path in candidates:
        path = os.path.abspath(path)
        if path != data_dir and path not in result:
            result.append(path)
    return result


def _move_path(src, dst):
    """Move src to dst when dst does not exist yet. Returns True on success."""
    if os.path.exists(dst) or not os.path.exists(src):
        return False

    try:
        # Instant on the same volume, which is the normal case.
        os.replace(src, dst)
        return True
    except OSError:
        pass

    try:
        if os.path.isdir(src):
            shutil.copytree(src, dst)
            try:
                shutil.rmtree(src)
            except OSError as e:
                logger.warning(f"Migrated {src} -> {dst}, but could not remove the old copy: {e}")
        else:
            shutil.copy2(src, dst)
            try:
                os.remove(src)
            except OSError as e:
                logger.warning(f"Migrated {src} -> {dst}, but could not remove the old file: {e}")
        return True
    except Exception as e:
        logger.error(f"Failed to migrate {src} -> {dst}: {e}")
        # Do not leave a partial copy behind: it would block a retry.
        try:
            if os.path.isdir(dst):
                shutil.rmtree(dst, ignore_errors=True)
            elif os.path.exists(dst):
                os.remove(dst)
        except OSError:
            pass
        return False


def migrate_data_dir(data_dir=None):
    r"""One-time move of settings/models/records into the data directory.

    Runs only for frozen, non-portable builds and only while data_dir has no
    settings.json, so it never touches a source checkout, never steals data
    into a portable copy and never repeats. Sources are checked next to the
    executable first (the old portable layout) and then in the legacy
    %APPDATA%\Scribe folder. Returns a list of "name <- source" strings for
    logging; an empty list means nothing was migrated.
    """
    if not getattr(sys, 'frozen', False) or is_portable():
        return []

    data_dir = os.path.abspath(data_dir or get_data_dir())
    os.makedirs(data_dir, exist_ok=True)
    if os.path.exists(os.path.join(data_dir, 'settings.json')):
        return []

    migrated = []
    for name in ('settings.json', 'models', 'records'):
        dst = os.path.join(data_dir, name)
        if os.path.exists(dst):
            continue
        for source_dir in _legacy_data_dirs(data_dir):
            src = os.path.join(source_dir, name)
            if os.path.exists(src) and _move_path(src, dst):
                migrated.append(f'{name} <- {src}')
                logger.info(f"Migrated {name}: {src} -> {dst}")
                break
    return migrated


def get_models_path():
    """Get the absolute path to the models directory inside the data dir."""
    models_path = os.path.join(get_data_dir(), 'models')

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
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return os.path.join(base_path, relative_path)
