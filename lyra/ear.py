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

 - transcribe_audio()  commands, in the configured language
   (SPEECH_LANGUAGE "hi" = always Hindi; "auto" = WHISPER_LANGUAGE,
   which may detect per utterance). Returns CLEANED text: Whisper
   repetition loops are dropped and stutters collapsed, so a command
   can never be garbage.
 - transcribe_wake()   the short wake-gate clip, decoded in pinned
   languages so per-clip detection cannot guess wrong. Returns the RAW
   text, so --debug-wake always shows what Whisper really produced.
============================================================
"""

import collections
import logging
import re

import numpy as np

from . import config
from .utils import normalize, strip_wake_word

log = logging.getLogger(__name__)

# Sentinel: "no language was forced for this call, use the configured one".
_DEFAULT_LANGUAGE = object()

#: One wake-clip decoding pass: the language that produced ``text`` (the
#: pinned one, or what Whisper detected), the text, and whether it holds an
#: accepted wake phrase.
WakePass = collections.namedtuple("WakePass", "language text matched")


# ------------------------------------------------------------
# WHISPER REPETITION LOOPS
# ------------------------------------------------------------
# On unclear audio Whisper can get stuck repeating one token:
#   "परेव परेव परेव परेव परेव परेव परेव"
#   "ब्रेव क्रोम यूट्यूट्यूट्यूट्यू...(33x)ब"
# Such a transcript is not speech and must never reach the skills or the
# chat model. Repetition is judged on the RAW token list first; only then
# are harmless stutters collapsed ("open open open notepad" -> "open
# notepad", "यूट्यूट्यूट्यूब" -> "यूट्यूब"). Genuine emphasis survives:
# "very very good" becomes "very good", it is never dropped.

LOOP_MIN_TOKENS = 6             # a spaced loop needs at least this many tokens...
LOOP_MAX_UNIQUE_RATIO = 0.34    # ...and fewer than 34% distinct tokens
LOOP_MIN_TOKEN_CHARS = 40       # a glued loop: one token this long...
LOOP_MAX_UNIQUE_CHARS = 0.20    # ...made of fewer than 20% distinct characters

# One "letter" for the glued-stutter pattern: a Unicode letter or a
# Devanagari combining mark (Python's \w does not match vowel signs such as
# "ू" or the virama, so they are listed explicitly). Digits never form a
# stutter unit: "1000000" is a number, not a loop.
_LETTER = r"(?:[^\W\d_]|[\u0900-\u0903\u093a-\u094f\u0951-\u0957\u0962\u0963])"
# A unit of 2+ letters repeated three or more times back to back.
_GLUED_STUTTER = re.compile(r"(" + _LETTER + r"{2,}?)\1{2,}")


def _token_key(token):
    """Comparable form of one token: lowercase, no punctuation."""

    return normalize(token) or token


def is_repetition_garbage(text):
    """True when a raw transcript is a Whisper loop rather than speech.

    A loop is >= LOOP_MIN_TOKENS tokens with < 34% distinct tokens, or any
    single token of >= LOOP_MIN_TOKEN_CHARS characters built from < 20%
    distinct characters. Judged on the raw tokens, BEFORE collapsing: after
    collapsing, "परेव" x8 is one token and would slip through.
    """

    keys = [_token_key(token) for token in (text or "").split()]
    if not keys:
        return False

    if len(keys) >= LOOP_MIN_TOKENS and len(set(keys)) / len(keys) < LOOP_MAX_UNIQUE_RATIO:
        return True

    return any(
        len(key) >= LOOP_MIN_TOKEN_CHARS and len(set(key)) / len(key) < LOOP_MAX_UNIQUE_CHARS
        for key in keys
    )


def collapse_repeats(text):
    """Collapse immediate word repeats and glued stutters; keep everything else.

    "open open open notepad" -> "open notepad"
    "यूट्यूट्यूट्यूब"          -> "यूट्यूब"
    "very very good"         -> "very good"

    Text without any repeat is returned unchanged (whitespace included).
    """

    text = (text or "").strip()
    tokens = text.split()
    out = []
    last_key = None
    changed = False

    for token in tokens:
        collapsed = _GLUED_STUTTER.sub(r"\1", token)
        changed = changed or collapsed != token
        key = _token_key(collapsed)
        if out and key == last_key:
            changed = True
            continue
        out.append(collapsed)
        last_key = key

    return " ".join(out) if changed else text


def clean_transcript(text):
    """What a command may contain: '' for a Whisper loop, else collapsed text.

    A dropped loop is logged at INFO and the turn is skipped, exactly like a
    filler utterance.
    """

    text = (text or "").strip()
    if not text:
        return ""
    if is_repetition_garbage(text):
        log.info("Dropped a Whisper repetition loop (not speech): %.160r", text)
        return ""
    return collapse_repeats(text)


def _merge_hotwords(*vocabularies):
    """Join hotword strings, dropping repeated words, first spelling wins."""

    seen = set()
    words = []
    for vocabulary in vocabularies:
        for word in (vocabulary or "").split():
            if word not in seen:
                seen.add(word)
                words.append(word)
    return " ".join(words)


class Ear:

    def __init__(self):

        from faster_whisper import WhisperModel

        # SPEECH_LANGUAGE "hi"/"en" pins recognition; "auto" defers to
        # WHISPER_LANGUAGE (which may itself be "auto" = detect per utterance).
        stt_language = config.stt_language()
        self.language = None if stt_language == "auto" else stt_language
        # Language of the text the last call returned: what Whisper detected
        # in auto mode, or the language that was pinned. The wake debug line
        # (WAKE_DEBUG / --debug-wake) prints it next to that same text.
        self.last_language = None
        # Every pass of the last wake clip, in order (see transcribe_wake).
        self.last_wake_passes = []
        model_name = config.WHISPER_MODEL
        # Existing Windows settings may still contain base.en. That model
        # can never understand Hindi, even with language="hi" requested.
        if self.language != "en" and model_name in {"tiny.en", "base.en", "small.en", "medium.en"}:
            multilingual = model_name.removesuffix(".en")
            log.warning(
                "%s is English-only; using multilingual %s for WHISPER_LANGUAGE=%s. "
                "Update WHISPER_MODEL in settings.json to remove .en.",
                model_name, multilingual, stt_language,
            )
            model_name = multilingual
        self.model_name = model_name
        if self.language == "hi" and model_name.split(".")[0] in {"tiny", "base"}:
            log.warning(
                "WHISPER_MODEL=%s mishears Hindi; 'small' is the practical minimum "
                "(python -m lyra.setup_voice --language hi --set-default --whisper-model small).",
                model_name,
            )
        print(f"Loading Whisper ({model_name}, language={stt_language})...")

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
        Returns the CLEANED transcript string ('' on failure or when Whisper
        produced a repetition loop instead of speech).

        `language` overrides the configured language for this one call
        (None = let Whisper detect the language). In SPEECH_LANGUAGE="hi" the
        configured language is always Hindi: no detection, no auto retry.
        """

        language = self.language if language is _DEFAULT_LANGUAGE else language
        text, reported = self._transcribe(
            audio_data, language,
            hotwords=self._command_hotwords(language), purpose="command",
        )
        self.last_language = reported
        return clean_transcript(text)

    def transcribe_wake(self, audio_data):
        """Transcribe one wake-gate clip and return the best RAW wake transcript.

        The raw text (loops included) is returned on purpose: --debug-wake
        must show what Whisper really heard. Commands taken from a wake clip
        are cleaned by the caller with clean_transcript().

        Passes, stopping at the first one that holds an accepted wake phrase:

        * SPEECH_LANGUAGE="hi": Hindi (bilingual hotwords, so "हे लायरा" is
          grounded), then English (English-only hotwords) so a spoken
          "Hey Lyra" still wakes. No auto-detect pass.
        * otherwise: the pinned wake language (English unless another one is
          configured; English passes get the English-only WHISPER_WAKE_HOTWORDS),
          then — only when recognition is "auto" — one auto-detect retry with
          the bilingual WHISPER_HOTWORDS.

        ``last_wake_passes`` records every pass as a WakePass and
        ``last_language`` is the language of the pass whose text is returned,
        so the debug line never pairs one pass's language with another
        pass's text.
        """

        passes = []
        for language, hotwords in self._wake_passes():
            text, reported = self._transcribe(
                audio_data, language, hotwords=hotwords, purpose="wake",
            )
            matched = bool(text) and _contains_wake_phrase(text)
            passes.append(WakePass(reported, text, matched))
            if matched:
                break

        self.last_wake_passes = passes
        chosen = next((p for p in passes if p.matched), None) \
            or next((p for p in passes if p.text), None) \
            or passes[0]
        self.last_language = chosen.language
        return chosen.text

    def _wake_passes(self):
        """[(language, hotwords)] for one wake clip, in decoding order."""

        english_hotwords = getattr(config, "WHISPER_WAKE_HOTWORDS", "")
        bilingual_hotwords = getattr(config, "WHISPER_HOTWORDS", "")

        if config.SPEECH_LANGUAGE == "hi":
            return [("hi", bilingual_hotwords), ("en", english_hotwords)]

        first = self.wake_language
        passes = [(first, english_hotwords if first == "en" else bilingual_hotwords)]
        if self.language is None:
            passes.append((None, bilingual_hotwords))
        return passes

    def _command_hotwords(self, language):
        """Vocabulary bias for one command pass.

        Hindi mode adds the short Hindi command vocabulary to Hindi (or
        detected) passes; "auto"/"en" keep the bilingual WHISPER_HOTWORDS
        exactly as before.
        """

        hotwords = getattr(config, "WHISPER_HOTWORDS", "")
        if config.SPEECH_LANGUAGE == "hi" and language in ("hi", None):
            return _merge_hotwords(getattr(config, "WHISPER_HINDI_HOTWORDS", ""), hotwords)
        return hotwords

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

    def _transcribe(self, audio_data, language, hotwords=None, purpose="command"):
        """One Whisper call with command-quality settings.

        Returns ``(text, language)``: the raw text ('' on failure) and the
        language that produced it (the pinned one, or Whisper's detection).
        """

        audio_array = self._audio_array(audio_data)
        if audio_array is None:
            return "", language or "unknown"

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
        # heard as "breathe" and "terminate" not as "terminal". The wake
        # passes pass their own list (English-only for the English pass).
        if hotwords is None:
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
            reported = getattr(info, "language", None) or language or "unknown"
            probability = getattr(info, "language_probability", None)
            log.log(
                logging.INFO if purpose == "command" else logging.DEBUG,
                "Whisper %s pass: language=%s (requested %s) probability=%s",
                purpose, reported, language or "auto",
                f"{probability:.2f}" if isinstance(probability, (int, float)) else "n/a",
            )
            return text.strip(), reported

        except Exception:
            log.exception("Whisper transcription failed")
            return "", language or "unknown"


def _contains_wake_phrase(transcript):
    """True when a transcript holds an accepted wake phrase at its start."""

    return strip_wake_word(normalize(transcript or ""))[0]
