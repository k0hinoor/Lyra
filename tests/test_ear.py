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
    assert model.calls[0]["hotwords"] == config.WHISPER_HOTWORDS
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
