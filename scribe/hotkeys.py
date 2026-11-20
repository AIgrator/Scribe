# hotkeys.py
"""Layout-independent hotkey parsing.

Qt stores hotkeys as text, for example ``Ctrl+Alt+0``.  Matching that text by
the character pynput reports breaks as soon as the keyboard layout changes:
the same physical key then produces another character, so a hotkey recorded in
one layout stops working in another one.

This module converts the text to a *virtual-key* code (the physical key) plus
a set of modifiers, and back.  Matching key events by virtual key is layout
independent: the key labelled ``0`` always reports ``VK_0``, and the key
labelled `` ` `` always reports ``VK_OEM_3``, whatever the active layout is.
"""
import ctypes
import logging
import platform
import re

logger = logging.getLogger(__name__)

_IS_WINDOWS = platform.system() == 'Windows'

MODIFIER_ORDER = ('ctrl', 'alt', 'shift', 'win')

MODIFIER_ALIASES = {
    'ctrl': 'ctrl',
    'control': 'ctrl',
    'ctl': 'ctrl',
    'alt': 'alt',
    'option': 'alt',
    'opt': 'alt',
    'shift': 'shift',
    'win': 'win',
    'cmd': 'win',
    'command': 'win',
    'meta': 'win',
    'super': 'win',
}

# Virtual-key codes of keys that do not produce a printable character.
SPECIAL_VKS = {
    'backspace': 0x08,
    'bksp': 0x08,
    'bs': 0x08,
    'tab': 0x09,
    'enter': 0x0D,
    'return': 0x0D,
    'pause': 0x13,
    'break': 0x13,
    'capslock': 0x14,
    'caps': 0x14,
    'esc': 0x1B,
    'escape': 0x1B,
    'space': 0x20,
    'spacebar': 0x20,
    'pageup': 0x21,
    'pgup': 0x21,
    'pagedown': 0x22,
    'pgdn': 0x22,
    'pgdown': 0x22,
    'end': 0x23,
    'home': 0x24,
    'left': 0x25,
    'up': 0x26,
    'right': 0x27,
    'down': 0x28,
    'printscreen': 0x2C,
    'print': 0x2C,
    'prtsc': 0x2C,
    'insert': 0x2D,
    'ins': 0x2D,
    'delete': 0x2E,
    'del': 0x2E,
    'numlock': 0x90,
    'scrolllock': 0x91,
    'scroll': 0x91,
    'num0': 0x60,
    'num1': 0x61,
    'num2': 0x62,
    'num3': 0x63,
    'num4': 0x64,
    'num5': 0x65,
    'num6': 0x66,
    'num7': 0x67,
    'num8': 0x68,
    'num9': 0x69,
    'num*': 0x6A,
    'multiply': 0x6A,
    'num+': 0x6B,
    'numplus': 0x6B,
    'add': 0x6B,
    'num-': 0x6D,
    'numminus': 0x6D,
    'subtract': 0x6D,
    'num.': 0x6E,
    'numdel': 0x6E,
    'numdecimal': 0x6E,
    'decimal': 0x6E,
    'num/': 0x6F,
    'numdivide': 0x6F,
    'divide': 0x6F,
}

# Preferred display names for the keys above.
_VK_NAMES = {
    0x08: 'Backspace',
    0x09: 'Tab',
    0x0D: 'Enter',
    0x13: 'Pause',
    0x14: 'CapsLock',
    0x1B: 'Esc',
    0x20: 'Space',
    0x21: 'PageUp',
    0x22: 'PageDown',
    0x23: 'End',
    0x24: 'Home',
    0x25: 'Left',
    0x26: 'Up',
    0x27: 'Right',
    0x28: 'Down',
    0x2C: 'Print',
    0x2D: 'Insert',
    0x2E: 'Delete',
    0x90: 'NumLock',
    0x91: 'ScrollLock',
    0x60: 'Num0',
    0x61: 'Num1',
    0x62: 'Num2',
    0x63: 'Num3',
    0x64: 'Num4',
    0x65: 'Num5',
    0x66: 'Num6',
    0x67: 'Num7',
    0x68: 'Num8',
    0x69: 'Num9',
    0x6A: 'Num*',
    0x6B: 'Num+',
    0x6D: 'Num-',
    0x6E: 'Num.',
    0x6F: 'Num/',
}

_FKEY_RE = re.compile(r'^f([1-9]|1[0-9]|2[0-4])$')

# Win32 constants used for character <-> virtual-key conversion.
_MAPVK_VK_TO_CHAR = 2
_KLF_NOTELLSHELL = 1

_us_layout = None
_us_layout_loaded = False


def _win32():
    return ctypes.windll.user32


def _us_hkl():
    """Loads the US layout once and returns its handle (used as a stable table)."""
    global _us_layout, _us_layout_loaded
    if not _IS_WINDOWS:
        return None
    if not _us_layout_loaded:
        _us_layout_loaded = True
        try:
            user32 = _win32()
            user32.LoadKeyboardLayoutW.restype = ctypes.c_void_p
            _us_layout = user32.LoadKeyboardLayoutW('00000409', _KLF_NOTELLSHELL)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Could not load the US keyboard layout: {e}")
            _us_layout = None
    return _us_layout


def _installed_layouts():
    """Returns the handles of all keyboard layouts installed on the system."""
    if not _IS_WINDOWS:
        return []
    try:
        user32 = _win32()
        user32.GetKeyboardLayoutList.argtypes = [
            ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
        count = user32.GetKeyboardLayoutList(0, None)
        if not count:
            return []
        array = (ctypes.c_void_p * count)()
        user32.GetKeyboardLayoutList(count, array)
        return [hkl for hkl in array if hkl]
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Could not enumerate keyboard layouts: {e}")
        return []


def _char_to_vk_win32(char):
    """Maps a character to (virtual key, required shift) using Windows layouts.

    ASCII characters are resolved with the US layout, so the result does not
    depend on the layout that happens to be active.  Other characters (for
    example a Cyrillic letter saved by an older Scribe version) are looked up
    in every installed layout.
    """
    if not _IS_WINDOWS or not char:
        return None
    try:
        user32 = _win32()
        user32.VkKeyScanExW.argtypes = [ctypes.c_wchar, ctypes.c_void_p]
        user32.VkKeyScanExW.restype = ctypes.c_short

        layouts = []
        if ord(char) < 128:
            layouts.append(_us_hkl())
        else:
            layouts.extend(_installed_layouts())
            # The active layout is usually in the list already; add it anyway.
            try:
                user32.GetKeyboardLayout.restype = ctypes.c_void_p
                layouts.append(user32.GetKeyboardLayout(0))
            except Exception:  # noqa: BLE001
                pass

        for hkl in layouts:
            if not hkl:
                continue
            result = user32.VkKeyScanExW(char, hkl)
            if result == -1:
                continue
            vk = result & 0xFF
            shift_state = (result >> 8) & 0x07
            # Older Scribe versions stored Cyrillic letters upper-cased just
            # for display; do not turn that into an implicit Shift.
            required_shift = bool(shift_state & 1) and ord(char) < 128
            return vk, required_shift
    except Exception as e:  # noqa: BLE001
        logger.debug(f"VkKeyScanExW failed for {char!r}: {e}")
    return None


def _char_to_vk(char):
    """Maps a single character to (virtual key, required shift)."""
    if not char:
        return None
    lower = char.lower()
    if 'a' <= lower <= 'z' and len(char) == 1:
        return ord(lower.upper()), False
    if '0' <= char <= '9':
        return ord(char), False
    return _char_to_vk_win32(char)


def _vk_to_char(vk):
    """Returns the unshifted character produced by a virtual key (US layout)."""
    if not _IS_WINDOWS:
        return None
    if 0x41 <= vk <= 0x5A:
        return chr(vk).lower()
    if 0x30 <= vk <= 0x39:
        return chr(vk)
    try:
        user32 = _win32()
        user32.MapVirtualKeyExW.argtypes = [
            ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p]
        user32.MapVirtualKeyExW.restype = ctypes.c_uint
        code = user32.MapVirtualKeyExW(vk, _MAPVK_VK_TO_CHAR, _us_hkl())
        if code:
            char = chr(code & 0xFFFF)
            if 'A' <= char <= 'Z':
                char = char.lower()
            if char.isprintable():
                return char
    except Exception as e:  # noqa: BLE001
        logger.debug(f"MapVirtualKeyExW failed for 0x{vk:X}: {e}")
    return None


def vk_to_key_text(vk):
    """Returns the human readable name of a virtual key, or ``None``."""
    if vk is None:
        return None
    if vk in _VK_NAMES:
        return _VK_NAMES[vk]
    match = _FKEY_RE.match(f'f{vk - 0x6F}') if 0x70 <= vk <= 0x87 else None
    if match:
        return f'F{vk - 0x6F}'
    return _vk_to_char(vk)


def _split_hotkey(text):
    """Splits a hotkey without losing a ``+`` key.

    ``Ctrl++`` means "Ctrl plus the + key", and ``Ctrl+Num+`` means "Ctrl plus
    the keypad plus key", so a plain ``split('+')`` is not enough.
    """
    text = text.strip()
    if text == '+':
        return ['+']
    for name in ('num+', 'numplus', 'add'):
        if text.lower().endswith(name):
            prefix = text[:-len(name)].rstrip('+')
            mods = [part.strip() for part in prefix.split('+') if part.strip()]
            return mods + [text[-len(name):]]
    if text.endswith('++'):
        # "Ctrl++" -> modifiers "Ctrl" and the key "+".
        return [part.strip() for part in text[:-1].split('+')[:-1]] + ['+']
    return [part.strip() for part in text.split('+')]


class Hotkey:
    """A parsed hotkey: modifiers plus the physical key."""

    __slots__ = ('mods', 'vk', 'char', 'name', 'text')

    def __init__(self, mods, vk=None, char=None, name=None, text=''):
        self.mods = frozenset(mods)
        self.vk = vk
        self.char = char
        self.name = name
        self.text = text

    def __repr__(self):
        return (f"Hotkey(mods={sorted(self.mods)}, vk={self.vk!r}, "
                f"char={self.char!r}, name={self.name!r})")

    def __eq__(self, other):
        return (isinstance(other, Hotkey)
                and self.mods == other.mods
                and self.vk == other.vk
                and self.char == other.char
                and self.name == other.name)

    def __hash__(self):
        return hash((self.mods, self.vk, self.char, self.name))


def parse_hotkey(text):
    """Parses a hotkey string into a :class:`Hotkey`, or returns ``None``."""
    if not text or not str(text).strip():
        return None
    text = str(text).strip()
    parts = _split_hotkey(text)
    if not parts or not parts[-1]:
        return None

    mods = set()
    for part in parts[:-1]:
        name = MODIFIER_ALIASES.get(part.lower())
        if not name:
            logger.debug(f"Unknown modifier {part!r} in hotkey {text!r}")
            return None
        mods.add(name)

    key = parts[-1]
    normalized = key.lower().replace(' ', '')

    if normalized in SPECIAL_VKS:
        return Hotkey(mods, vk=SPECIAL_VKS[normalized], name=normalized, text=text)

    match = _FKEY_RE.match(normalized)
    if match:
        number = int(match.group(1))
        return Hotkey(mods, vk=0x6F + number, name=f'f{number}', text=text)

    if len(key) == 1:
        char = key.lower() if key.isalpha() else key
        mapped = _char_to_vk(key)
        vk = None
        if mapped:
            vk, required_shift = mapped
            if required_shift:
                mods.add('shift')
        return Hotkey(mods, vk=vk, char=char, text=text)

    logger.warning(f"Hotkey {text!r} uses an unknown key {key!r}")
    return None


def hotkey_text_from_vk(vk, mods):
    """Builds the canonical hotkey text for a key press, or returns ``None``."""
    key_text = vk_to_key_text(vk)
    if not key_text:
        return None
    parts = [modifier.capitalize() for modifier in MODIFIER_ORDER
             if modifier in mods]
    parts.append(key_text)
    return '+'.join(parts)
