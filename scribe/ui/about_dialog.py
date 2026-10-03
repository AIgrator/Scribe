# scribe/ui/about_dialog.py
import logging

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QTextEdit, QVBoxLayout

from scribe.utils import resource_path

logger = logging.getLogger(__name__)


class AboutDialog(QDialog):
    """'About' dialog window with a detailed, scrollable license view."""

    def __init__(self, texts, parent=None):
        super().__init__(parent)
        self.texts = texts
        self.setWindowTitle(self.texts.get('about_title', 'About Scribe'))
        self.setWindowIcon(QIcon(resource_path('resources/icon.ico')))

        main_layout = QVBoxLayout(self)

        # --- Top Section: Icon + Info ---
        top_section_layout = QHBoxLayout()
        top_section_layout.setContentsMargins(10, 10, 10, 10)

        icon_label = QLabel()
        pixmap = QPixmap(resource_path('resources/scribe.png'))
        if not pixmap.isNull():
            icon_label.setPixmap(pixmap.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon_label.setAlignment(Qt.AlignTop)
        top_section_layout.addWidget(icon_label)

        info_layout = QVBoxLayout()
        name_label = QLabel("Scribe")
        font = name_label.font()
        font.setPointSize(16)
        font.setBold(True)
        info_layout.addWidget(name_label)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)  # Removed top margin to reduce space
        version_label = QLabel("1.3.0")
        author_label = QLabel("Yaroslav Litovchenko")
        email_url = "mailto:aigrator@gmail.com"
        email_label = QLabel(f'<a href="{email_url}">aigrator@gmail.com</a>')
        email_label.setOpenExternalLinks(True)
        repo_url = "https://github.com/AIgrator/Scribe"
        repo_label = QLabel(f'<a href="{repo_url}">github.com/AIgrator/Scribe</a>')
        repo_label.setOpenExternalLinks(True)
        home_url = "https://aigrator-scribe.sourceforge.net"
        home_label = QLabel(f'<a href="{home_url}">aigrator-scribe.sourceforge.net</a>')
        home_label.setOpenExternalLinks(True)
        bugs_url = "https://github.com/AIgrator/Scribe/issues"
        bugs_label = QLabel(f'<a href="{bugs_url}">github.com/AIgrator/Scribe/issues</a>')
        bugs_label.setOpenExternalLinks(True)
        license_label = QLabel("MIT")
        form_layout.addRow(self.texts.get('about_version', 'Version:'), version_label)
        form_layout.addRow(self.texts.get('about_author', 'Author:'), author_label)
        form_layout.addRow(self.texts.get('about_email', 'Email:'), email_label)
        form_layout.addRow(self.texts.get('about_github', 'GitHub page:'), repo_label)
        form_layout.addRow(self.texts.get('about_home', 'Home page:'), home_label)
        form_layout.addRow(self.texts.get('about_bugs', 'Bugs/Suggestions:'), bugs_label)
        form_layout.addRow(self.texts.get('about_license', 'License:'), license_label)
        info_layout.addLayout(form_layout)

        # Add stretch to push the info content to the top
        info_layout.addStretch()

        top_section_layout.addLayout(info_layout)
        top_section_layout.addStretch()
        main_layout.addLayout(top_section_layout)

        # --- Scrollable License Text ---
        license_text_area = QTextEdit()
        license_text_area.setReadOnly(True)
        license_text_area.setFixedHeight(120) # Adjusted height

        license_text = (
            "<p>Copyright (c) 2026 Yaroslav Litovchenko</p>"
            "<p>Permission is hereby granted, free of charge, to any person obtaining a copy "
            "of this software and associated documentation files (the \"Software\"), to deal "
            "in the Software without restriction, including without limitation the rights "
            "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell "
            "copies of the Software, and to permit persons to whom the Software is "
            "furnished to do so, subject to the following conditions:</p>"
            "<p>The above copyright notice and this permission notice shall be included in all "
            "copies or substantial portions of the Software.</p>"
            "<p>THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR "
            "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, "
            "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE "
            "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER "
            "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, "
            "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE "
            "SOFTWARE.</p>"
        )
        license_text_area.setHtml(license_text)
        main_layout.addWidget(license_text_area)

        # Add some spacing before the button
        main_layout.addSpacing(10)

        # --- Bottom Section: Button (Right-aligned) ---
        button_layout = QHBoxLayout()
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.button(QDialogButtonBox.Ok).setText(self.texts.get('ok', 'OK'))
        buttons.accepted.connect(self.accept)
        button_layout.addStretch(1)
        button_layout.addWidget(buttons)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)
        self.setFixedSize(520, 430)
