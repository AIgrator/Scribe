# ui/busy_dialog.py

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QMovie
from PyQt5.QtWidgets import QDialog, QLabel, QVBoxLayout

from scribe.utils import resource_path


class BusyDialog(QDialog):
    def __init__(self, parent=None, texts=None, title=None):
        super().__init__(parent)
        self.texts = texts
        # Use the provided title, or fall back to the default
        window_title = title or self.texts.get('busy_loading_model', 'Loading model in RAM, please wait...')
        self.setWindowTitle(window_title)

        layout = QVBoxLayout(self)

        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet('background: transparent;')

        gif_label = QLabel()
        gif_label.setAlignment(Qt.AlignCenter)
        gif_label.setStyleSheet('background: transparent;')
        movie = QMovie(resource_path("resources/loading.gif"))
        gif_label.setMovie(movie)
        movie.start()
        layout.addWidget(gif_label)
        self.setModal(True)
