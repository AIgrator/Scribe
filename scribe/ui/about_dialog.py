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
        version_label = QLabel("1.0.0") # TODO: Get version dynamically
        author_label = QLabel("Litovchenko Yaroslav")
        repo_url = "https://github.com/AIgrator/Scribe"
        repo_label = QLabel(f'<a href="{repo_url}">{repo_url}</a>')
        repo_label.setOpenExternalLinks(True)
        form_layout.addRow(self.texts.get('about_version', 'Version:'), version_label)
        form_layout.addRow(self.texts.get('about_author', 'Author:'), author_label)
        form_layout.addRow(self.texts.get('about_source_code', 'Source Code:'), repo_label)
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
            "<p>Copyright (C) 2025 Litovchenko Yaroslav</p>"
            "<p>This program is free software: you can redistribute it and/or modify it under the terms of the "
            "GNU General Public License as published by the Free Software Foundation, either version 3 of the "
            "License, or (at your option) any later version.</p>"
            "<p>This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; "
            "without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. "
            "See the GNU General Public License for more details.</p>"
            "<p>You should have received a copy of the GNU General Public License along with this program. "
            "If not, see <a href=\"http://www.gnu.org/licenses/\">http://www.gnu.org/licenses/</a>.</p>"
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
        self.setFixedSize(520, 310)
