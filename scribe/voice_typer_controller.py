# voice_typer_controller.py
import logging
import threading
import time
import traceback

from PyQt5.QtCore import QObject, Qt, pyqtSignal

from scribe.audio_devices import AudioDevices
from scribe.vosk_recognizer import VoskRecognizer

logger = logging.getLogger(__name__)

class VoiceTyperController(QObject):
    microphone_changed = pyqtSignal(str)
    state_changed = pyqtSignal(bool, str) # New signal for running state and mode

    def __init__(
        self,
        model_path,
        inserter_type='keyboard',
        sample_rate=16000,
        blocksize=4000,
        settings_manager=None,
        need_resample=False,
        input_sample_rate=None,
        application=None
    ):
        super().__init__()
        self.application = application
        self.model_path = model_path
        self.inserter_type = inserter_type
        self.sample_rate = sample_rate
        self.blocksize = blocksize
        self.settings_manager = settings_manager
        self.need_resample = need_resample
        self.input_sample_rate = input_sample_rate
        self.recognizer = None
        self.running = False
        self.auto_stop_countdown = -1
        self.auto_stop_thread = None
        self._lock = threading.Lock()

        # We define and install a microphone
        initial_mic = self.settings_manager.get('selected_microphone')
        if not initial_mic:
            initial_mic = AudioDevices.get_default_input_name()
            if initial_mic:
                # Keep the default microphone if it has not been set
                self.settings_manager.set('selected_microphone', initial_mic)
        self.device_name = initial_mic

        self._init_recognizer()

    def _init_recognizer(self):
        logger.info(f"[VoiceTyperController] _init_recognizer called. Model path: {self.model_path}, Sample rate: {self.sample_rate}")
        if self.recognizer and self.running:
            logger.info("[VoiceTyperController] Stopping existing recognizer before re-initialization.")
            self.recognizer.stop()
            self.running = False

        kwargs = dict(
            model_path=self.model_path,
            sample_rate=self.sample_rate,
            blocksize=self.blocksize,
            inserter_type=self.inserter_type,
            settings_manager=self.settings_manager,
            need_resample=self.need_resample,
            input_sample_rate=self.input_sample_rate,
            device_name=self.device_name
        )
        self.recognizer = VoskRecognizer(**kwargs)
        # Use a direct connection to ensure the slot is executed immediately in the emitter's thread.
        # This is safe because _reset_auto_stop_timer is thread-safe.
        self.recognizer.text_recognized.connect(self._reset_auto_stop_timer, Qt.DirectConnection)

    def _auto_stop_loop(self):
        """Run in a separate thread and handle the auto-stop countdown."""
        while self.running:
            with self._lock:
                if self.auto_stop_countdown > 0:
                    # logger.info(f"Auto-stop in: {self.auto_stop_countdown} seconds...")
                    self.auto_stop_countdown -= 1
                elif self.auto_stop_countdown == 0:
                    logger.info("Auto-stop timeout reached. Stopping recognition.")
                    # It's crucial to call stop() outside the lock to avoid deadlocks
                    # We can't call it directly, so we emit a signal that the main thread can connect to
                    # For simplicity and avoiding Qt cross-thread signal issues without a QThread,
                    # we will just call stop() and design it to be safe.
                    self.stop()
                    break  # Exit loop after stopping

            time.sleep(1)
        logger.info("Auto-stop thread finished.")


    def _reset_auto_stop_timer(self, text: str):
        """Resets the auto-stop countdown if the recognized text is meaningful."""
        with self._lock:
            # Check if countdown is active
            if self.auto_stop_countdown != -1 and len(text) > 1:
                timeout_seconds = self.settings_manager.get("auto_stop_timeout", 0)
                if timeout_seconds > 0:
                    # logger.debug(f"Resetting auto-stop countdown to {timeout_seconds}s due to recognized text.")
                    self.auto_stop_countdown = timeout_seconds

    def start(self):
        if self.application and self.application.is_loading_model:
            logger.debug("Ignoring start() request: model is loading.")
            return
        logger.info(f"[VoiceTyperController] start() called. Current running state: {self.running}")
        if not self.running:
            self.running = True # Set running to true before starting threads
            self.recognizer.start()
            self.state_changed.emit(self.running, getattr(self.recognizer, 'mode', None))

            # Start the auto-stop thread if the timeout is set
            timeout_seconds = self.settings_manager.get("auto_stop_timeout", 0)
            if timeout_seconds > 0:
                with self._lock:
                    self.auto_stop_countdown = timeout_seconds
                logger.info(f"Auto-stop enabled. Timeout: {timeout_seconds} seconds.")
                self.auto_stop_thread = threading.Thread(target=self._auto_stop_loop, daemon=True)
                self.auto_stop_thread.start()

    def stop(self):
        if self.application and self.application.is_loading_model:
            logger.debug("Ignoring stop() request: model is loading.")
            return
        logger.info(f"[VoiceTyperController] stop() called. Current running state: {self.running}")
        if not self.running:
            return

        self.running = False # Signal all threads to stop

        # Stop the recognizer first. This is a non-blocking call.
        self.recognizer.stop()

        # The auto_stop_thread will see self.running as False and exit its loop.
        # We don't need to join it as it's a daemon.

        self.state_changed.emit(self.running, getattr(self.recognizer, 'mode', None))
        logger.info("Recognition stopped.")

    def toggle(self):
        if self.application and self.application.is_loading_model:
            logger.debug("Ignoring toggle() request: model is loading.")
            return
        try:
            if self.running:
                self.stop()
            else:
                self.start()
        except Exception as e:
            logger.error(f"Exception in toggle(): {e}")
            traceback.print_exc()

    def change_microphone(self, device_name):
        if self.application and self.application.is_loading_model:
            logger.debug("Ignoring change_microphone() request: model is loading.")
            return
        """Centralized method for changing microphone.

        Stops recognition, changes device, saves setting,
        restarts recognition and emits change signal.
        """
        if not device_name or self.device_name == device_name:
            logger.info(f"[VoiceTyperController] Microphone is already '{device_name}' or invalid, no change needed.")
            return

        logger.info(f"[VoiceTyperController] Changing microphone from '{self.device_name}' to '{device_name}'")

        was_running = self.running
        self.stop()

        # Changing the device
        self.device_name = device_name
        if hasattr(self.recognizer, 'set_device'):
            self.recognizer.set_device(device_name)

        # Save the new setting
        self.settings_manager.set('selected_microphone', device_name)

        if was_running:
            self.start()

        # Notifying the UI of changes
        self.microphone_changed.emit(device_name)
        logger.info("[VoiceTyperController] Microphone change complete. Emitted signal.")

    def switch_to_transcribe_mode(self):
        if self.application and self.application.is_loading_model:
            logger.debug("Ignoring switch_to_transcribe_mode() request: model is loading.")
            return
        logger.info("Switched to transcription mode")
        if self.running and getattr(self.recognizer, 'mode', None) == 'transcribe':
            self.stop()
            return
        if self.running:
            self.stop()
        self.recognizer.set_mode('transcribe')
        self.start()
        self.state_changed.emit(self.running, self.recognizer.mode)

    def switch_to_command_mode(self):
        if self.application and self.application.is_loading_model:
            logger.debug("Ignoring switch_to_command_mode() request: model is loading.")
            return
        from scribe.command_handler import command_mode
        logger.info("Switched to command mode")
        if self.running and getattr(self.recognizer, 'mode', None) == 'command':
            self.stop()
            return
        if self.running:
            self.stop()
        self.recognizer.set_mode('command', final_handler=command_mode(self.settings_manager))
        self.start()
        self.state_changed.emit(self.running, self.recognizer.mode)

    def set_tray_app(self, tray_app):
        self._tray_app = tray_app

    def _update_tray_tooltip(self):
        if hasattr(self, '_tray_app') and self._tray_app is not None:
            self._tray_app._update_tray_icon()

    def is_fully_stopped(self):
        if self.recognizer is None:
            return True
        if getattr(self.recognizer, 'running', False):
            return False
        if hasattr(self.recognizer, 'recognition_thread') and self.recognizer.recognition_thread:
            if self.recognizer.recognition_thread.is_alive():
                return False
        if hasattr(self.recognizer, 'inserter') and hasattr(self.recognizer.inserter, 'wait_until_idle'):
            self.recognizer.inserter.wait_until_idle(timeout=0.1)
        return True

    def set_inserter_type(self, inserter_type):
        self.inserter_type = inserter_type
        if hasattr(self.recognizer, 'set_inserter_type'):
            self.recognizer.set_inserter_type(inserter_type)

    def _update_tray_ui_and_tooltip(self):
        if hasattr(self, '_tray_app') and self._tray_app is not None:
            self._tray_app.update_tray_ui()
