"""
============================================================
 TESTS — lyra/ear.py
============================================================
 Whisper is faked; the tests only check which arguments the
 recognizer is called with (hotword vocabulary in particular).
============================================================
"""

import sys
from types import SimpleNamespace

import numpy as np
import pytest

from lyra import config
from lyra import ear as ear_module


class FakeSegment:
    def __init__(self, text):
        self.text = text


class FakeWhisperModel:
    """Records every transcribe() call instead of running Whisper."""

    def __init__(self, *args, **kwargs):
        self.init_args = args
        self.init_kwargs = kwargs
        self.calls = []
        self.refuse_hotwords = False
        # {language: text}; None is the auto-detection pass.
        self.script = None

    def transcribe(self, audio, **kwargs):
        if self.refuse_hotwords and "hotwords" in kwargs:
            raise TypeError("transcribe() got an unexpected keyword argument 'hotwords'")
        self.calls.append(kwargs)
        if self.script is not None:
            language = kwargs["language"]
            return ([FakeSegment(self.script.get(language, ""))],
                    SimpleNamespace(language=language or "hi"))
        return [FakeSegment("open brave")], SimpleNamespace(language="en")


class FakeAudio:
    """Stands in for speech_recognition.AudioData."""

    def __init__(self, samples=160):
        self._raw = np.zeros(samples, dtype=np.int16).tobytes()

    def get_raw_data(self, convert_rate=None, convert_width=None):
        return self._raw


@pytest.fixture
def fake_whisper(monkeypatch):
    models = []

    def factory(*args, **kwargs):
        model = FakeWhisperModel(*args, **kwargs)
        models.append(model)
        return model

    fake_module = SimpleNamespace(WhisperModel=factory)
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)
    return models


def test_transcribe_passes_the_vocabulary_hotwords(fake_whisper):
    ear = ear_module.Ear()
    fake_whisper[-1].calls.clear()          # drop the warm-up call

    text = ear.transcribe_audio(FakeAudio())

    assert text == "open brave"
    kwargs = fake_whisper[-1].calls[-1]
    assert kwargs["hotwords"] == config.WHISPER_HOTWORDS
    for word in ("Lyra", "Brave", "YouTube", "terminate execution"):
        assert word in kwargs["hotwords"]


def test_hotword_support_failure_falls_back_silently(fake_whisper):
    ear = ear_module.Ear()
    model = fake_whisper[-1]
    model.calls.clear()
    model.refuse_hotwords = True

    text = ear.transcribe_audio(FakeAudio())

    assert text == "open brave"
    assert "hotwords" not in model.calls[-1]


def test_the_standard_arguments_survive(fake_whisper):
    ear = ear_module.Ear()
    model = fake_whisper[-1]
    model.calls.clear()

    ear.transcribe_audio(FakeAudio())

    kwargs = model.calls[-1]
    assert kwargs["language"] is None
    assert kwargs["task"] == "transcribe"
    assert kwargs["beam_size"] == config.WHISPER_BEAM
    assert kwargs["vad_filter"] is True
    assert kwargs["condition_on_previous_text"] is False


# ------------------------------------------------------------
# MULTILINGUAL TRANSCRIPTION
# ------------------------------------------------------------

@pytest.mark.parametrize("language", ["en", "hi", "auto"])
def test_recognition_language_can_be_forced_or_automatically_detected(fake_whisper, monkeypatch, language):
    monkeypatch.setattr(config, "WHISPER_LANGUAGE", language)
    ear = ear_module.Ear()
    model = fake_whisper[-1]
    model.calls.clear()
    ear.transcribe_audio(FakeAudio())
    assert model.calls[-1]["language"] == (None if language == "auto" else language)
    assert model.calls[-1]["task"] == "transcribe"


@pytest.mark.parametrize("model_name", ["tiny.en", "base.en", "small.en", "medium.en"])
@pytest.mark.parametrize("language", ["auto", "hi"])
def test_legacy_english_only_models_are_upgraded_for_hindi(fake_whisper, monkeypatch, model_name, language, caplog):
    monkeypatch.setattr(config, "WHISPER_MODEL", model_name)
    monkeypatch.setattr(config, "WHISPER_LANGUAGE", language)
    ear = ear_module.Ear()
    assert fake_whisper[-1].init_args == (model_name.removesuffix(".en"),)
    assert ear.model_name == model_name.removesuffix(".en")
    assert "English-only" in caplog.text


def test_explicit_english_mode_can_keep_an_english_only_model(fake_whisper, monkeypatch):
    monkeypatch.setattr(config, "WHISPER_MODEL", "base.en")
    monkeypatch.setattr(config, "WHISPER_LANGUAGE", "en")
    ear_module.Ear()
    assert fake_whisper[-1].init_args == ("base.en",)


def test_hindi_text_is_returned_without_translation_or_ascii_cleanup(fake_whisper):
    ear = ear_module.Ear()
    model = fake_whisper[-1]
    calls = []

    def transcribe(audio, **kwargs):
        calls.append(kwargs)
        return iter([FakeSegment("मुझे हिंदी में"), FakeSegment("जवाब दो।")]), SimpleNamespace(language="hi")

    model.transcribe = transcribe
    assert ear.transcribe_audio(FakeAudio()) == "मुझे हिंदी में जवाब दो।"
    assert calls[-1]["language"] is None
    assert calls[-1]["task"] == "transcribe"


@pytest.mark.parametrize("raw", [b"", b"\x00"])
def test_empty_or_malformed_audio_is_not_transcribed(fake_whisper, raw):
    ear = ear_module.Ear()
    model = fake_whisper[-1]
    model.calls.clear()
    audio = FakeAudio()
    audio._raw = raw
    assert ear.transcribe_audio(audio) == ""
    assert model.calls == []


# ------------------------------------------------------------
# WAKE-CLIP TRANSCRIPTION
# ------------------------------------------------------------
# Command transcription may detect the language per utterance; the short
# wake clip must not, or "Hey Lyra" comes back as another language.

def _scripted(model, english, auto):
    """Reply with `english` for the pinned pass and `auto` for detection."""

    model.script = {"en": english, None: auto}


def test_wake_clip_is_pinned_to_english_instead_of_being_language_detected(fake_whisper, monkeypatch):
    monkeypatch.setattr(config, "WHISPER_LANGUAGE", "auto")
    ear = ear_module.Ear()
    model = fake_whisper[-1]
    model.calls.clear()
    _scripted(model, "Hey Lyra open notepad", "हे लायरा नोटपैड खोलो")

    assert ear.transcribe_wake(FakeAudio()).strip() == "Hey Lyra open notepad"

    assert [call["language"] for call in model.calls] == ["en"]      # no auto pass needed
    # Bug 1: the English wake pass gets the English-only vocabulary; the
    # Devanagari half of WHISPER_HOTWORDS was echoed back as noise.
    assert model.calls[0]["hotwords"] == config.WHISPER_WAKE_HOTWORDS
    assert "Hey Lyra" in model.calls[0]["hotwords"]
    assert ear.last_language == "en"


def test_commands_still_detect_the_language_automatically(fake_whisper, monkeypatch):
    monkeypatch.setattr(config, "WHISPER_LANGUAGE", "auto")
    ear = ear_module.Ear()
    model = fake_whisper[-1]
    model.calls.clear()

    ear.transcribe_audio(FakeAudio())

    assert model.calls[-1]["language"] is None


def test_wake_clip_retries_with_auto_detection_when_english_misses(fake_whisper, monkeypatch):
    monkeypatch.setattr(config, "WHISPER_LANGUAGE", "auto")
    ear = ear_module.Ear()
    model = fake_whisper[-1]
    model.calls.clear()
    # The English pass mis-hears the clip into something with no wake name;
    # the auto pass returns the native-script name from WAKE_NATIVE_NAMES.
    _scripted(model, "a liar", "हे लायरा मुझे जवाब दो")

    assert ear.transcribe_wake(FakeAudio()) == "हे लायरा मुझे जवाब दो"
    assert [call["language"] for call in model.calls] == ["en", None]


def test_wake_clip_keeps_the_english_text_when_the_auto_retry_also_misses(fake_whisper, monkeypatch):
    monkeypatch.setattr(config, "WHISPER_LANGUAGE", "auto")
    ear = ear_module.Ear()
    model = fake_whisper[-1]
    model.calls.clear()
    _scripted(model, "the weather is nice", "बहुत अच्छा")

    assert ear.transcribe_wake(FakeAudio()) == "the weather is nice"
    assert [call["language"] for call in model.calls] == ["en", None]


def test_a_configured_language_is_never_retried_with_auto_detection(fake_whisper, monkeypatch):
    monkeypatch.setattr(config, "WHISPER_LANGUAGE", "hi")
    ear = ear_module.Ear()
    model = fake_whisper[-1]
    model.calls.clear()
    _scripted(model, "no wake name here", "कुछ और")

    ear.transcribe_wake(FakeAudio())

    assert [call["language"] for call in model.calls] == ["hi"]


def test_a_configured_english_mode_uses_english_for_the_wake_clip(fake_whisper, monkeypatch):
    monkeypatch.setattr(config, "WHISPER_LANGUAGE", "en")
    ear = ear_module.Ear()
    model = fake_whisper[-1]
    model.calls.clear()
    _scripted(model, "hey lyra", "कुछ और")

    assert ear.transcribe_wake(FakeAudio()).strip() == "hey lyra"
    assert [call["language"] for call in model.calls] == ["en"]
    assert ear.wake_language == "en"


def test_wake_transcription_reports_the_detected_language(fake_whisper, monkeypatch):
    monkeypatch.setattr(config, "WHISPER_LANGUAGE", "auto")
    ear = ear_module.Ear()
    model = fake_whisper[-1]
    model.calls.clear()
    assert ear.last_language is None
    _scripted(model, "hey lyra", "कुछ और")

    ear.transcribe_wake(FakeAudio())

    assert ear.last_language == "en"


def test_old_faster_whisper_gets_an_initial_prompt_instead_of_hotwords(fake_whisper):
    ear = ear_module.Ear()
    model = fake_whisper[-1]
    model.calls.clear()
    model.refuse_hotwords = True

    ear.transcribe_wake(FakeAudio())

    assert "hotwords" not in model.calls[-1]
    assert model.calls[-1]["initial_prompt"] == config.WHISPER_HOTWORDS


# ------------------------------------------------------------
# BUG 1 — ENGLISH WAKE PASS, PER-PASS LANGUAGE  (PR #12 leftover)
# ------------------------------------------------------------
# Evidence:
#   [wake-debug] engine=whisper lang=ar heard='सुन ले विर्वात' -> no wake
#   [wake-debug] engine=whisper lang=en heard='परेव परेव परेव परेव परेव परेव परेव' -> no wake

def _has_devanagari(text):
    return any("\u0900" <= char <= "\u097f" for char in text or "")


def _ear(fake_whisper, monkeypatch, speech="auto", whisper="auto"):
    monkeypatch.setattr(config, "SPEECH_LANGUAGE", speech)
    monkeypatch.setattr(config, "WHISPER_LANGUAGE", whisper)
    ear = ear_module.Ear()
    model = fake_whisper[-1]
    model.calls.clear()
    return ear, model


@pytest.mark.parametrize("speech", ["auto", "en", "hi"])
def test_the_english_wake_pass_never_receives_devanagari_hotwords(fake_whisper, monkeypatch, speech):
    ear, model = _ear(fake_whisper, monkeypatch, speech=speech)
    model.script = {}                                   # every pass misses

    ear.transcribe_wake(FakeAudio())

    english = [call for call in model.calls if call["language"] == "en"]
    assert english, "an English wake pass must run"
    for call in english:
        assert call["hotwords"] == config.WHISPER_WAKE_HOTWORDS
        assert not _has_devanagari(call["hotwords"])


def test_the_auto_retry_receives_the_bilingual_hotwords(fake_whisper, monkeypatch):
    ear, model = _ear(fake_whisper, monkeypatch)
    _scripted(model, "a liar", "हे लायरा")

    ear.transcribe_wake(FakeAudio())

    assert [call["language"] for call in model.calls] == ["en", None]
    assert model.calls[1]["hotwords"] == config.WHISPER_HOTWORDS
    assert _has_devanagari(model.calls[1]["hotwords"])


def test_the_debug_language_always_describes_the_text_on_the_same_line(fake_whisper, monkeypatch, tmp_path):
    from lyra import wake as wake_module

    ear, model = _ear(fake_whisper, monkeypatch)

    # Two scripted passes, neither a wake: the pinned English pass comes back
    # as Devanagari noise (reported "en"), the auto retry as Hindi ("hi").
    def transcribe(audio, **kwargs):
        model.calls.append(kwargs)
        if kwargs["language"] == "en":
            return [FakeSegment("परेव परेव")], SimpleNamespace(language="en")
        return [FakeSegment("सुन ले विर्वात")], SimpleNamespace(language="hi")

    model.transcribe = transcribe
    monkeypatch.setattr(config, "WAKE_VOSK_MODEL_DIR", tmp_path / "no-model")
    assessment = wake_module.WakeWordDetector().evaluate(FakeAudio(), ear.transcribe_wake)

    # The returned text is the English pass's, so its language is "en" —
    # never the retry's language paired with the first pass's text.
    assert assessment.transcript == "परेव परेव"
    assert assessment.language == "en" == ear.last_language

    lines = wake_module.format_wake_debug(assessment).splitlines()
    assert lines == [
        "[wake-debug] engine=whisper pass=1/2 lang=en heard='परेव परेव' -> no wake",
        "[wake-debug] engine=whisper pass=2/2 lang=hi heard='सुन ले विर्वात' -> no wake",
    ]


def test_hindi_mode_runs_hindi_then_english_and_never_auto_detects(fake_whisper, monkeypatch):
    ear, model = _ear(fake_whisper, monkeypatch, speech="hi")
    model.script = {"hi": "कुछ और सुनाओ", "en": "Hey Lyra"}

    assert ear.transcribe_wake(FakeAudio()) == "Hey Lyra"     # English pass only
    assert [call["language"] for call in model.calls] == ["hi", "en"]
    assert model.calls[0]["hotwords"] == config.WHISPER_HOTWORDS
    assert model.calls[1]["hotwords"] == config.WHISPER_WAKE_HOTWORDS
    assert ear.last_language == "en"
    assert [(p.language, p.matched) for p in ear.last_wake_passes] == [("hi", False), ("en", True)]


def test_hindi_mode_wakes_on_the_hindi_pass_without_an_english_pass(fake_whisper, monkeypatch):
    ear, model = _ear(fake_whisper, monkeypatch, speech="hi")
    model.script = {"hi": "हे लायरा नोटपैड खोलो", "en": "Hey Lyra"}

    assert ear.transcribe_wake(FakeAudio()) == "हे लायरा नोटपैड खोलो"
    assert [call["language"] for call in model.calls] == ["hi"]
    assert ear.last_language == "hi"


def test_hindi_mode_debug_output_names_the_matching_pass(fake_whisper, monkeypatch, tmp_path):
    from lyra import wake as wake_module

    ear, model = _ear(fake_whisper, monkeypatch, speech="hi")
    model.script = {"hi": "कुछ और सुनाओ", "en": "Hey Lyra"}
    monkeypatch.setattr(config, "WAKE_VOSK_MODEL_DIR", tmp_path / "no-model")

    assessment = wake_module.WakeWordDetector().evaluate(FakeAudio(), ear.transcribe_wake)

    assert assessment.matched
    assert wake_module.format_wake_debug(assessment).splitlines() == [
        "[wake-debug] engine=whisper pass=1/2 lang=hi heard='कुछ और सुनाओ' -> no wake",
        "[wake-debug] engine=whisper pass=2/2 lang=en heard='Hey Lyra' -> WAKE",
    ]


def test_a_single_pass_keeps_the_original_one_line_format(fake_whisper, monkeypatch, tmp_path):
    from lyra import wake as wake_module

    ear, model = _ear(fake_whisper, monkeypatch)
    _scripted(model, "Hey Lyra", "")
    monkeypatch.setattr(config, "WAKE_VOSK_MODEL_DIR", tmp_path / "no-model")

    assessment = wake_module.WakeWordDetector().evaluate(FakeAudio(), ear.transcribe_wake)

    assert wake_module.format_wake_debug(assessment) == (
        "[wake-debug] engine=whisper lang=en heard='Hey Lyra' -> WAKE"
    )


# ------------------------------------------------------------
# BUG 3 — HINDI SPEECH IS DECODED AS HINDI
# ------------------------------------------------------------

def test_hindi_mode_decodes_commands_as_hindi_without_detection(fake_whisper, monkeypatch):
    # WHISPER_LANGUAGE "auto" would detect per utterance (an hi clip came
    # back labelled "ar"); SPEECH_LANGUAGE "hi" pins Hindi regardless.
    ear, model = _ear(fake_whisper, monkeypatch, speech="hi", whisper="auto")
    model.script = {"hi": "नोटपैड खोलो"}

    assert ear.transcribe_audio(FakeAudio()) == "नोटपैड खोलो"
    assert [call["language"] for call in model.calls] == ["hi"]      # no auto retry
    assert ear.language == ear.wake_language == "hi"


def test_hindi_command_passes_carry_the_hindi_vocabulary(fake_whisper, monkeypatch):
    ear, model = _ear(fake_whisper, monkeypatch, speech="hi")
    model.script = {"hi": "आवाज़ बढ़ाओ"}

    ear.transcribe_audio(FakeAudio())

    hotwords = model.calls[-1]["hotwords"].split()
    for word in config.WHISPER_HINDI_HOTWORDS.split():
        assert word in hotwords
    assert len(hotwords) == len(set(hotwords))               # no duplicated words


def test_auto_mode_commands_keep_the_original_hotwords(fake_whisper, monkeypatch):
    ear, model = _ear(fake_whisper, monkeypatch)
    ear.transcribe_audio(FakeAudio())
    assert model.calls[-1]["hotwords"] == config.WHISPER_HOTWORDS


def test_english_mode_decodes_english(fake_whisper, monkeypatch):
    ear, model = _ear(fake_whisper, monkeypatch, speech="en", whisper="hi")
    ear.transcribe_audio(FakeAudio())
    assert model.calls[-1]["language"] == "en"


def test_command_language_and_confidence_are_logged_at_info(fake_whisper, monkeypatch, caplog):
    import logging

    ear, model = _ear(fake_whisper, monkeypatch)
    model.transcribe = lambda audio, **kwargs: (
        [FakeSegment("मौसम बताओ")], SimpleNamespace(language="hi", language_probability=0.62)
    )

    with caplog.at_level(logging.INFO, logger="lyra.ear"):
        ear.transcribe_audio(FakeAudio())

    record = next(r for r in caplog.records if "command pass" in r.getMessage())
    assert record.levelno == logging.INFO
    assert "language=hi" in record.getMessage()
    assert "probability=0.62" in record.getMessage()


def test_wake_pass_confidence_is_logged_at_debug_only(fake_whisper, monkeypatch, caplog):
    import logging

    ear, model = _ear(fake_whisper, monkeypatch)
    _scripted(model, "Hey Lyra", "")

    with caplog.at_level(logging.INFO, logger="lyra.ear"):
        ear.transcribe_wake(FakeAudio())
    assert not [r for r in caplog.records if "wake pass" in r.getMessage()]

    with caplog.at_level(logging.DEBUG, logger="lyra.ear"):
        ear.transcribe_wake(FakeAudio())
    assert [r for r in caplog.records if "wake pass" in r.getMessage()]


def test_a_weak_model_in_hindi_mode_warns_once_with_the_upgrade_command(fake_whisper, monkeypatch, caplog):
    monkeypatch.setattr(config, "SPEECH_LANGUAGE", "hi")
    monkeypatch.setattr(config, "WHISPER_MODEL", "base")
    ear_module.Ear()
    assert caplog.text.count("practical minimum") == 1
    assert "--whisper-model small" in caplog.text


def test_small_in_hindi_mode_does_not_warn(fake_whisper, monkeypatch, caplog):
    monkeypatch.setattr(config, "SPEECH_LANGUAGE", "hi")
    monkeypatch.setattr(config, "WHISPER_MODEL", "small")
    ear_module.Ear()
    assert "practical minimum" not in caplog.text


# ------------------------------------------------------------
# BUG 2 — WHISPER LOOPS ARE NOT SPEECH
# ------------------------------------------------------------
# Evidence:
#   heard='परेव परेव परेव परेव परेव परेव परेव'
#   You: ब्रेव क्रोम यूट्यूट्यूट्यू...(33x)ब  ->  Lyra answered it as speech

GLUED_LOOP = "यू" + "ट्यू" * 33 + "ब"
LOOPS = [
    GLUED_LOOP,
    " ".join(["परेव"] * 7),
    " ".join(["परेव"] * 8),
    "ब्रेव क्रोम " + GLUED_LOOP,
    "open open open open open open",
    "Thank you. Thank you. Thank you. Thank you. Thank you. Thank you.",
]


@pytest.mark.parametrize("loop", LOOPS)
def test_a_whisper_loop_is_never_returned_as_a_command(fake_whisper, monkeypatch, loop):
    ear, model = _ear(fake_whisper, monkeypatch)
    model.script = {None: loop}
    assert ear.transcribe_audio(FakeAudio()) == ""


@pytest.mark.parametrize("loop", LOOPS[:4])
def test_a_whisper_loop_is_dropped_in_hindi_mode_too(fake_whisper, monkeypatch, loop):
    ear, model = _ear(fake_whisper, monkeypatch, speech="hi")
    model.script = {"hi": loop}
    assert ear.transcribe_audio(FakeAudio()) == ""


def test_a_dropped_loop_is_logged_at_info(fake_whisper, monkeypatch, caplog):
    import logging

    ear, model = _ear(fake_whisper, monkeypatch)
    model.script = {None: " ".join(["परेव"] * 7)}
    with caplog.at_level(logging.INFO, logger="lyra.ear"):
        ear.transcribe_audio(FakeAudio())
    assert any(
        r.levelno == logging.INFO and "repetition loop" in r.getMessage() for r in caplog.records
    )


@pytest.mark.parametrize("raw, cleaned", [
    ("open open open notepad", "open notepad"),
    ("Open open OPEN notepad", "Open notepad"),
    ("यूट्यूट्यूट्यूब", "यूट्यूब"),
    ("ब्रेव क्रोम यूट्यूट्यूट्यूब खोलो", "ब्रेव क्रोम यूट्यूब खोलो"),
    ("very very good", "very good"),                 # emphasis collapses, never drops
    ("बहुत बहुत धन्यवाद", "बहुत धन्यवाद"),
])
def test_stutters_are_collapsed_not_dropped(fake_whisper, monkeypatch, raw, cleaned):
    ear, model = _ear(fake_whisper, monkeypatch)
    model.script = {None: raw}
    assert ear.transcribe_audio(FakeAudio()) == cleaned


@pytest.mark.parametrize("text", [
    "open brave", "set volume to 100000", "open notepad and write a poem",
    "what is the weather in Bhubaneswar", "नोटपैड खोलो", "मुझे कहानी सुनाओ",
    "पापा को फोन करो", "banana", "mississippi", "lalala",
    "मुझे हिंदी में जवाब दो।",
])
def test_ordinary_commands_are_untouched(text):
    assert not ear_module.is_repetition_garbage(text)
    expected = "la" if text == "lalala" else text
    assert ear_module.clean_transcript(text) == expected


def test_numbers_never_form_a_stutter():
    assert ear_module.collapse_repeats("set volume to 1000000") == "set volume to 1000000"


def test_repetition_is_judged_on_the_raw_tokens_before_collapsing():
    raw = " ".join(["परेव"] * 8)
    assert ear_module.collapse_repeats(raw) == "परेव"        # one token after collapsing...
    assert ear_module.is_repetition_garbage(raw)             # ...but a loop on the raw list
    assert ear_module.clean_transcript(raw) == ""


def test_five_repeats_are_not_yet_a_loop():
    assert ear_module.clean_transcript("no no no no no") == "no"


@pytest.mark.parametrize("speech", ["en", "auto"])
def test_the_wake_transcript_keeps_the_raw_loop_for_debugging(fake_whisper, monkeypatch, speech):
    ear, model = _ear(fake_whisper, monkeypatch, speech=speech)
    loop = " ".join(["परेव"] * 7)
    model.script = {"en": loop, None: ""}
    assert ear.transcribe_wake(FakeAudio()) == loop
