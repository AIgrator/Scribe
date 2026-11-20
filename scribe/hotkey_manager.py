# hotkey_manager.py
import logging
import platform
import queue
import threading

from pynput import keyboard
from PyQt5.QtCore import QCoreApplication, QObject, QTimer

from scribe.hotkeys import parse_hotkey

logger = logging.getLogger(__name__)

_IS_WINDOWS = platform.system() == 'Windows'

# Virtual keys of the modifier keys, including the left/right variants that
# the Windows low-level hook reports.
_MODIFIER_VKS = {
    0x10: 'shift',
    0xA0: 'shift',
    0xA1: 'shift',
    0x11: 'ctrl',
    0xA2: 'ctrl',
    0xA3: 'ctrl',
    0x12: 'alt',
    0xA4: 'alt',
    0xA5: 'alt',  # AltGr
    0x5B: 'win',
    0x5C: 'win',
}


def _key_vk(key):
    """Returns the virtual-key code of a pynput key, or ``None``."""
    if isinstance(key, keyboard.Key):
        value = key.value
        return getattr(value, 'vk', None)
    return getattr(key, 'vk', None)


class HotkeyManager(QObject):
    """Manages global hotkeys for the application.

    Two details matter for reliability:

    * hotkeys are matched by *virtual-key code* (the physical key), not by the
      character pynput reports, so they keep working after a keyboard-layout
      switch or a reboot;
    * callbacks run on a worker thread, not on the low-level keyboard hook.
      Windows silently removes a hook whose callback takes longer than
      ``LowLevelHooksTimeout`` (about 300 ms), and starting or stopping the
      microphone takes longer than that.
    """

    # How often to check that the listener thread is still alive.
    _WATCHDOG_INTERVAL_MS = 15000

    def __init__(self, settings_manager, controller):
        super().__init__()
        self.settings_manager = settings_manager
        self.controller = controller
        self.listener = None
        self._last_registered_hotkeys = {}
        self._actions = {}
        self._pressed_vks = set()
        self._modifiers = set()
        self._generation = 0
        self._queue = queue.Queue()
        self._worker = threading.Thread(
            target=self._worker_loop, name='hotkey-worker', daemon=True)
        self._worker.start()
        self.register_hotkeys()
        self.settings_manager.settings_changed.connect(self.on_settings_changed)

        self._watchdog = None
        if QCoreApplication.instance() is not None:
            self._watchdog = QTimer(self)
            self._watchdog.setInterval(self._WATCHDOG_INTERVAL_MS)
            self._watchdog.timeout.connect(self._ensure_listener_alive)
            self._watchdog.start()

    # ------------------------------------------------------------------ setup
    def on_settings_changed(self, new_settings):
        """Re-registers hotkeys if they have changed in the settings."""
        new_modes = new_settings.get('modes', self.settings_manager.DEFAULTS['modes'])
        new_models_hotkeys = new_settings.get('models_hotkeys', self.settings_manager.DEFAULTS['models_hotkeys'])

        last_modes = self._last_registered_hotkeys.get('modes', {})
        last_models_hotkeys = self._last_registered_hotkeys.get('models_hotkeys', {})

        if new_modes != last_modes or new_models_hotkeys != last_models_hotkeys:
            logger.info("Hotkey settings changed, re-registering...")
            self.register_hotkeys()

    def _to_pynput_format(self, key_str: str):
        """Converts a hotkey string like 'Ctrl+Shift+Q' to pynput format '<ctrl>+<shift>+q'."""
        if not key_str:
            return None

        keys = key_str.lower().split('+')
        formatted_keys = []

        key_map = {
            'ctrl': 'ctrl',
            'alt': 'alt',
            'shift': 'shift',
            'cmd': 'cmd',
            'win': 'cmd',
            'super': 'cmd'
        }

        for key in keys:
            key = key.strip()
            if key in key_map:
                formatted_keys.append(f"<{key_map[key]}>")
            else:
                formatted_keys.append(key)

        return "+".join(formatted_keys)

    def _collect_hotkeys(self):
        """Returns a list of (text, description, action) from the settings."""
        entries = []

        modes = self.settings_manager.get('modes', {})
        entries.append((modes.get('transcribe_mode', 'Ctrl+Shift+Q'),
                        'transcription mode', self.controller.switch_to_transcribe_mode))
        entries.append((modes.get('command_mode', 'Ctrl+Alt+Q'),
                        'command mode', self.controller.switch_to_command_mode))

        models_dict = self.settings_manager.get('models', {})
        models_hotkeys = self.settings_manager.get('models_hotkeys', {})
        seen = set()
        for lang_models in models_dict.values():
            for model in lang_models:
                name = model.get('name')
                if not name or name in seen:
                    continue
                seen.add(name)
                hotkey = models_hotkeys.get(name, '')
                if hotkey:
                    entries.append((hotkey, f'model {name}',
                                    self._make_switch_model(name)))
        return entries

    def _make_switch_model(self, model_name):
        def switch_model():
            self._switch_model(model_name)
        return switch_model

    def register_hotkeys(self):
        """Stops the old listener and registers new hotkeys from settings."""
        self.stop()

        hotkey_map = {}
        legacy_map = {}
        for text, description, action in self._collect_hotkeys():
            if not text:
                continue
            if _IS_WINDOWS:
                hotkey = parse_hotkey(text)
                if hotkey is None or hotkey.vk is None:
                    logger.warning(
                        "Hotkey %r (%s) is not supported on this system and "
                        "will be ignored.", text, description)
                    continue
                key = (hotkey.mods, hotkey.vk)
                if key in hotkey_map:
                    logger.warning(
                        "Hotkey %r (%s) duplicates another hotkey; keeping the "
                        "first one.", text, description)
                    continue
                hotkey_map[key] = action
                logger.info(
                    "Registered hotkey %s for %s (modifiers=%s, vk=0x%02X)",
                    text, description,
                    '+'.join(sorted(hotkey.mods)) or 'none', hotkey.vk)
            else:
                pynput_hotkey = self._to_pynput_format(text)
                if pynput_hotkey:
                    legacy_map[pynput_hotkey] = action
                    logger.info(f"Press {text} for {description}.")

        self._generation += 1
        self._actions = hotkey_map

        if _IS_WINDOWS:
            if hotkey_map:
                self._start_vk_listener()
        elif legacy_map:
            try:
                self.listener = keyboard.GlobalHotKeys(legacy_map)
                self.listener.start()
                logger.info("Hotkey listener started with new hotkeys.")
            except Exception as e:  # noqa: BLE001
                # This can happen on Wayland or if there are permission issues
                logger.error(f"Failed to start GlobalHotKeys listener: {e}", exc_info=True)
                if platform.system() == "Linux":
                    logger.error("On Linux, you may need to install 'python3-xlib' and run as root.")
                self.listener = None

        self._last_registered_hotkeys = {
            'modes': self.settings_manager.get('modes', {}).copy(),
            'models_hotkeys': self.settings_manager.get('models_hotkeys', {}).copy()
        }

    def _start_vk_listener(self):
        try:
            self._pressed_vks.clear()
            self._modifiers.clear()
            self.listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
            )
            self.listener.start()
            logger.info("Hotkey listener started with new hotkeys.")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to start keyboard listener: {e}", exc_info=True)
            self.listener = None

    # -------------------------------------------------------------- hook side
    def _on_press(self, key, injected=False):
        """Runs on the pynput hook thread: it must stay as short as possible."""
        try:
            vk = _key_vk(key)
            if vk is None:
                return
            modifier = _MODIFIER_VKS.get(vk)
            if modifier:
                self._modifiers.add(modifier)
                return
            if vk in self._pressed_vks:
                return  # auto-repeat while the key is held down
            self._pressed_vks.add(vk)
            action = self._actions.get((frozenset(self._modifiers), vk))
            if action is not None:
                self._queue.put((self._generation, action))
        except Exception:  # noqa: BLE001
            logger.exception("Error while handling a hotkey press")

    def _on_release(self, key, injected=False):
        """Runs on the pynput hook thread: it must stay as short as possible."""
        try:
            vk = _key_vk(key)
            if vk is None:
                return
            modifier = _MODIFIER_VKS.get(vk)
            if modifier:
                self._modifiers.discard(modifier)
            self._pressed_vks.discard(vk)
        except Exception:  # noqa: BLE001
            logger.exception("Error while handling a hotkey release")

    # ------------------------------------------------------------ worker side
    def _worker_loop(self):
        while True:
            item = self._queue.get()
            if item is None:
                break
            generation, action = item
            if generation != self._generation:
                # The hotkeys were re-registered while this action was queued.
                continue
            try:
                action()
            except Exception:  # noqa: BLE001
                logger.exception("Error while executing a hotkey action")

    def _ensure_listener_alive(self):
        """Restarts the listener if its thread died unexpectedly."""
        if not self._actions:
            return
        listener = self.listener
        if listener is None or not listener.is_alive():
            logger.warning("Hotkey listener is not running; restarting it.")
            self.register_hotkeys()

    def _switch_model(self, model_name):
        """Changes the current model and language via settings_manager."""
        logger.info(f"Switching to model: {model_name}")
        models_dict = self.settings_manager.get('models', {})
        model_lang = None
        for lang, lang_models in models_dict.items():
            for model in lang_models:
                if model.get('name') == model_name:
                    model_lang = model.get('language', lang)
                    break
            if model_lang:
                break

        if model_lang is None:
            logger.error(f"Failed to determine language for model {model_name}")
            return

        self.settings_manager.set('current_model', model_name)
        self.settings_manager.set('language', model_lang)

    def stop(self):
        """Stops the hotkey listener thread."""
        listener = self.listener
        self.listener = None
        self._actions = {}
        # Invalidate actions that were queued before this call.
        self._generation += 1
        if listener is not None:
            logger.info("Stopping hotkey listener.")
            try:
                if listener.is_alive():
                    listener.stop()
                    listener.join(timeout=2)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"Error while stopping the hotkey listener: {e}")
        self._pressed_vks.clear()
        self._modifiers.clear()

    def __del__(self):
        """Ensure the listener and worker are stopped when the manager is deleted."""
        try:
            if self._watchdog is not None:
                self._watchdog.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.stop()
            self._queue.put(None)
        except Exception:  # noqa: BLE001
            pass
