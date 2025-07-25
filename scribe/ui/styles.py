# ui/styles.py
import sys

LIGHT_THEME_STYLESHEET = """
#MainVoiceWindow {
    background-color: #ffffff;
}
#ControlPanel {
    background-color: #f0f0f0;
    border-top: 1px solid #dcdcdc;
}
#ControlPanel QPushButton {
    background-color: #f0f0f0;
    color: #000;
    border: 1px solid #adadad;
}
#ControlPanel QPushButton:hover {
    background-color: #e1e1e1;
}
#ControlPanel QPushButton:pressed {
    background-color: #d1d1d1;
}
#ControlPanel QPushButton:!text {
    border: none;
    padding: 0;
}
"""

DARK_THEME_STYLESHEET = """
#MainVoiceWindow {
    background-color: #2e2e2e;
}
#ControlPanel {
    background-color: #383838;
    border-top: 1px solid #4a4a4a;
}
#ControlPanel QPushButton {
    background-color: #505050;
    color: #e0e0e0;
    border: 1px solid #6a6a6a;
}
#ControlPanel QPushButton:hover {
    background-color: #606060;
}
#ControlPanel QPushButton:pressed {
    background-color: #707070;
}
#ControlPanel QPushButton:!text {
    border: none;
    padding: 0;
}
"""

# Common styles that do not depend on the theme, but are needed by the application
DEFAULT_APP_STYLE = """
QToolTip {
    color: #000000;
    background-color: #f5f5dc;
    border: 1px solid #a9a9a9;
}
QGroupBox {
    font-weight: bold;
    border: 2px solid #222;
    border-radius: 8px;
    margin-top: 5px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 5px;
    top: -3px;
}
"""

# Style for the hotkey input field in recording mode
HOTKEY_RECORDING_STYLE = "background-color: #e0f0ff;"

# Style for warning labels
WARNING_LABEL_STYLE = 'color: #c00; font-weight: bold; padding: 8px 8px; border: 1.5px solid #c00; border-radius: 6px; background: #fff6f6;'

# Style for small gray hints
HINT_LABEL_STYLE = 'color: #888; font-size: 10px;'


def get_active_mode_style(color_rgb, text_color_rgb=(255, 255, 255)):
    """Returns the style for the active mode button."""
    return (
        f"background-color: rgb({color_rgb[0]},{color_rgb[1]},{color_rgb[2]}); "
        f"color: rgb({text_color_rgb[0]},{text_color_rgb[1]},{text_color_rgb[2]}); "
        "font-weight: bold;"
        "border: none;"
        "padding: 0;"
    )


def get_table_style():
    """Returns the style for QTableWidget."""
    return """
        QTableWidget {
            gridline-color: #d0d0d0;
            background-color: #ffffff;
        }
        QHeaderView::section {
            background-color: #f0f0f0;
            padding: 4px;
            border: 1px solid #d0d0d0;
            font-weight: bold;
        }
        QTableWidget::item {
            padding: 5px;
        }
        QTableWidget::item:selected {
            background-color: #a8d8ff;
            color: #000000;
        }
    """

def is_system_in_dark_mode():
    """Checks if the system is using a dark theme. Works only on Windows. Returns False for other OSes."""
    if sys.platform == 'win32':
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize')
            value, _ = winreg.QueryValueEx(key, 'AppsUseLightTheme')
            return value == 0
        except (ImportError, FileNotFoundError, OSError):
            return False
    return False
