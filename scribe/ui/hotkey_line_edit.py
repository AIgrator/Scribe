# ui/hotkey_line_edit.py
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QToolButton, QVBoxLayout

from scribe.hotkeys import hotkey_text_from_vk, parse_hotkey
from scribe.ui.styles import HOTKEY_RECORDING_STYLE

# Qt key -> Windows virtual key, used only when a key event does not report a
# native virtual key (for example on a platform without Win32).
_QT_SPECIAL_VKS = {
    Qt.Key_Delete: 0x2E, Qt.Key_Enter: 0x0D, Qt.Key_Return: 0x0D,
    Qt.Key_Insert: 0x2D, Qt.Key_Tab: 0x09, Qt.Key_Escape: 0x1B,
    Qt.Key_Backspace: 0x08, Qt.Key_Home: 0x24, Qt.Key_End: 0x23,
    Qt.Key_PageUp: 0x21, Qt.Key_PageDown: 0x22, Qt.Key_Print: 0x2C,
    Qt.Key_ScrollLock: 0x91, Qt.Key_Pause: 0x13, Qt.Key_CapsLock: 0x14,
    Qt.Key_NumLock: 0x90, Qt.Key_Space: 0x20, Qt.Key_Left: 0x25,
    Qt.Key_Up: 0x26, Qt.Key_Right: 0x27, Qt.Key_Down: 0x28,
}


def _qt_key_to_vk(key):
    if Qt.Key_A <= key <= Qt.Key_Z:
        return key
    if Qt.Key_0 <= key <= Qt.Key_9:
        return key
    if Qt.Key_F1 <= key <= Qt.Key_F24:
        return 0x70 + (key - Qt.Key_F1)
    return _QT_SPECIAL_VKS.get(key)


def _event_modifiers(event):
    mods = set()
    modifiers = event.modifiers()
    if modifiers & Qt.ControlModifier:
        mods.add('ctrl')
    if modifiers & Qt.AltModifier:
        mods.add('alt')
    if modifiers & Qt.ShiftModifier:
        mods.add('shift')
    if modifiers & Qt.MetaModifier:
        mods.add('win')
    return mods


def _event_hotkey_text(event):
    """Builds a layout-independent hotkey string from a key event."""
    mods = _event_modifiers(event)
    # Win32 reports the physical key, which is exactly what the matcher uses.
    if sys.platform == 'win32':
        vk = event.nativeVirtualKey()
        if vk:
            return hotkey_text_from_vk(vk, mods)
    vk = _qt_key_to_vk(event.key())
    if vk:
        return hotkey_text_from_vk(vk, mods)
    # Other platforms (X11) and keys without a VK: fall back to the typed
    # character. The non-Windows matcher still works with characters.
    char = event.text()
    if char and char.isprintable():
        parts = [name.capitalize() for name in ('ctrl', 'alt', 'shift', 'win')
                 if name in mods]
        parts.append(char)
        return '+'.join(parts)
    return None


class HotkeyLineEdit(QLineEdit):
    """Hotkey input field with a button for manual selection via dialog."""

    def __init__(self, texts, hotkey="", parent=None):
        super().__init__(parent)
        self.texts = texts
        self._hotkey_text = ""
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
        # The string is stored as-is: it is the value saved in the settings.
        # Keeping it verbatim avoids Qt re-spelling it in the active layout.
        self._hotkey_text = sequence_str or ""
        self.setText(self._hotkey_text)

    def hotkey_text(self):
        """Returns the hotkey value even while the field shows its prompt."""
        return self._hotkey_text

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._is_recording = True
        self.setText(self.texts.get('hotkey_press_keys', 'Press a combination…'))
        self.setStyleSheet(HOTKEY_RECORDING_STYLE)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._is_recording = False
        self.setText(self._hotkey_text)
        self.setStyleSheet("")

    def keyPressEvent(self, event):
        from PyQt5.QtWidgets import QMessageBox
        if not self._is_recording:
            super().keyPressEvent(event)
            return
        key = event.key()
        if key == Qt.Key_Escape:
            self._hotkey_text = ""
            self.setText("")
            self.clearFocus()
            return
        if key in (Qt.Key_Control, Qt.Key_Alt, Qt.Key_Shift, Qt.Key_Meta,
                   Qt.Key_Super_L, Qt.Key_Super_R):
            return
        hotkey_str = _event_hotkey_text(event)
        if not hotkey_str or parse_hotkey(hotkey_str) is None:
            QMessageBox.warning(self, self.texts.get('hotkey_warning_title', 'Invalid combination'),
                               self.texts.get('hotkey_invalid', 'This combination is not supported. Please choose another.'))
            self.setText(self._hotkey_text)
            self.clearFocus()
            return
        self._hotkey_text = hotkey_str
        self.setText(hotkey_str)
        self.clearFocus()

    def open_hotkey_dialog(self):
        from PyQt5.QtWidgets import QMessageBox
        dlg = HotkeyDialog(self.texts, self)
        if dlg.exec_() == QDialog.Accepted:
            hotkey_str = dlg.get_hotkey_str()
            # Check if the combination is supported
            if not hotkey_str or parse_hotkey(hotkey_str) is None:
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
            'Print', 'ScrollLock', 'Pause', 'CapsLock', 'NumLock', 'Space',
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
