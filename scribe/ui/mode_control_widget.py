# ui/mode_control_widget.py
from PyQt5.QtCore import QSize, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QHBoxLayout, QPushButton, QWidget

from scribe.ui.styles import get_active_mode_style
from scribe.utils import resource_path


class ModeControlWidget(QWidget):
    def apply_scale(self, scale):
        """Applies scaling to buttons and icons (only if use_icons)."""
        self.scale = scale
        if self.use_icons:
            base_btn_width = self.base_btn_mode_width
            base_btn_height = self.base_btn_mode_height
            base_icon_width = 128 # Base icon width, can be moved to settings
            base_icon_height = 64 # Base icon height, can be moved to settings
            btn_width = int(base_btn_width * self.scale)
            btn_height = int(base_btn_height * self.scale)
            icon_width = int(base_icon_width * self.scale)
            icon_height = int(base_icon_height * self.scale)
            self.transcribe_btn.setIconSize(QSize(icon_width, icon_height))
            self.transcribe_btn.setFixedSize(btn_width, btn_height)
            self.command_btn.setIconSize(QSize(icon_width, icon_height))
            self.command_btn.setFixedSize(btn_width, btn_height)
    """
    A reusable widget containing transcription and command mode buttons
    and the logic to update their state and style.
    """
    transcribe_clicked = pyqtSignal()
    command_clicked = pyqtSignal()


    def __init__(
        self,
        texts,
        settings_manager,
        use_icons=False,
        enable_tooltips=False,
        tray_colors=None,
        parent=None,
        scale=None,
        base_btn_mode_width=150,
        base_btn_mode_height=75
    ):
        super().__init__(parent)
        self.texts = texts
        self.settings_manager = settings_manager
        self.use_icons = use_icons
        self.enable_tooltips = enable_tooltips
        self.tray_colors = tray_colors if tray_colors is not None else {}
        self.scale = scale
        self.base_btn_mode_width = base_btn_mode_width
        self.base_btn_mode_height = base_btn_mode_height
        self.current_theme = 'light'  # default theme

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.transcribe_btn = QPushButton()
        self.command_btn = QPushButton()

        if not self.use_icons:
            self.transcribe_btn.setMinimumWidth(140)
            self.command_btn.setMinimumWidth(140)
            self.transcribe_btn.setText(self.texts.get('transcribe_start'))
            self.command_btn.setText(self.texts.get('command_start'))
            h = self.transcribe_btn.sizeHint().height()
            if h > 0:
                self.transcribe_btn.setFixedHeight(h)
                self.command_btn.setFixedHeight(h)
        else:
            self.update_theme(self.current_theme) # Set initial icons
            # Apply scaling immediately after setting icons
            self.apply_scale(self.scale if self.scale is not None else 1.0)
            self.transcribe_btn.setToolTip(self.texts.get('transcribe_start'))
            self.command_btn.setToolTip(self.texts.get('command_start'))

        # Set style for tooltip if tooltips are enabled
        if self.enable_tooltips:
            pass # The style for QToolTip is now set globally

        self.transcribe_btn.clicked.connect(self.transcribe_clicked.emit)
        self.command_btn.clicked.connect(self.command_clicked.emit)

        layout.addWidget(self.transcribe_btn)
        layout.addWidget(self.command_btn)

    def update_theme(self, theme):
        """Updates icons based on the selected theme."""
        self.current_theme = theme
        if not self.use_icons:
            return

        if self.current_theme == 'dark':
            self.transcribe_icon = QIcon(resource_path('resources/transcribe_white.png'))
            self.command_icon = QIcon(resource_path('resources/command_white.png'))
        else:
            self.transcribe_icon = QIcon(resource_path('resources/transcribe.png'))
            self.command_icon = QIcon(resource_path('resources/command.png'))

        self.transcribe_btn.setIcon(self.transcribe_icon)
        self.command_btn.setIcon(self.command_icon)


    def update_state(self, running, mode):
        """Updates button text and style based on recognition state."""
        tray_color = self.tray_colors

        # Get colors from settings
        transcribe_color = tray_color.get('transcribe_color', (255, 106, 0))
        command_color = tray_color.get('command_color', (72, 0, 255))
        text_color = tray_color.get('text_color', (255, 255, 255))

        # Generate styles through a centralized function
        transcribe_active_style = get_active_mode_style(transcribe_color, text_color)
        command_active_style = get_active_mode_style(command_color, text_color)

        is_transcribe_active = running and mode == 'transcribe'
        transcribe_text = self.texts.get('transcribe_stop' if is_transcribe_active else 'transcribe_start')
        if not self.use_icons:
            self.transcribe_btn.setText(transcribe_text)
        if self.enable_tooltips:
            self.transcribe_btn.setToolTip(transcribe_text)

        if is_transcribe_active:
            self.transcribe_btn.setStyleSheet(transcribe_active_style)
        else:
            self.transcribe_btn.setStyleSheet("") # Reset to global style

        is_command_active = running and mode == 'command'
        command_text = self.texts.get('command_stop' if is_command_active else 'command_start')
        if not self.use_icons:
            self.command_btn.setText(command_text)
        if self.enable_tooltips:
            self.command_btn.setToolTip(command_text)

        if is_command_active:
            self.command_btn.setStyleSheet(command_active_style)
        else:
            self.command_btn.setStyleSheet("") # Reset to global style

        # Forcibly reset the button size after changing the style,
        # to avoid their "compression" in small mode.
        if self.use_icons and self.scale is not None:
            btn_width = int(self.base_btn_mode_width * self.scale)
            btn_height = int(self.base_btn_mode_height * self.scale)
            self.transcribe_btn.setFixedSize(btn_width, btn_height)
            self.command_btn.setFixedSize(btn_width, btn_height)
