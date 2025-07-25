# vosk_recognizer.py
import json
import logging
import os
import queue
import sys
import threading
import time
import traceback

import sounddevice as sd
import vosk
from PyQt5.QtCore import QObject, pyqtSignal

from scribe.replacements import apply_replacements, apply_replacements_actions, load_replacements
from scribe.transcribe_file import get_transcribe_file

logger = logging.getLogger(__name__)

class VoskRecognizer(QObject):
    rms_signal = pyqtSignal(float)  # RMS level of the audio signal (0..1)
    recognition_state_changed = pyqtSignal(bool, str)  # running, mode
    text_recognized = pyqtSignal(str)  # Emitted when any text is recognized

    def __init__(
        self,
        model_path,
        sample_rate=16000,
        blocksize=4000,
        partial_interval=0.5,
        inserter_type='clipboard',
        device_name=None,
        settings_manager=None,
        mode='transcribe',
        final_handler=None,
        partial_handler=None,
        need_resample=False,
        input_sample_rate=None
    ):
        super().__init__()
        """
        model_path: path to the unpacked Vosk model
        sample_rate: usually 16000
        blocksize: audio block size, for example 4000 (~0.25 s at 16kHz)
        partial_interval: minimum interval (sec) between partial applications
        inserter_type: type of text inserter ('clipboard' or 'winapi')
        """
        logger.info(f"[VoskRecognizer] __init__ called. Model path: {model_path}, Sample rate: {sample_rate}, Device name: {device_name}")
        self.device_name = device_name

        # On Windows, loading models from paths with non-ASCII characters is problematic.
        # A workaround is to temporarily change the current directory.
        original_cwd = None
        try:
            if model_path and sys.platform == 'win32':
                original_cwd = os.getcwd()
                os.chdir(os.path.dirname(model_path))
                # After changing the directory, we load the model using its base name.
                self.model = vosk.Model(os.path.basename(model_path))
            else:
                self.model = vosk.Model(model_path)
        except Exception as e:
            logger.error(f"Model loading error: {e}")
            raise
        finally:
            # Restore the original working directory immediately.
            if original_cwd:
                os.chdir(original_cwd)
        self.sample_rate = sample_rate
        self.blocksize = blocksize
        self.PARTIAL_INTERVAL = partial_interval
        self.need_resample = need_resample
        self.input_sample_rate = input_sample_rate if input_sample_rate else sample_rate

        # PCM data queue
        self.audio_queue = queue.Queue()

        # Partial-state
        self.partial_prev = ""       # last inserted partial
        self.partial_buffer = ""     # last received Vosk partial
        self.last_partial_time = 0.0 # time of last partial_prev application

        self.running = False
        self.stream = None
        self.recognition_thread = None
        self._lock = threading.Lock()


        self.settings_manager = settings_manager
        self.mode = mode  # 'transcribe' or 'command'
        self.final_handler = final_handler  # callback for final text
        self.partial_handler = partial_handler  # callback for partial (optional)
        # Text inserter. Available options: 'clipboard', 'keyboard'
        if inserter_type == 'clipboard':
            from scribe.inserters.clipboard_text_inserter import ClipboardTextInserter
            self.inserter = ClipboardTextInserter(self.settings_manager)
        elif inserter_type == 'keyboard':
            from scribe.inserters.keyboard_text_inserter import KeyboardTextInserter
            self.inserter = KeyboardTextInserter(self.settings_manager)
        else:
            logger.warning(f"Unknown inserter_type '{inserter_type}', using ClipboardTextInserter")
            from scribe.inserters.clipboard_text_inserter import ClipboardTextInserter
            self.inserter = ClipboardTextInserter(self.settings_manager)

        # Load replacements and flags during initialization
        self._load_replacements()

    def set_mode(self, mode, final_handler=None, partial_handler=None):
        """Allows changing the operation mode (transcribe/command/...) and handlers on the fly.

        Can be called at any time, even while running.
        When changing mode, resets partial_prev and partial_buffer to avoid text deletion when switching from command mode.
        """
        self.mode = mode
        # Emit signal after mode change
        self.recognition_state_changed.emit(self.running, self.mode)
        # If final_handler is explicitly passed — use it, else:
        if final_handler is not None:
            self.final_handler = final_handler
        elif mode == 'transcribe':
            # In transcription mode, disable command handler
            self.final_handler = None
        # Similarly for partial_handler (if needed)
        if partial_handler is not None:
            self.partial_handler = partial_handler
        # print(f"[VoskRecognizer] Final self.inserter: {type(self.inserter)}", flush=True)  # disabled

        # Reset partial_prev and partial_buffer when changing mode
        self.partial_prev = ""
        self.partial_buffer = ""
        self.last_partial_time = 0.0

        # Load replacements and flags
        self._load_replacements()

    """
    The VoskRecognizer class now supports multiple operation modes (transcribe/command) and allows
    dynamic mode and handler changes without reloading the model.
    """
    def _load_replacements(self):
        """Loads replacements and flags from settings for the current language (via replacements.py)."""
        self._replacements, self._replacements_enabled, self._partial_replacements_enabled, self._lang = load_replacements(self.settings_manager)

    def _apply_replacements(self, text):
        """Applies replacements to text only by individual words (via replacements.py)."""
        return apply_replacements(text, self._replacements)

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for audio input stream. Puts audio data into the queue for recognition. Also calculates RMS and sends it via a signal."""
        if status:
            logger.info(f"Stream status: {status}")
        self.audio_queue.put(bytes(indata))
        # Calculate RMS (signal level)
        try:
            import numpy as np
            arr = np.frombuffer(indata, dtype='int16')
            rms = np.sqrt(np.mean(arr.astype(np.float32) ** 2)) / 32768.0
            scaled_rms = min(1.0, rms * 50.0) # Scale for visualization, cap at 1.0
            self.rms_signal.emit(float(scaled_rms))
            #logger.debug(f"RMS: {rms}, Scaled RMS: {scaled_rms}")
        except Exception:
            pass

    def set_device(self, device_name):
        """Set the device name for the next start."""
        self.device_name = device_name

    def start(self):
        """Starts the speech recognition process, microphone stream, and recognition thread. Creates a file for transcription if enabled in settings."""
        recognizer_id = id(self)
        logger.info(f"[VoskRecognizer] start() called. Recognizer ID: {recognizer_id}, Running state: {self.running}")
        if self.running:
            logger.info(f"[self.id][{recognizer_id}] Already running (running={self.running})")
            return
        logger.info(f"[self.id][{recognizer_id}] inserter={type(self.inserter).__name__}")
        self.inserter.start()
        self.running = True
        # Emit signal after start
        self.recognition_state_changed.emit(self.running, self.mode)
        self.partial_prev = ""
        self.partial_buffer = ""
        self.last_partial_time = 0.0

        # Create file for transcription immediately if enabled in settings
        settings = {}
        enabled = False
        if hasattr(self, 'settings_manager') and self.settings_manager:
            sm = self.settings_manager
            settings = sm.all() if hasattr(sm, 'all') else {}
            enabled = settings.get('transcribe_to_file', False)
        if enabled:
            get_transcribe_file(self)

        # Start recognition in a thread
        self.recognition_thread = threading.Thread(target=self._recognition_loop, daemon=True)
        self.recognition_thread.start()

        # Open microphone
        try:
            # If device name is specified, find its index
            device_index = None
            if self.device_name:
                for idx, dev in enumerate(sd.query_devices()):
                    if dev['name'] == self.device_name and dev['max_input_channels'] > 0:
                        device_index = idx
                        break
                if device_index is None:
                    logger.warning(f"[self.id][{recognizer_id}] [WARN] Device with name not found: {self.device_name}, using default")
            self.stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.blocksize,
                dtype='int16',
                channels=1,
                callback=self._audio_callback,
                device=device_index
            )
            self.stream.start()
        except Exception as e:
            logger.error(f"[self.id][{recognizer_id}] Failed to open microphone: {e}")
            self.running = False
            return

        logger.info(f"[self.id][{recognizer_id}] Recognition started (running={self.running})")

    def stop(self):
        """Stops the speech recognition process, closes the microphone stream, and waits for all threads and inserter operations to finish."""
        logger.info(f"[VoskRecognizer] stop() called. Recognizer ID: {id(self)}, Running state: {self.running}")
        if not self.running:
            return

        # 1. Stop the audio stream immediately to prevent new data from entering the queue.
        # This is critical for a clean shutdown, especially on systems like Windows 7
        # where stream termination might not be instantaneous.
        if self.stream:
            try:
                self.stream.callback = None
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                logger.error(f"Exception while stopping audio stream: {e}")
            self.stream = None

        # 2. Signal the recognition thread to stop processing.
        self.running = False

        # 3. Clear the queue to discard any audio data that was buffered before the stop call.
        # This prevents the thread from processing stale data.
        with self.audio_queue.mutex:
            self.audio_queue.queue.clear()

        # 4. The recognition thread is a daemon, so we don't need to join it.
        # It will exit automatically when the `self.running` flag is False.
        # Joining it here can cause deadlocks if stop() is called from a worker thread.
        self.recognition_thread = None

        # 5. Wait for any pending text insertion operations to complete.
        if hasattr(self.inserter, 'wait_until_idle'):
            self.inserter.wait_until_idle()

        self.inserter.stop()

        # 6. Emit the final state change signal after everything is truly stopped.
        self.recognition_state_changed.emit(self.running, self.mode)


    def _recognition_loop(self):
        """Main recognition loop.

        Reads audio data from the queue, processes it with Vosk recognizer,
        and applies partial and final results using the appropriate handlers.
        """
        recognizer = vosk.KaldiRecognizer(self.model, self.sample_rate)
        while self.running:
            try:
                data = self.audio_queue.get(timeout=0.2)

                if recognizer.AcceptWaveform(data):
                    # Final result: process immediately
                    try:
                        res = json.loads(recognizer.Result())
                        final_text = res.get("text", "").strip()
                    except Exception:
                        final_text = ""
                    if final_text:
                        self._apply_final(final_text)
                else:
                    # Partial result: save to buffer and check time
                    try:
                        pres = json.loads(recognizer.PartialResult())
                        partial = pres.get("partial", "").strip()
                    except Exception:
                        partial = ""
                    if partial != self.partial_buffer:
                        self.partial_buffer = partial
                        logger.debug(f"[Partial-buffer] New partial: '{partial}'")
                    # Apply only if partial_buffer differs from partial_prev and enough time has passed
                    now = time.time()
                    if self.partial_buffer and self.partial_buffer != self.partial_prev and (now - self.last_partial_time >= self.PARTIAL_INTERVAL):
                        self._apply_partial(self.partial_buffer)
                        self.last_partial_time = now
                    # If Vosk gave an empty partial and there was a previous partial_prev, erase leftovers
                    if not self.partial_buffer and self.partial_prev:
                        logger.debug(f"[Partial-buffer] partial is empty, erasing leftovers '{self.partial_prev}'")
                        with self._lock:
                            self.inserter.erase_chars(len(self.partial_prev))
                            self.partial_prev = ""
                        self.last_partial_time = now
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"FATAL ERROR in recognition loop: {e}")
                logger.error(traceback.format_exc())
                # It's better to stop the loop on unexpected error
                self.running = False

        # On finish: clear any remaining partial
        with self._lock:
            if self.partial_prev:
                logger.debug(f"Clearing remaining partial on finish: '{self.partial_prev}'")
                self.inserter.erase_chars(len(self.partial_prev))
                self.partial_prev = ""

    def _apply_diff(self, old_text: str, new_text: str, context: str):
        """Applies the difference between old_text and new_text using the inserter.

        Deletes the differing suffix from old_text and inserts the new suffix from new_text.
        """
        with self._lock:
            # Calculate common prefix
            common_len = 0
            maxlen = min(len(old_text), len(new_text))
            while common_len < maxlen and old_text[common_len] == new_text[common_len]:
                common_len += 1
            to_delete = len(old_text) - common_len
            suffix = new_text[common_len:]

            # Logging
            logger.debug(f"[{context}->apply] old='{old_text}' new='{new_text}'")
            logger.debug(f"[{context}->apply] common_len={common_len}, to_delete={to_delete}, suffix='{suffix}'")

            # Deletion
            if to_delete > 0:
                logger.debug(f"[{context}->apply] Deleting {to_delete} characters")
                self.inserter.erase_chars(to_delete)

            # Insertion
            if suffix:
                logger.debug(f"[{context}->apply] Inserting suffix via buffer: '{suffix}'")
                self.inserter.insert_text(suffix)

            return new_text  # Return the updated value

    def _apply_partial(self, partial: str):
        """Always cleans the partial from special commands for display and insertion.

        If partial replacements are enabled, applies them to the clean text using apply_replacements_actions,
        so that text replaced by special commands is not inserted. Otherwise, uses the clean text directly.
        If a user partial_handler is set, calls it. Otherwise, performs standard transcription behavior.
        """
        from scribe.replacements import parse_replace_string
        actions = parse_replace_string(partial)
        partial_clean = ''.join(act['value'] for act in actions if act['type'] == 'text')
        # If partial replacements are enabled, apply them to the clean text,
        # but use apply_replacements_actions to avoid inserting text replaced by special commands
        if self._partial_replacements_enabled:
            from scribe.replacements import apply_replacements_actions as ara
            actions2 = ara(partial_clean, self._replacements)
            # In partial, insert only those text fragments that do not immediately follow a special command
            partial = ''.join(act['value'] for act in actions2 if act['type'] == 'text')
        else:
            partial = partial_clean
        # If a user partial_handler is set, call it
        if self.partial_handler:
            self.partial_handler(partial)
            return
        # Standard behavior (transcription)
        if self.mode == 'transcribe':
            self.partial_prev = self._apply_diff(self.partial_prev, partial, "Partial")
        self.text_recognized.emit(partial)

    def _apply_final(self, final_text: str):
        """Applies replacements to the final text if enabled. Handles writing the final result to file if enabled in settings.

        Calls the user final_handler if set. Handles text insertion unless in command mode.
        """
        actions = None
        if self._replacements_enabled:
            actions = apply_replacements_actions(final_text, self._replacements)
            # For file writing and callback, collect a string without special commands
            final_text_plain = ''.join(
                act['value'] if act['type'] == 'text' else '' for act in actions
            )
            diff_text = final_text_plain
        else:
            final_text_plain = final_text
            diff_text = final_text

        # Write the final result to file if enabled in settings
        settings = {}
        enabled = False
        if hasattr(self, 'settings_manager') and self.settings_manager:
            sm = self.settings_manager
            settings = sm.all() if hasattr(sm, 'all') else {}
            enabled = settings.get('transcribe_to_file', False)
        if enabled:
            f = get_transcribe_file(self)
            if f and final_text_plain.strip():
                try:
                    f.write(final_text_plain.strip() + '\n')
                    f.flush()
                except Exception as e:
                    logger.error(f"Failed to write to transcription file: {e}")

        # If a user final_handler is set, call it
        if self.final_handler:
            self.final_handler(final_text_plain)
            # Do not return! File writing is already done above

        # Insert text only if not in command mode
        if self.mode != 'command':
            has_keys = actions is not None and any(act['type'] == 'key' for act in actions)
            if hasattr(self.inserter, 'insert_actions') and actions is not None and has_keys:
                # If there are special commands, always delete the entire partial_prev
                if self.partial_prev:
                    logger.debug(f"[Final->apply] erase_chars (full) before insert_actions: {len(self.partial_prev)}")
                    self.inserter.erase_chars(len(self.partial_prev))
                self.inserter.insert_actions(actions)
            else:
                # diff logic: get what actually needs to be inserted
                old_text = self.partial_prev
                new_text = diff_text
                common_len = 0
                maxlen = min(len(old_text), len(new_text))
                while common_len < maxlen and old_text[common_len] == new_text[common_len]:
                    common_len += 1
                to_delete = len(old_text) - common_len
                suffix = new_text[common_len:]
                logger.debug(f"[Final->apply] old='{old_text}' new='{new_text}'")
                logger.debug(f"[Final->apply] common_len={common_len}, to_delete={to_delete}, suffix='{suffix}'")
                if to_delete > 0:
                    logger.debug(f"[Final->apply] Deleting {to_delete} characters")
                    self.inserter.erase_chars(to_delete)
                if suffix or not old_text:
                    logger.debug(f"[Final->apply] Inserting suffix via buffer: '{suffix}'")
                    self.inserter.insert_text(suffix)
            logger.debug("[Final->apply] Adding space after final")
            self.inserter.insert_text(" ")

        self.partial_prev = ""
        self.partial_buffer = ""
        self.last_partial_time = time.time()
        logger.info(f"[✓] {final_text_plain}")
        self.text_recognized.emit(final_text_plain)

    def set_inserter_type(self, inserter_type):
        """Allows changing the text insertion method without reloading the model.

        Stops the old inserter, creates a new one, and starts it if recognition is already running.
        """
        was_running = getattr(self, 'running', False)
        if was_running:
            self.inserter.stop()
        self.settings_manager = self.settings_manager  # just in case
        if inserter_type == 'clipboard':
            from scribe.inserters.clipboard_text_inserter import ClipboardTextInserter
            self.inserter = ClipboardTextInserter(self.settings_manager)
        elif inserter_type == 'keyboard':
            from scribe.inserters.keyboard_text_inserter import KeyboardTextInserter
            self.inserter = KeyboardTextInserter(self.settings_manager)
        else:
            logger.warning(f"Unknown inserter_type '{inserter_type}', using ClipboardTextInserter")
            from scribe.inserters.clipboard_text_inserter import ClipboardTextInserter
            self.inserter = ClipboardTextInserter(self.settings_manager)
        if was_running:
            self.inserter.start()
