# audio_utils.py
import os

import numpy as np


class AudioUtils:
    @staticmethod
    def resample_audio(data, input_rate, target_rate):
        """Resamples audio data using only numpy.

        data: bytes or np.array (int16), mono
        Returns bytes.
        """
        if isinstance(data, bytes):
            data = np.frombuffer(data, dtype=np.int16)
        input_length = len(data)
        output_length = int(input_length * target_rate / input_rate)
        input_times = np.linspace(0, 1, input_length, endpoint=False)
        output_times = np.linspace(0, 1, output_length, endpoint=False)
        resampled = np.interp(output_times, input_times, data).astype(np.int16)
        return resampled.tobytes()

    @staticmethod
    def detect_sample_rate(model_path):
        """Determines the sample_rate for a Vosk model by reading mfcc.conf.

        Looks for mfcc.conf in the conf/ and am/ subfolders.
        Returns sample_rate (int), default is 16000.
        """
        for subdir in ['conf', 'am']:
            conf_path = os.path.join(model_path, subdir, 'mfcc.conf')
            if os.path.exists(conf_path):
                with open(conf_path, encoding='utf-8') as f:
                    for line in f:
                        if '--sample-frequency=' in line:
                            try:
                                return int(line.strip().split('=')[1])
                            except Exception:
                                pass
                        if '--sample-rate=' in line:
                            try:
                                return int(line.strip().split('=')[1])
                            except Exception:
                                pass
        return 16000  # default fallback
