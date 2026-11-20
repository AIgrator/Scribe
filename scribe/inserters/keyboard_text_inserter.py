# inserters/linux_keyboard_text_inserter.py
import ctypes
import logging
import platform
import queue
import threading
import time

from pynput.keyboard import Controller, Key

from scribe.inserters.text_inserter import TextInserter

logger = logging.getLogger(__name__)

_IS_WINDOWS = platform.system() == 'Windows'

# Win32 constants for SendInput.
_INPUT_KEYBOARD = 1
_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ('wVk', ctypes.c_ushort),
        ('wScan', ctypes.c_ushort),
        ('dwFlags', ctypes.c_ulong),
        ('time', ctypes.c_ulong),
        ('dwExtraInfo', ctypes.c_void_p),
    ]


class _MOUSEINPUT(ctypes.Structure):
    # Present only to give the union its real (largest) size, so that
    # sizeof(INPUT) matches what SendInput expects.
    _fields_ = [
        ('dx', ctypes.c_long),
        ('dy', ctypes.c_long),
        ('mouseData', ctypes.c_ulong),
        ('dwFlags', ctypes.c_ulong),
        ('time', ctypes.c_ulong),
        ('dwExtraInfo', ctypes.c_void_p),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [('ki', _KEYBDINPUT), ('mi', _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [('type', ctypes.c_ulong), ('u', _INPUTUNION)]


def _send_unicode_win32(text: str) -> bool:
    """Type text with SendInput and KEYEVENTF_UNICODE.

    pynput resolves a character to a *virtual key* using the layout of Scribe's
    own thread; the target window then translates that key with *its* layout.
    When the two layouts differ, Cyrillic turns into Latin and '.' becomes 'ю'
    (issue #1). The Unicode flag sends the code unit as WM_CHAR instead, so the
    target receives exactly the characters we asked for, whatever the layout.

    Returns True when every event was accepted, False to let the caller fall
    back to pynput (non-Windows, or SendInput refused the input).
    """
    if not text:
        return True
    try:
        user32 = ctypes.windll.user32
        raw = text.encode('utf-16-le')
        units = [int.from_bytes(raw[i:i + 2], 'little')
                 for i in range(0, len(raw), 2)]
        events = []
        for unit in units:
            for flags in (_KEYEVENTF_UNICODE,
                          _KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP):
                event = _INPUT(type=_INPUT_KEYBOARD)
                event.u.ki = _KEYBDINPUT(0, unit, flags, 0, None)
                events.append(event)
        array = (_INPUT * len(events))(*events)
        sent = user32.SendInput(len(events), array, ctypes.sizeof(_INPUT))
        return sent == len(events)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Win32 SendInput(unicode) failed: {e}")
        return False


class KeyboardTextInserter(TextInserter):
    def __init__(self, settings_manager):
        self.settings_manager = settings_manager
        self._queue = queue.Queue()
        self._worker = None
        self._running = False
        self._pending = 0
        self._pending_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._keyboard = Controller()
        self._unicode_typing = _IS_WINDOWS
        self._update_settings(self.settings_manager.all())
        self.settings_manager.settings_changed.connect(self._update_settings)

    def _update_settings(self, settings):
        kb = settings.get('keyboard_settings', self.settings_manager.DEFAULTS['keyboard_settings'])
        self.key_delay = kb.get('key_delay_ms', 20) / 1000.0
        self.after_text_delay = kb.get('after_text_delay_ms', 5) / 1000.0
        self.backspace_delay = kb.get('backspace_delay_ms', 10) / 1000.0

    def start(self):
        logger.info("start() called")
        with self._state_lock:
            if self._running and self._worker is not None and self._worker.is_alive():
                return
            self._running = True
            self._start_worker()

    def _start_worker(self):
        """Starts a worker with its own queue (the caller holds _state_lock)."""
        self._queue = queue.Queue()
        self._worker = threading.Thread(
            target=self._worker_loop, args=(self._queue,), daemon=True)
        self._worker.start()
        logger.info("Text inserter worker started.")

    def stop(self):
        logger.info("stop() called")
        with self._state_lock:
            self._running = False
            self._queue.put(('__STOP__', None))
            worker = self._worker
        if worker is not None and worker.is_alive():
            worker.join(timeout=1)

    def _enqueue(self, cmd, arg):
        """Queues a command, starting a fresh worker if the old one is gone.

        The previous version reused a single worker thread and put a stop
        marker into its queue.  When a dictation was still being typed at
        stop() time, the marker stayed in the queue; the next start() saw a
        live thread and did not create a new one, so the marker shut the
        worker down and every following command was queued to a dead thread.
        That is why recognition kept running but no text appeared until the
        model (and therefore the inserter) was recreated.
        """
        with self._state_lock:
            if not self._running:
                logger.warning(
                    "Ignoring %s: the text inserter is stopped.", cmd)
                return
            worker = self._worker
            if worker is None or not worker.is_alive():
                logger.warning(
                    "The text inserter worker is not running; restarting it.")
                self._start_worker()
            with self._pending_lock:
                self._pending += 1
            self._queue.put((cmd, arg))

    def insert_text(self, text: str):
        logger.info(f"insert_text() called with text: {text!r}")
        self._enqueue('insert_text', text)

    def insert_actions(self, actions: list):
        logger.info(f"insert_actions() called with actions: {actions!r}")
        self._enqueue('insert_actions', actions)

    def erase_chars(self, count: int):
        logger.info(f"erase_chars() called with count: {count}")
        self._enqueue('erase_chars', count)

    def _type_char(self, char: str):
        """Types one character, layout-independently when possible."""
        if self._unicode_typing and char >= ' ' and _send_unicode_win32(char):
            return
        self._keyboard.press(char)
        self._keyboard.release(char)

    def _worker_loop(self, work_queue):
        while True:
            cmd, arg = work_queue.get()
            if cmd == '__STOP__':
                break
            try:
                if cmd == 'insert_text':
                    # Type character by character with delay, mimicking keyboard.write(delay=...)
                    for char in arg:
                        self._type_char(char)
                        time.sleep(self.key_delay)
                    time.sleep(self.after_text_delay * len(arg))
                elif cmd == 'insert_actions':
                    for action in arg:
                        if action['type'] == 'text' and action['value']:
                            # Type character by character with delay
                            for char in action['value']:
                                self._type_char(char)
                                time.sleep(self.key_delay)
                            time.sleep(self.after_text_delay * len(action['value']))
                        elif action['type'] == 'key' and action['value']:
                            key_to_press = self._map_key(action['value'])
                            if key_to_press:
                                self._keyboard.press(key_to_press)
                                self._keyboard.release(key_to_press)
                                time.sleep(self.key_delay)
                elif cmd == 'erase_chars':
                    for _ in range(arg):
                        self._keyboard.press(Key.backspace)
                        self._keyboard.release(Key.backspace)
                        time.sleep(self.backspace_delay)
            except Exception as e:
                logger.error(f"Error in keyboard text inserter worker loop: {e}")
            finally:
                with self._pending_lock:
                    self._pending -= 1

    def _map_key(self, key_name):
        key_map = {
            'backspace': Key.backspace,
            'tab': Key.tab,
            'enter': Key.enter,
            'space': Key.space,
        }
        return key_map.get(key_name.lower())

    def wait_until_idle(self, timeout=2.0):
        """Waits until every queued command has been typed."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._pending_lock:
                pending = self._pending
            if pending <= 0:
                return
            time.sleep(0.01)
        logger.warning("wait_until_idle: timeout")
