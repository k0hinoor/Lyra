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

        self.language = None if config.WHISPER_LANGUAGE == "auto" else config.WHISPER_LANGUAGE
        model_name = config.WHISPER_MODEL
        # Existing Windows settings may still contain base.en. That model
        # can never understand Hindi, even with language="hi" requested.
        if self.language != "en" and model_name in {"tiny.en", "base.en", "small.en", "medium.en"}:
            multilingual = model_name.removesuffix(".en")
            log.warning(
                "%s is English-only; using multilingual %s for WHISPER_LANGUAGE=%s. "
                "Update WHISPER_MODEL in settings.json to remove .en.",
                model_name, multilingual, config.WHISPER_LANGUAGE,
            )
            model_name = multilingual
        self.model_name = model_name
        print(f"Loading Whisper ({model_name}, language={config.WHISPER_LANGUAGE})...")

        self.model = WhisperModel(
            model_name,
            device=config.WHISPER_DEVICE,
            compute_type=config.WHISPER_COMPUTE,
        )

        # tiny warm-up so the first real command is not slower
        silence = np.zeros(8000, dtype=np.float32)
        segments, _info = self.model.transcribe(
            silence, language=self.language or "en", task="transcribe",
        )
        list(segments)

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

        try:
            audio_array = np.frombuffer(raw, dtype=np.int16)
            if not audio_array.size:
                return ""
            audio_array = audio_array.astype(np.float32) / 32768.0
        except (TypeError, ValueError):
            log.exception("Invalid microphone PCM buffer")
            return ""

        kwargs = dict(
            language=self.language,
            task="transcribe",  # keep Hindi as Hindi; do not translate it to English
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
            log.debug("Whisper detected language=%s", getattr(_info, "language", "unknown"))
            return text.strip()

        except Exception:
            log.exception("Whisper transcription failed")
            return ""
