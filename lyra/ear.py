"""
============================================================
 LYRA EARS
============================================================
 Speech-to-text with faster-whisper.

 Speed tricks:
 - transcribes straight from RAM (no WAV file on disk)
 - beam size 1, VAD trimmed, no timestamps
 - 16 kHz mono int8 on CPU

 Two entry points:

 - transcribe_audio()  commands, in the configured language ("auto"
   detects per utterance)
 - transcribe_wake()   the short wake-gate clip, always decoded in a
   pinned language first so per-clip detection cannot guess wrong
============================================================
"""

import logging

import numpy as np

from . import config
from .utils import normalize, strip_wake_word

log = logging.getLogger(__name__)

# Sentinel: "no language was forced for this call, use the configured one".
_DEFAULT_LANGUAGE = object()


class Ear:

    def __init__(self):

        from faster_whisper import WhisperModel

        self.language = None if config.WHISPER_LANGUAGE == "auto" else config.WHISPER_LANGUAGE
        # Language reported by the last transcription: what Whisper detected
        # in auto mode, or the language that was pinned. The wake debug line
        # (WAKE_DEBUG / --debug-wake) prints it.
        self.last_language = None
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

    @property
    def wake_language(self):
        """Language for a wake clip: the configured one, or English when auto.

        Per-clip detection on a 1-2 second utterance often settles on the
        wrong language, and then "Hey Lyra" comes back as Hindi script or as
        an unrelated English sentence. The wake phrase is English, so auto
        mode pins English for the wake clip instead of detecting.
        """
        return self.language or "en"

    def transcribe_audio(self, audio_data, language=_DEFAULT_LANGUAGE):
        """
        audio_data: speech_recognition.AudioData
        Returns the transcript string ('' on failure).

        `language` overrides WHISPER_LANGUAGE for this one call
        (None = let Whisper detect the language).
        """
        return self._transcribe(
            audio_data,
            self.language if language is _DEFAULT_LANGUAGE else language,
        )

    def transcribe_wake(self, audio_data):
        """Transcribe one wake-gate clip and return the best wake transcript.

        First pass: the pinned wake language (English unless another language
        was configured), with the same hotword bias as commands, so a short
        clip is decoded as the English phrase it really is. When that pass
        does not contain an accepted wake phrase, one auto-detect retry runs
        (only in WHISPER_LANGUAGE="auto") so a Hindi native-script wake name
        spoken as "हे लायरा" still has a chance.
        """

        transcript = self._transcribe(audio_data, self.wake_language)

        if _contains_wake_phrase(transcript):
            return transcript

        if self.language is None:
            retry = self._transcribe(audio_data, None)
            if retry and _contains_wake_phrase(retry):
                return retry
            return transcript or retry

        return transcript

    # --------------------------------------------------------
    # INTERNALS
    # --------------------------------------------------------

    def _audio_array(self, audio_data):
        """int16 AudioData -> float32 mono array in [-1, 1], or None."""

        try:
            raw = audio_data.get_raw_data(
                convert_rate=16000,
                convert_width=2
            )
        except Exception:
            log.exception("Could not read microphone audio")
            return None

        try:
            audio_array = np.frombuffer(raw, dtype=np.int16)
            if not audio_array.size:
                return None
            return audio_array.astype(np.float32) / 32768.0
        except (TypeError, ValueError):
            log.exception("Invalid microphone PCM buffer")
            return None

    def _transcribe(self, audio_data, language):
        """One Whisper call with command-quality settings. '' on failure."""

        audio_array = self._audio_array(audio_data)
        if audio_array is None:
            return ""

        kwargs = dict(
            language=language,
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
        # heard as "breathe" and "terminate" not as "terminal". The same bias
        # keeps "Hey Lyra" itself in the wake clip's transcript.
        hotwords = getattr(config, "WHISPER_HOTWORDS", "")
        if hotwords:
            kwargs["hotwords"] = hotwords

        try:
            try:
                segments, info = self.model.transcribe(audio_array, **kwargs)
            except TypeError:
                # older faster-whisper without hotword support: an initial
                # prompt carries the same vocabulary into the decoder.
                if "hotwords" not in kwargs:
                    raise
                kwargs.pop("hotwords", None)
                if hotwords:
                    kwargs["initial_prompt"] = hotwords
                segments, info = self.model.transcribe(audio_array, **kwargs)

            text = " ".join(segment.text for segment in segments)
            self.last_language = getattr(info, "language", None) or language or "unknown"
            log.debug("Whisper detected language=%s", self.last_language)
            return text.strip()

        except Exception:
            log.exception("Whisper transcription failed")
            return ""


def _contains_wake_phrase(transcript):
    """True when a transcript holds an accepted wake phrase at its start."""

    return strip_wake_word(normalize(transcript or ""))[0]
