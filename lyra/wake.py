"""Lightweight offline wake gate; command-quality Whisper runs only after a hit."""

import json
import logging

from . import config
from .utils import normalize, strip_wake_word

log = logging.getLogger(__name__)


class WakeWordDetector:
    """Use a persistent Vosk acoustic model on short utterances when installed.

    If the optional Vosk model is absent, preserve the previous Whisper-based
    wake behavior rather than disabling voice mode. The caller then runs the
    regular Whisper command transcription only after a Vosk wake hit.
    """

    def __init__(self):
        self.model = None
        self._fallback_logged = False
        model_dir = config.WAKE_VOSK_MODEL_DIR
        if model_dir.is_dir():
            try:
                from vosk import Model
                self.model = Model(str(model_dir))
                log.info("Vosk wake model loaded from %s", model_dir)
            except Exception:
                log.exception("Could not load Vosk wake model")
        else:
            log.warning(
                "Lightweight wake model is not installed at %s; wake detection "
                "will fall back to Whisper. See README setup instructions.", model_dir
            )

    @property
    def lightweight(self):
        return self.model is not None

    def detect(self, audio_data, fallback_transcriber=None):
        """Return ``(matched, remainder, transcript)`` for a captured short clip."""
        if self.model is None:
            transcript = fallback_transcriber(audio_data) if fallback_transcriber else ""
            matched, remainder = strip_wake_word(normalize(transcript))
            return matched, remainder, transcript

        try:
            from vosk import KaldiRecognizer
            pcm = audio_data.get_raw_data(convert_rate=16000, convert_width=2)
            if len(pcm) % 2:
                log.warning("Ignoring odd-length wake audio buffer (%d bytes)", len(pcm))
                return False, "", ""
            recognizer = KaldiRecognizer(self.model, 16000)
            recognizer.SetWords(False)
            accepted = recognizer.AcceptWaveform(pcm)
            result = json.loads(recognizer.Result() if accepted else recognizer.FinalResult())
            transcript = result.get("text", "")
            matched, remainder = strip_wake_word(normalize(transcript))
            return matched, remainder, transcript
        except Exception:
            log.exception("Lightweight wake detection failed; disabling it and using Whisper fallback")
            self.model = None
            transcript = fallback_transcriber(audio_data) if fallback_transcriber else ""
            matched, remainder = strip_wake_word(normalize(transcript))
            return matched, remainder, transcript
