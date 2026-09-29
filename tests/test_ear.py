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
    assert kwargs["language"] == "en"
    assert kwargs["beam_size"] == config.WHISPER_BEAM
    assert kwargs["vad_filter"] is True
    assert kwargs["condition_on_previous_text"] is False
