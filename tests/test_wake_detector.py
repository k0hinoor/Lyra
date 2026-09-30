import json
import sys
from pathlib import Path
from types import SimpleNamespace

from lyra import wake as wake_module


class FakeAudio:
    def get_raw_data(self, convert_rate, convert_width):
        assert convert_rate == 16000 and convert_width == 2
        return b"\x00\x00" * 50


class FakeEar:
    """Stands in for lyra.ear.Ear's wake transcriber."""

    def __init__(self, transcript="Hey Lyra, open Notepad", language="en"):
        self.transcript = transcript
        self.last_language = language
        self.clips = []

    def transcribe_wake(self, audio):
        self.clips.append(audio)
        return self.transcript


def _missing_model(monkeypatch, tmp_path):
    monkeypatch.setattr(wake_module.config, "WAKE_VOSK_MODEL_DIR", tmp_path / "no-model")
    return wake_module.WakeWordDetector()


def _vosk_model(monkeypatch, tmp_path, transcript):
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
            return json.dumps({"text": transcript})

    monkeypatch.setitem(sys.modules, "vosk", SimpleNamespace(Model=FakeModel, KaldiRecognizer=FakeRecognizer))
    return wake_module.WakeWordDetector()


# ------------------------------------------------------------
# VOSK PATH (unchanged behaviour)
# ------------------------------------------------------------

def test_vosk_detection_does_not_call_whisper_after_a_miss(monkeypatch, tmp_path):
    detector = _vosk_model(monkeypatch, tmp_path, "see you later")
    fallback_calls = []
    assert detector.lightweight
    assert detector.detect(FakeAudio(), lambda audio: fallback_calls.append(audio))[0] is False
    assert fallback_calls == []


def test_vosk_positive_wake_is_prefix_gated(monkeypatch, tmp_path):
    detector = _vosk_model(monkeypatch, tmp_path, "hey later open notepad")
    matched, remainder, transcript = detector.detect(FakeAudio())
    assert matched
    assert remainder == "open notepad"
    assert transcript == "hey later open notepad"


# ------------------------------------------------------------
# WHISPER FALLBACK
# ------------------------------------------------------------

def test_whisper_fallback_uses_the_wake_transcriber_and_reports_the_engine(monkeypatch, tmp_path):
    detector = _missing_model(monkeypatch, tmp_path)
    ear = FakeEar()

    assessment = detector.evaluate(FakeAudio(), ear.transcribe_wake)

    assert assessment.engine == "whisper"
    assert assessment.language == "en"
    assert assessment.matched
    assert assessment.remainder == "open notepad"
    assert assessment.transcript == "Hey Lyra, open Notepad"
    assert len(ear.clips) == 1


def test_detect_still_returns_the_three_tuple(monkeypatch, tmp_path):
    detector = _missing_model(monkeypatch, tmp_path)
    assert detector.detect(FakeAudio(), FakeEar().transcribe_wake) == (
        True, "open notepad", "Hey Lyra, open Notepad",
    )


def test_the_fallback_language_is_unknown_without_a_reporting_transcriber(monkeypatch, tmp_path):
    detector = _missing_model(monkeypatch, tmp_path)
    assessment = detector.evaluate(FakeAudio(), lambda audio: "hey lyra")
    assert assessment.language == "unknown"
    assert assessment.matched


# ------------------------------------------------------------
# DEBUG OUTPUT
# ------------------------------------------------------------

def test_the_debug_line_reports_a_whisper_hit(monkeypatch, tmp_path):
    detector = _missing_model(monkeypatch, tmp_path)
    assessment = detector.evaluate(FakeAudio(), FakeEar().transcribe_wake)

    assert wake_module.format_wake_debug(assessment) == (
        "[wake-debug] engine=whisper lang=en heard='Hey Lyra, open Notepad' -> WAKE"
    )


def test_the_debug_line_reports_a_whisper_miss(monkeypatch, tmp_path):
    detector = _missing_model(monkeypatch, tmp_path)
    assessment = detector.evaluate(FakeAudio(), FakeEar(transcript="see you later").transcribe_wake)

    assert wake_module.format_wake_debug(assessment) == (
        "[wake-debug] engine=whisper lang=en heard='see you later' -> no wake"
    )


def test_the_debug_line_reports_the_vosk_engine(monkeypatch, tmp_path):
    detector = _vosk_model(monkeypatch, tmp_path, "hey lira open notepad")
    assessment = detector.evaluate(FakeAudio())

    assert wake_module.format_wake_debug(assessment) == (
        "[wake-debug] engine=vosk lang=en heard='hey lira open notepad' -> WAKE"
    )


def test_the_debug_line_survives_an_empty_transcript(monkeypatch, tmp_path):
    detector = _missing_model(monkeypatch, tmp_path)
    assessment = detector.evaluate(FakeAudio(), FakeEar(transcript="", language=None).transcribe_wake)

    assert wake_module.format_wake_debug(assessment) == (
        "[wake-debug] engine=whisper lang=unknown heard='' -> no wake"
    )


# ------------------------------------------------------------
# STARTUP HINT
# ------------------------------------------------------------

def test_a_missing_vosk_model_produces_one_install_hint(monkeypatch, tmp_path):
    detector = _missing_model(monkeypatch, tmp_path)

    assert detector.lightweight is False
    assert detector.engine == "whisper"
    assert detector.hint is not None
    assert "python -m lyra.setup_wake_model" in detector.hint
    assert "--debug-wake" in detector.hint
    assert "\n" not in detector.hint                 # one startup line


def test_an_installed_vosk_model_needs_no_hint(monkeypatch, tmp_path):
    detector = _vosk_model(monkeypatch, tmp_path, "hey lyra")

    assert detector.lightweight is True
    assert detector.engine == "vosk"
    assert detector.hint is None


def test_the_hint_names_the_directory_that_was_looked_in(tmp_path):
    model_dir = Path("/nowhere/models/vosk-model-small-en-us-0.15")
    assert str(model_dir) in wake_module.model_missing_hint(model_dir)
