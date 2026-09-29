"""
============================================================
 LYRA EARS
============================================================
 Speech-to-text with faster-whisper.

 Speed tricks:
 - transcribes straight from RAM (no WAV file on disk)
 - beam size 1, VAD trimmed, no timestamps
 - 16 kHz mono int8 on CPU
============================================================
"""

import logging

import numpy as np

from . import config

log = logging.getLogger(__name__)


class Ear:

    def __init__(self):

        from faster_whisper import WhisperModel

        print(f"Loading Whisper ({config.WHISPER_MODEL})...")

        self.model = WhisperModel(
            config.WHISPER_MODEL,
            device=config.WHISPER_DEVICE,
            compute_type=config.WHISPER_COMPUTE,
        )

        # tiny warm-up so the first real command is not slower
        silence = np.zeros(8000, dtype=np.float32)
        list(self.model.transcribe(silence, language="en"))

        print("Whisper ready.")

    # --------------------------------------------------------
    # TRANSCRIBE
    # --------------------------------------------------------

    def transcribe_audio(self, audio_data):
        """
        audio_data: speech_recognition.AudioData
        Returns the transcript string ('' on failure).
        """

        try:
            raw = audio_data.get_raw_data(
                convert_rate=16000,
                convert_width=2
            )
        except Exception:
            log.exception("Could not read microphone audio")
            return ""

        audio_array = np.frombuffer(raw, dtype=np.int16)
        audio_array = audio_array.astype(np.float32) / 32768.0

        kwargs = dict(
            language="en",
            temperature=0.0,
            beam_size=config.WHISPER_BEAM,
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 400,
                "speech_pad_ms": 200,
            },
            condition_on_previous_text=False,
            without_timestamps=True,
        )

        # Bias Whisper towards Lyra's own vocabulary so "brave" is not
        # heard as "breathe" and "terminate" not as "terminal".
        hotwords = getattr(config, "WHISPER_HOTWORDS", "")
        if hotwords:
            kwargs["hotwords"] = hotwords

        try:
            try:
                segments, _info = self.model.transcribe(audio_array, **kwargs)
            except TypeError:
                # older faster-whisper without hotword support
                kwargs.pop("hotwords", None)
                segments, _info = self.model.transcribe(audio_array, **kwargs)

            text = " ".join(segment.text for segment in segments)

            return text.strip()

        except Exception:
            log.exception("Whisper transcription failed")
            return ""
