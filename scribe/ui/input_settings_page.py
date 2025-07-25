# ui/input_settings_page.py
from PyQt5.QtWidgets import QButtonGroup, QFormLayout, QGroupBox, QLabel, QPushButton, QRadioButton, QSpinBox, QWidget

from scribe.ui.styles import HINT_LABEL_STYLE, WARNING_LABEL_STYLE


class InputSettingsPageWidget(QWidget):
    def __init__(self, texts, settings_manager, parent=None):
        super().__init__(parent)
        self.texts = texts
        self.settings_manager = settings_manager
        self.settings = self.settings_manager.all()
        layout = QFormLayout(self)
        layout.setSpacing(10)

        # Radio buttons for selecting input method
        self.input_method_group = QButtonGroup(self)
        self.rb_keyboard = QRadioButton(self.texts.get('input_method_keyboard', 'Keyboard typing'))
        self.rb_clipboard = QRadioButton(self.texts.get('input_method_clipboard', 'Clipboard paste'))
        self.input_method_group.addButton(self.rb_keyboard)
        self.input_method_group.addButton(self.rb_clipboard)

        inserter_type = self.settings.get('inserter_type', self.settings_manager.DEFAULTS['inserter_type'])
        if inserter_type == 'clipboard':
            self.rb_clipboard.setChecked(True)
        else:
            self.rb_keyboard.setChecked(True)

        layout.addRow(self.texts.get('input_method', 'Input method'), self.rb_keyboard)
        layout.addRow('', self.rb_clipboard)

        # Important hint for the user
        info_label = QLabel(self.texts.get('input_settings_info', 'If typing works fine, there is no reason to change keyboard or clipboard paste parameters.'))
        info_label.setWordWrap(True)
        info_label.setStyleSheet(WARNING_LABEL_STYLE)
        layout.addRow(info_label)

        # Group of typing (keyboard) parameters in a frame
        kb_group = QGroupBox(self.texts.get('keyboard_settings_group', 'Keyboard typing parameters'))
        kb_vbox = QFormLayout()
        self.keyboard_settings_widgets = {}
        kb_settings = self.settings.get('keyboard_settings', self.settings_manager.DEFAULTS['keyboard_settings'])
        self.kb_ranges = {
            'key_delay_ms': (
                int(0.5 * self.settings_manager.DEFAULTS['keyboard_settings']['key_delay_ms']),
                int(2.0 * self.settings_manager.DEFAULTS['keyboard_settings']['key_delay_ms'])
            ),
            'after_text_delay_ms': (
                int(0.5 * self.settings_manager.DEFAULTS['keyboard_settings']['after_text_delay_ms']),
                int(2.0 * self.settings_manager.DEFAULTS['keyboard_settings']['after_text_delay_ms'])
            ),
            'backspace_delay_ms': (
                int(0.5 * self.settings_manager.DEFAULTS['keyboard_settings']['backspace_delay_ms']),
                int(2.0 * self.settings_manager.DEFAULTS['keyboard_settings']['backspace_delay_ms'])
            ),
        }
        for key, label in [
            ('key_delay_ms', self.texts.get('key_delay_ms', 'Delay between characters (ms)')),
            ('after_text_delay_ms', self.texts.get('after_text_delay_ms', 'Pause after text (ms per char)')),
            ('backspace_delay_ms', self.texts.get('backspace_delay_ms', 'Delay between Backspace (ms)'))
        ]:
            minv, maxv = self.kb_ranges[key]
            spin = QSpinBox()
            spin.setMinimum(minv)
            spin.setMaximum(maxv)
            spin.setValue(kb_settings.get(key, self.settings_manager.DEFAULTS['keyboard_settings'][key]))
            spin.setSingleStep(1)
            spin.setMaximumWidth(80)
            self.keyboard_settings_widgets[key] = spin
            hint_key = f'{key}_hint'
            hint = QLabel(self.texts.get(hint_key, '').format(minv, maxv) if self.texts.get(hint_key) else f"{hint_key}: {minv}-{maxv}")
            hint.setStyleSheet(HINT_LABEL_STYLE)
            kb_vbox.addRow(label, spin)
            kb_vbox.addRow('', hint)
        kb_group.setLayout(kb_vbox)
        layout.addRow(kb_group)

        # Group of paste (clipboard) parameters in a frame
        cb_group = QGroupBox(self.texts.get('clipboard_settings_group', 'Clipboard paste parameters'))
        cb_vbox = QFormLayout()
        self.clipboard_settings_widgets = {}
        cb_settings = self.settings.get('clipboard_settings', self.settings_manager.DEFAULTS['clipboard_settings'])
        minv, maxv = self.kb_ranges['backspace_delay_ms']
        spin_cb = QSpinBox()
        spin_cb.setMinimum(minv)
        spin_cb.setMaximum(maxv)
        spin_cb.setValue(cb_settings.get('clipboard_delay_ms', self.settings_manager.DEFAULTS['clipboard_settings']['clipboard_delay_ms']))
        spin_cb.setSingleStep(1)
        spin_cb.setMaximumWidth(80)
        self.clipboard_settings_widgets['clipboard_delay_ms'] = spin_cb
        hint_cb = QLabel(self.texts.get('clipboard_delay_ms_hint', 'Range: {}–{} ms.').format(minv, maxv))
        hint_cb.setStyleSheet(HINT_LABEL_STYLE)
        cb_vbox.addRow(self.texts.get('clipboard_delay_ms', 'Delay between pastes (ms)'), spin_cb)
        cb_vbox.addRow('', hint_cb)
        cb_group.setLayout(cb_vbox)
        layout.addRow(cb_group)

        # Reset button with tooltip on hover
        reset_btn = QPushButton(self.texts.get('input_settings_reset_button', 'Reset input settings'))
        reset_btn.setToolTip(self.texts.get('input_settings_reset_hint', 'To quickly restore input settings to default values, press the button below.'))
        reset_btn.setMouseTracking(True)
        layout.addRow('', reset_btn)
        reset_btn.clicked.connect(self.do_reset)

    def do_reset(self):
        # Reset all widget values to default
        kb_defaults = self.settings_manager.DEFAULTS['keyboard_settings']
        for key, spin in self.keyboard_settings_widgets.items():
            spin.setValue(kb_defaults[key])
        cb_defaults = self.settings_manager.DEFAULTS['clipboard_settings']
        for key, spin in self.clipboard_settings_widgets.items():
            spin.setValue(cb_defaults[key])
        inserter_type = self.settings_manager.DEFAULTS['inserter_type']
        if inserter_type == 'clipboard':
            self.rb_clipboard.setChecked(True)
        else:
            self.rb_keyboard.setChecked(True)

    def get_keyboard_settings(self):
        result = {}
        for key, widget in self.keyboard_settings_widgets.items():
            val = widget.value()
            result[key] = val
        return result

    def get_clipboard_settings(self):
        result = {}
        for key, widget in self.clipboard_settings_widgets.items():
            val = widget.value()
            result[key] = val
        return result

    def get_inserter_type(self):
        return 'clipboard' if self.rb_clipboard.isChecked() else 'keyboard'
