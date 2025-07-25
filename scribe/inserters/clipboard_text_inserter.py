# inserters/clipboard_text_inserter.py
import logging
import queue
import threading
import time

import win32api
import win32clipboard
import win32con

from scribe.inserters.text_inserter import TextInserter

logger = logging.getLogger(__name__)

class ClipboardTextInserter(TextInserter):
    def __init__(self, settings_manager):
        self.settings_manager = settings_manager
        self._orig_clipboard = None
        self._queue = queue.Queue()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._running = False
        self._update_settings(self.settings_manager.all())
        self.settings_manager.settings_changed.connect(self._update_settings)

    def _update_settings(self, settings):
        cb = settings.get('clipboard_settings', self.settings_manager.DEFAULTS['clipboard_settings'])
        self.clipboard_delay = cb.get('clipboard_delay_ms', 10) / 1000.0

    def start(self):
        try:
            win32clipboard.OpenClipboard()
            try:
                orig = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            except Exception:
                orig = None
            win32clipboard.CloseClipboard()
            self._orig_clipboard = orig
            if orig is not None:
                snippet = orig[:50] + ("..." if len(orig) > 50 else "")
                logger.info(f"Original buffer saved (start): '{snippet}'")
            else:
                logger.info("The original buffer is empty or not text")
        except Exception as e:
            self._orig_clipboard = None
            logger.error(f"Failed to get buffer on startup: {e}")
        self._running = True
        if not self._worker.is_alive():
            self._worker = threading.Thread(target=self._worker_loop, daemon=True)
            self._worker.start()

    def stop(self):
        logger.info("stop() called")
        self._running = False
        self._queue.put(('__STOP__', None))
        if self._worker.is_alive():
            self._worker.join(timeout=1)

    def insert_text(self, text: str):
        logger.info(f"insert_text() called with text: {text!r}")
        self._queue.put(('insert_text', text))

    def erase_chars(self, count: int):
        logger.info(f"erase_chars() called with count: {count}")
        self._queue.put(('erase_chars', count))

    def _worker_loop(self):
        while self._running:
            try:
                cmd, arg = self._queue.get()
                if cmd == '__STOP__':
                    break
                if cmd == 'insert_text':
                    # Сохраняем и вставляем через буфер обмена
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, arg)
                    win32clipboard.CloseClipboard()
                    win32api.keybd_event(0x11, 0, 0, 0)  # Ctrl
                    win32api.keybd_event(0x56, 0, 0, 0)  # V
                    win32api.keybd_event(0x56, 0, 2, 0)  # V up
                    win32api.keybd_event(0x11, 0, 2, 0)  # Ctrl up
                    time.sleep(self.clipboard_delay * len(arg))
                elif cmd == 'insert_actions':
                    # Собираем итоговый текст с учётом спецклавиш
                    buf = ''
                    for action in arg:
                        if action['type'] == 'text' and action['value']:
                            buf += action['value']
                        elif action['type'] == 'key' and action['value']:
                            key = action['value']
                            if key == 'Space':
                                buf += ' '
                            elif key == 'Tab':
                                buf += '\t'
                            elif key == 'Enter':
                                buf += '\n'
                            elif key == 'Backspace':
                                buf = buf[:-1] if buf else buf
                    # Вставляем итоговый буфер через буфер обмена
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, buf)
                    win32clipboard.CloseClipboard()
                    win32api.keybd_event(0x11, 0, 0, 0)  # Ctrl
                    win32api.keybd_event(0x56, 0, 0, 0)  # V
                    win32api.keybd_event(0x56, 0, 2, 0)  # V up
                    win32api.keybd_event(0x11, 0, 2, 0)  # Ctrl up
                    time.sleep(self.clipboard_delay * len(buf))
                elif cmd == 'erase_chars':
                    for _ in range(arg):
                        win32api.keybd_event(0x08, 0, 0, 0)  # Backspace
                        win32api.keybd_event(0x08, 0, 2, 0)
                        time.sleep(0.01)
            except Exception as e:
                logger.error(f"{e}")

    def insert_actions(self, actions: list):
        """Pastes a list of actions (text/key) via the clipboard, supporting special keys."""
        logger.info(f"called with actions: {actions!r}")
        self._queue.put(('insert_actions', actions))

    def wait_until_idle(self, timeout=2.0):
        """Waits until the command queue and worker thread are completely empty."""
        start_time = time.time()
        while self._worker.is_alive():
            if self._queue.empty():
                break
            if time.time() - start_time > timeout:
                logger.warning("wait_until_idle: timeout")
                break
            time.sleep(0.01)
