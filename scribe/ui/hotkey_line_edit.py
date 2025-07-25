# ui/hotkey_line_edit.py
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QToolButton, QVBoxLayout

from scribe.ui.styles import HOTKEY_RECORDING_STYLE


class HotkeyLineEdit(QLineEdit):
    """Hotkey input field with a button for manual selection via dialog."""

    def __init__(self, texts, hotkey="", parent=None):
        super().__init__(parent)
        self.texts = texts
        self.hotkey_sequence = None
        self.set_hotkey(hotkey)
        self.setReadOnly(True)
        self.setAlignment(Qt.AlignCenter)
        self._is_recording = False
        # Button with three dots
        self.button = QToolButton(self)
        self.button.setText("…")
        self.button.setCursor(Qt.PointingHandCursor)
        self.button.setToolTip(self.texts.get('hotkey_choose_dialog', 'Choose a combination…'))
        self.button.setFixedWidth(22)
        self.button.clicked.connect(self.open_hotkey_dialog)
        self.setTextMargins(0, 0, self.button.width(), 0)
        self.button.move(self.rect().right() - self.button.width(), 0)
        self.button.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.button.move(self.rect().right() - self.button.width(), 0)

    def set_hotkey(self, sequence_str):
        self.hotkey_sequence = QKeySequence(sequence_str)
        # If the combination contains Win/Meta — display manually
        if 'Win' in sequence_str or 'Meta' in sequence_str:
            self.setText(sequence_str)
        else:
            self.setText(self.hotkey_sequence.toString(QKeySequence.NativeText))

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._is_recording = True
        self.setText(self.texts.get('hotkey_press_keys', 'Press a combination…'))
        self.setStyleSheet(HOTKEY_RECORDING_STYLE)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._is_recording = False
        self.setText(self.hotkey_sequence.toString(QKeySequence.NativeText))
        self.setStyleSheet("")

    def keyPressEvent(self, event):
        from PyQt5.QtWidgets import QMessageBox
        if not self._is_recording:
            super().keyPressEvent(event)
            return
        key = event.key()
        special_keys = {
            Qt.Key_Delete: 'Delete', Qt.Key_Enter: 'Enter', Qt.Key_Return: 'Enter', Qt.Key_Insert: 'Insert',
            Qt.Key_Tab: 'Tab', Qt.Key_Escape: 'Esc', Qt.Key_Backspace: 'Backspace', Qt.Key_Home: 'Home',
            Qt.Key_End: 'End', Qt.Key_PageUp: 'PageUp', Qt.Key_PageDown: 'PageDown', Qt.Key_Print: 'PrintScreen',
            Qt.Key_ScrollLock: 'ScrollLock', Qt.Key_Pause: 'Pause', Qt.Key_CapsLock: 'CapsLock',
            Qt.Key_NumLock: 'NumLock', Qt.Key_Space: 'Space',
        }
        if key == Qt.Key_Escape:
            self.hotkey_sequence = QKeySequence()
            self.setText("")
            self.clearFocus()
            return
        if key in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta, Qt.Key_Super_L, Qt.Key_Super_R):
            return
        modifiers = event.modifiers()
        if key in special_keys:
            parts = []
            if modifiers & Qt.ControlModifier:
                parts.append('Ctrl')
            if modifiers & Qt.AltModifier:
                parts.append('Alt')
            if modifiers & Qt.ShiftModifier:
                parts.append('Shift')
            if modifiers & Qt.MetaModifier:
                parts.append('Win')
            parts.append(special_keys[key])
            hotkey_str = "+".join(parts)
            # Check if the combination is supported
            if not hotkey_str or not QKeySequence(hotkey_str).toString(QKeySequence.NativeText):
                QMessageBox.warning(self, self.texts.get('hotkey_warning_title', 'Invalid combination'),
                                   self.texts.get('hotkey_invalid', 'This combination is not supported. Please choose another.'))
                self.setText("")
                self.clearFocus()
                return
            self.hotkey_sequence = QKeySequence(hotkey_str)
            self.setText(hotkey_str)
            self.clearFocus()
            return
        # Regular keys
        self.hotkey_sequence = QKeySequence(key | int(modifiers))
        hotkey_str = self.hotkey_sequence.toString(QKeySequence.NativeText)
        if not hotkey_str:
            QMessageBox.warning(self, self.texts.get('hotkey_warning_title', 'Invalid combination'),
                               self.texts.get('hotkey_invalid', 'This combination is not supported. Please choose another.'))
            self.setText("")
            self.clearFocus()
            return
        self.setText(hotkey_str)
        self.clearFocus()

    def open_hotkey_dialog(self):
        from PyQt5.QtWidgets import QMessageBox
        dlg = HotkeyDialog(self.texts, self)
        if dlg.exec_() == QDialog.Accepted:
            hotkey_str = dlg.get_hotkey_str()
            # Check if the combination is supported
            if not hotkey_str or not QKeySequence(hotkey_str).toString(QKeySequence.NativeText):
                QMessageBox.warning(self, self.texts.get('hotkey_warning_title', 'Invalid combination'),
                                   self.texts.get('hotkey_invalid', 'This combination is not supported. Please choose another.'))
                return
            self.set_hotkey(hotkey_str)

# Hotkey selection dialog (checkboxes + drop-down list)
class HotkeyDialog(QDialog):
    def __init__(self, texts, parent=None):
        super().__init__(parent)
        self.setWindowTitle(texts.get('hotkey_choose_dialog', 'Choose a combination'))
        self.setModal(True)
        layout = QVBoxLayout(self)
        # Modifiers
        self.ctrl_cb = QCheckBox('Ctrl')
        self.alt_cb = QCheckBox('Alt')
        self.shift_cb = QCheckBox('Shift')
        self.win_cb = QCheckBox('Win')
        mod_layout = QHBoxLayout()
        mod_layout.addWidget(self.ctrl_cb)
        mod_layout.addWidget(self.alt_cb)
        mod_layout.addWidget(self.shift_cb)
        mod_layout.addWidget(self.win_cb)
        layout.addLayout(mod_layout)
        # Main key
        layout.addWidget(QLabel(texts.get('hotkey_choose_key', 'Key:')))
        self.key_combo = QComboBox()
        self._populate_keys()
        layout.addWidget(self.key_combo)
        # Buttons
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton('OK')
        cancel_btn = QPushButton('Cancel')
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _populate_keys(self):
        # <Unmapped> first
        self.key_combo.addItem('<Unmapped>')
        # Letters
        for c in range(ord('A'), ord('Z')+1):
            self.key_combo.addItem(chr(c))
        # Digits
        for c in range(ord('0'), ord('9')+1):
            self.key_combo.addItem(chr(c))
        # F1-F12
        for i in range(1, 13):
            self.key_combo.addItem(f'F{i}')
        # Special keys
        special = [
            'Delete', 'Enter', 'Insert', 'Tab', 'Esc', 'Backspace', 'Home', 'End', 'PageUp', 'PageDown',
            'PrintScreen', 'ScrollLock', 'Pause', 'CapsLock', 'NumLock', 'Space',
            '-', '=', '[', ']', ';', '\\', ',', '.', '/', '`', "'"
        ]
        for s in special:
            self.key_combo.addItem(s)

    def get_hotkey_str(self):
        parts = []
        if self.ctrl_cb.isChecked():
            parts.append('Ctrl')
        if self.alt_cb.isChecked():
            parts.append('Alt')
        if self.shift_cb.isChecked():
            parts.append('Shift')
        if self.win_cb.isChecked():
            parts.append('Win')
        key = self.key_combo.currentText()
        if key and key != '<Unmapped>':
            parts.append(key)
        return '+'.join(parts)
