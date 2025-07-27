# controller_loader.py
import logging

from PyQt5.QtCore import QThread, pyqtSignal

from scribe.audio_utils import AudioUtils
from scribe.voice_typer_controller import VoiceTyperController

logger = logging.getLogger(__name__)

class ControllerLoader(QThread):
    finished = pyqtSignal(object, object)  # (controller, error)
    def __init__(self, model_path, inserter_type, settings_manager, application):
        super().__init__()
        self.model_path = model_path
        self.inserter_type = inserter_type
        self.settings_manager = settings_manager
        self.application = application
    def run(self):
        try:
            # 1. Determine sample_rate for the model
            sample_rate = AudioUtils.detect_sample_rate(self.model_path)
            logger.info(f"sample_rate from model {sample_rate} Hz")
            mic_name = self.settings_manager.all().get('selected_microphone')

            # 2. Check if the microphone supports the required sample rate (for warning)
            from scribe.audio_devices import AudioDevices
            if not AudioDevices.check_microphone_sample_rate(sample_rate, device=mic_name):
                logger.warning(f"Microphone {mic_name or '[default]'} does not support {sample_rate} Hz. Resampling or errors possible!")
                # 3. Get the actual microphone sample rate only if resampling is needed
                input_sample_rate = sample_rate
                try:
                    import sounddevice as sd
                    if mic_name:
                        for dev in sd.query_devices():
                            if dev['name'] == mic_name and dev['max_input_channels'] > 0:
                                input_sample_rate = int(dev['default_samplerate'])
                                break
                        else:
                            input_sample_rate = int(sd.query_devices(kind='input')['default_samplerate'])
                    else:
                        input_sample_rate = int(sd.query_devices(kind='input')['default_samplerate'])
                except Exception:
                    pass
                need_resample = True
            else:
                input_sample_rate = sample_rate
                need_resample = False

            controller = VoiceTyperController(
                model_path=self.model_path,
                inserter_type=self.inserter_type,
                sample_rate=sample_rate,
                settings_manager=self.settings_manager,
                need_resample=need_resample,
                input_sample_rate=input_sample_rate,
                blocksize=self.settings_manager.all().get('blocksize', 4000),
                application=self.application
            )
            self.finished.emit(controller, None)
        except Exception as e:
            self.finished.emit(None, e)
