import json
import sys
from pathlib import Path
from types import SimpleNamespace

from lyra import wake as wake_module


class FakeAudio:
    def get_raw_data(self, convert_rate, convert_width):
        assert convert_rate == 16000 and convert_width == 2
        return b"\x00\x00" * 50


def test_vosk_detection_does_not_call_whisper_after_a_miss(monkeypatch, tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    monkeypatch.setattr(wake_module.config, "WAKE_VOSK_MODEL_DIR", model_dir)

    class FakeModel:
        def __init__(self, path):
            self.path = path

    class FakeRecognizer:
        def __init__(self, model, rate):
            self.model, self.rate = model, rate

        def SetWords(self, _enabled):
            pass

        def AcceptWaveform(self, _pcm):
            return True

        def Result(self):
            return json.dumps({"text": "see you later"})

    monkeypatch.setitem(sys.modules, "vosk", SimpleNamespace(Model=FakeModel, KaldiRecognizer=FakeRecognizer))
    detector = wake_module.WakeWordDetector()
    fallback_calls = []
    assert detector.lightweight
    assert detector.detect(FakeAudio(), lambda audio: fallback_calls.append(audio))[0] is False
    assert fallback_calls == []


def test_vosk_positive_wake_is_prefix_gated(monkeypatch, tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    monkeypatch.setattr(wake_module.config, "WAKE_VOSK_MODEL_DIR", model_dir)

    class FakeModel:
        def __init__(self, _path):
            pass

    class FakeRecognizer:
        def __init__(self, _model, _rate):
            pass

        def SetWords(self, _enabled):
            pass

        def AcceptWaveform(self, _pcm):
            return True

        def Result(self):
            return '{"text":"hey later open notepad"}'

    monkeypatch.setitem(sys.modules, "vosk", SimpleNamespace(Model=FakeModel, KaldiRecognizer=FakeRecognizer))
    detector = wake_module.WakeWordDetector()
    matched, remainder, transcript = detector.detect(FakeAudio())
    assert matched
    assert remainder == "open notepad"
    assert transcript == "hey later open notepad"
