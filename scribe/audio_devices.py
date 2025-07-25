
# audio_devices.py
import logging

import sounddevice as sd

logger = logging.getLogger(__name__)

class AudioDevices:
    @staticmethod
    def check_microphone_sample_rate(sample_rate, device=None):
        """Checks if the microphone (or default device) supports the given sample_rate.

        If device=None, checks for the default device.
        Returns True/False.
        """
        try:
            if device:
                # Find all devices with the given name
                matching_devices = [d for d in sd.query_devices() if d['name'] == device and d['max_input_channels'] > 0]
                if not matching_devices:
                    logger.warning(f"No input device found with name: {device}")
                    return False

                # Check each matching device
                for dev_info in matching_devices:
                    try:
                        sd.check_input_settings(device=dev_info['index'], samplerate=sample_rate)
                        logger.info(f"Device '{device}' (index {dev_info['index']}) supports {sample_rate} Hz")
                        return True
                    except Exception:
                        continue  # Try the next device

                # If no matching device supports the sample rate
                logger.warning(f"No device named '{device}' supports {sample_rate} Hz.")
                return False
            else:
                # Check default device if no specific device is named
                sd.check_input_settings(samplerate=sample_rate)
                logger.info(f"Default microphone supports {sample_rate} Hz")
                return True
        except Exception as e:
            logger.warning(f"Microphone does NOT support {sample_rate} Hz: {e}")
            return False
    FORBIDDEN_KEYWORDS = (
        'mix', 'mixer',         # Mixers
        'loopback',             # Loopback devices
        'speaker', 'output'     # Output devices that may appear as inputs
    )

    @staticmethod
    def get_wasapi_index():
        try:
            for i, api in enumerate(sd.query_hostapis()):
                if api['name'] == 'Windows WASAPI':
                    return i
        except Exception as e:
            logger.error(f"Failed to query audio host APIs: {e}")
        return -1

    @staticmethod
    def get_input_devices(wasapi_only=True):
        wasapi_index = AudioDevices.get_wasapi_index() if wasapi_only else -1
        devices = []
        try:
            all_devices = sd.query_devices()
            for d in all_devices:
                if d['max_input_channels'] <= 0:
                    continue
                if wasapi_only and wasapi_index != -1 and d['hostapi'] != wasapi_index:
                    continue
                name = d['name']
                if any(k in name.lower() for k in AudioDevices.FORBIDDEN_KEYWORDS):
                    continue
                devices.append(name)
        except Exception as e:
            logger.error(f"Failed to get microphone list: {e}")
        return devices

    @staticmethod
    def get_default_input_name():
        try:
            default_input = sd.query_devices(kind='input')
            return default_input['name']
        except Exception as e:
            logger.error(f"Failed to determine default microphone: {e}")
            return None

    # In the future: methods for saving/loading the selected device
