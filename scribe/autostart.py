# autostart.py
"""Manage launching Scribe automatically when the user signs in.

The installer can create the same entry, so the settings checkbox must read
and write the real OS state instead of a private settings key.
"""
import logging
import os
import sys

logger = logging.getLogger(__name__)

APP_NAME = 'Scribe'
_RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'


def _startup_command():
    """Return the command that starts this copy of Scribe."""
    if getattr(sys, 'frozen', False):
        return f'"{sys.executable}"'

    # Running from source: prefer pythonw.exe so no console window appears.
    python_exe = sys.executable
    pythonw_exe = os.path.join(os.path.dirname(python_exe), 'pythonw.exe')
    if os.path.exists(pythonw_exe):
        python_exe = pythonw_exe
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    run_script = os.path.join(project_root, 'run.py')
    return f'"{python_exe}" "{run_script}"'


def _linux_desktop_file():
    config_dir = os.getenv('XDG_CONFIG_HOME') or os.path.join(os.path.expanduser('~'), '.config')
    return os.path.join(config_dir, 'autostart', 'scribe.desktop')


def is_supported():
    """Return True if autostart can be managed on this platform."""
    return sys.platform == 'win32' or sys.platform.startswith('linux')


def is_enabled():
    """Return True if Scribe is registered to start when the user signs in."""
    if sys.platform == 'win32':
        return _windows_is_enabled()
    if sys.platform.startswith('linux'):
        return os.path.isfile(_linux_desktop_file())
    return False


def set_enabled(enabled):
    """Enable or disable autostart for the current user."""
    if sys.platform == 'win32':
        if enabled:
            _windows_enable()
        else:
            _windows_disable()
        return
    if sys.platform.startswith('linux'):
        if enabled:
            _linux_enable()
        else:
            _linux_disable()
        return
    raise OSError(f'Autostart is not supported on {sys.platform}')


def _windows_is_enabled():
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
        return True
    except FileNotFoundError:
        return False
    except OSError as e:
        logger.warning(f"Failed to read autostart registry value: {e}")
        return False


def _windows_enable():
    import winreg

    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
    ) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _startup_command())
    logger.info("Autostart enabled: %s", _startup_command())


def _windows_disable():
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, APP_NAME)
        logger.info("Autostart disabled.")
    except FileNotFoundError:
        pass


def _linux_enable():
    desktop_file = _linux_desktop_file()
    os.makedirs(os.path.dirname(desktop_file), exist_ok=True)
    with open(desktop_file, 'w', encoding='utf-8') as f:
        f.write(
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={APP_NAME}\n"
            f"Exec={_startup_command()}\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n"
        )
    logger.info("Autostart enabled: %s", desktop_file)


def _linux_disable():
    desktop_file = _linux_desktop_file()
    try:
        os.remove(desktop_file)
        logger.info("Autostart disabled: %s", desktop_file)
    except FileNotFoundError:
        pass
