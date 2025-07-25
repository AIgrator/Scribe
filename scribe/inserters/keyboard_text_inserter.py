# inserters/keyboard_text_inserter.py
import logging
import queue
import threading
import time

import keyboard

from scribe.inserters.text_inserter import TextInserter

logger = logging.getLogger(__name__)

class KeyboardTextInserter(TextInserter):
    def __init__(self, settings_manager):
        self.settings_manager = settings_manager
        self._queue = queue.Queue()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._running = False
        self._update_settings(self.settings_manager.all())
        self.settings_manager.settings_changed.connect(self._update_settings)

    def _update_settings(self, settings):
        kb = settings.get('keyboard_settings', self.settings_manager.DEFAULTS['keyboard_settings'])
        self.key_delay = kb.get('key_delay_ms', 20) / 1000.0
        self.after_text_delay = kb.get('after_text_delay_ms', 5) / 1000.0
        self.backspace_delay = kb.get('backspace_delay_ms', 10) / 1000.0

    def start(self):
        logger.info("start() called")
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

    def insert_actions(self, actions: list):
        logger.info(f"insert_actions() called with actions: {actions!r}")
        self._queue.put(('insert_actions', actions))

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
                    keyboard.write(arg, delay=self.key_delay)
                    time.sleep(self.after_text_delay * len(arg))
                elif cmd == 'insert_actions':
                    # Выполняем действия строго в том порядке, в котором они были переданы
                    for action in arg:
                        if action['type'] == 'text' and action['value']:
                            keyboard.write(action['value'], delay=self.key_delay)
                            time.sleep(self.after_text_delay * len(action['value']))
                        elif action['type'] == 'key' and action['value']:
                            keyboard.send(action['value'])
                            time.sleep(self.key_delay)
                elif cmd == 'erase_chars':
                    for _ in range(arg):
                        keyboard.send('backspace')
                        time.sleep(self.backspace_delay)
            except Exception as e:
                logger.error(f"{e}")

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
