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

    def transcribe(self, audio, **kwargs):
        if self.refuse_hotwords and "hotwords" in kwargs:
            raise TypeError("transcribe() got an unexpected keyword argument 'hotwords'")
        self.calls.append(kwargs)
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
