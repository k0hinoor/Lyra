"""Lightweight offline wake gate; command-quality Whisper runs only after a hit."""

import collections
import json
import logging

from . import config
from .utils import normalize, strip_wake_word

log = logging.getLogger(__name__)

# The optional Vosk model is the small US-English recognizer.
VOSK_LANGUAGE = "en"

#: One wake-gate decision, with everything the debug line prints.
WakeAssessment = collections.namedtuple(
    "WakeAssessment", "matched remainder transcript engine language"
)


def model_missing_hint(model_dir=None):
    """One-line startup hint shown when the optional Vosk wake model is absent."""

    path = config.WAKE_VOSK_MODEL_DIR if model_dir is None else model_dir
    return (
        f"Lightweight wake model not installed ({path}) — wake detection falls "
        "back to Whisper (slower, noisier). Install it with: "
        "python -m lyra.setup_wake_model   [run LYRA with --debug-wake to see "
        "what every wake clip contains]"
    )


def format_wake_debug(assessment):
    """One line per wake-gate clip, printed when WAKE_DEBUG / --debug-wake is on."""

    verdict = "WAKE" if assessment.matched else "no wake"
    return (
        f"[wake-debug] engine={assessment.engine} "
        f"lang={assessment.language or 'unknown'} "
        f"heard='{assessment.transcript}' -> {verdict}"
    )


def _transcriber_language(transcriber):
    """Language the fallback transcriber reported for the clip it just read."""

    owner = getattr(transcriber, "__self__", None)   # bound method -> owning Ear
    source = owner if owner is not None else transcriber
    return getattr(source, "last_language", None) or "unknown"


class WakeWordDetector:
    """Use a persistent Vosk acoustic model on short utterances when installed.

    If the optional Vosk model is absent, preserve the previous Whisper-based
    wake behavior rather than disabling voice mode. The caller then runs the
    regular Whisper command transcription only after a Vosk wake hit.

    When Vosk is missing, :attr:`hint` explains how to install it so the
    startup path can print exactly one line about it.
    """

    def __init__(self):
        self.model = None
        self.hint = None
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
        if self.model is None:
            self.hint = model_missing_hint(model_dir)

    @property
    def lightweight(self):
        return self.model is not None

    @property
    def engine(self):
        """Which recognizer answers for this process: "vosk" or "whisper"."""

        return "vosk" if self.lightweight else "whisper"

    def evaluate(self, audio_data, fallback_transcriber=None):
        """Return a :class:`WakeAssessment` for one captured short clip."""

        if self.model is None:
            return self._whisper_assessment(audio_data, fallback_transcriber)

        try:
            transcript = self._recognize_vosk(audio_data)
        except Exception:
            log.exception("Lightweight wake detection failed; disabling it and using Whisper fallback")
            self.model = None
            self.hint = model_missing_hint()
            return self._whisper_assessment(audio_data, fallback_transcriber)

        if transcript is None:          # unusable buffer, already logged
            return WakeAssessment(False, "", "", "vosk", VOSK_LANGUAGE)

        matched, remainder = strip_wake_word(normalize(transcript))
        return WakeAssessment(matched, remainder, transcript, "vosk", VOSK_LANGUAGE)

    def detect(self, audio_data, fallback_transcriber=None):
        """Return ``(matched, remainder, transcript)`` for a captured short clip."""

        assessment = self.evaluate(audio_data, fallback_transcriber)
        return assessment.matched, assessment.remainder, assessment.transcript

    # --------------------------------------------------------
    # INTERNALS
    # --------------------------------------------------------

    def _whisper_assessment(self, audio_data, fallback_transcriber):
        transcript = fallback_transcriber(audio_data) if fallback_transcriber else ""
        matched, remainder = strip_wake_word(normalize(transcript))
        return WakeAssessment(
            matched, remainder, transcript, "whisper",
            _transcriber_language(fallback_transcriber),
        )

    def _recognize_vosk(self, audio_data):
        """Vosk's text for one clip, or None when the buffer is unusable."""

        from vosk import KaldiRecognizer
        pcm = audio_data.get_raw_data(convert_rate=16000, convert_width=2)
        if len(pcm) % 2:
            log.warning("Ignoring odd-length wake audio buffer (%d bytes)", len(pcm))
            return None
        recognizer = KaldiRecognizer(self.model, 16000)
        recognizer.SetWords(False)
        accepted = recognizer.AcceptWaveform(pcm)
        result = json.loads(recognizer.Result() if accepted else recognizer.FinalResult())
        return result.get("text", "")
