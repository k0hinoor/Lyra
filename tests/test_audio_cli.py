"""
============================================================
 TESTS — microphone CLI plumbing
============================================================
 --devices listing, the calibrated-threshold cap, --mic-test
 and the device/energy setup voice mode performs at startup.

 speech_recognition, the Ear, the Voice and the Whisper model
 loader are faked: no sound card, no microphone, no model.
============================================================
"""

import sys
from types import SimpleNamespace

import numpy as np
import pytest

import main
from lyra import config
from lyra import ear as ear_module
from lyra import voice as voice_module


CHUNK = 64
SAMPLE_RATE = 16000
LOUD = 8000


# ------------------------------------------------------------
# FAKES
# ------------------------------------------------------------

class FakeStream:
    """Hands out the same chunk forever (a microphone hearing its room)."""

    def __init__(self, chunk=CHUNK, level=LOUD):
        self.chunk = chunk
        self.level = level
        self.reads = 0

    def read(self, size):
        assert size == self.chunk
        self.reads += 1
        return np.full(self.chunk, self.level, dtype=np.int16).tobytes()


class FakeEar:
    instances = []
    wake_transcript = "Hey Lyra open notepad"

    def __init__(self):
        self.last_language = None
        self.transcribed = []
        FakeEar.instances.append(self)

    def transcribe_audio(self, audio, language=None):
        self.last_language = "en"
        self.transcribed.append(audio)
        return "open notepad"

    def transcribe_wake(self, audio):
        self.last_language = "en"
        self.transcribed.append(audio)
        return type(self).wake_transcript


class FakeVoice:
    instances = []

    def __init__(self):
        self.spoken = []
        self.stopped = 0
        self.beeps = 0
        FakeVoice.instances.append(self)

    @property
    def is_speaking(self):
        return False

    @property
    def capturing(self):
        return False

    def speak(self, text):
        self.spoken.append(text)
        return True

    def speak_stream(self, sentences):
        self.spoken.extend(list(sentences))

    def stop(self):
        self.stopped += 1

    def beep(self):
        self.beeps += 1


@pytest.fixture
def audio_fakes(monkeypatch, tmp_path):
    """A fake speech_recognition module plus fake Ear/Voice/model classes."""

    class WaitTimeoutError(Exception):
        pass

    class Microphone:
        names = ["Speakers (Realtek(R) Audio)", "Microphone (USB Audio Device)"]
        stream_level = LOUD
        created = []

        def __init__(self, sample_rate=None, device_index=None):
            self.requested_index = device_index
            self.device_index = 1 if device_index is None else device_index
            self.SAMPLE_RATE = SAMPLE_RATE
            self.SAMPLE_WIDTH = 2
            self.CHUNK = CHUNK
            self.stream = FakeStream(level=type(self).stream_level)
            type(self).created.append(self)

        @staticmethod
        def list_microphone_names():
            return list(Microphone.names)

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

    class Recognizer:
        created = []
        calibrated_threshold = 5000.0
        listen_hook = None

        def __init__(self):
            self.energy_threshold = 1.0
            self.pause_threshold = None
            self.non_speaking_duration = None
            self.phrase_threshold = None
            self.listen_calls = []
            type(self).created.append(self)

        def adjust_for_ambient_noise(self, source, duration=0.5):
            self.energy_threshold = type(self).calibrated_threshold

        def listen(self, source, timeout=None, phrase_time_limit=None):
            self.listen_calls.append(
                {"timeout": timeout, "phrase_time_limit": phrase_time_limit}
            )
            if type(self).listen_hook is not None:
                return type(self).listen_hook(self, source)
            # voice mode: end the (otherwise endless) loop on the first listen
            raise KeyboardInterrupt

    FakeEar.instances.clear()
    FakeEar.wake_transcript = "Hey Lyra open notepad"       # tests change the class
    FakeVoice.instances.clear()

    module = SimpleNamespace(
        Microphone=Microphone, Recognizer=Recognizer, WaitTimeoutError=WaitTimeoutError,
    )
    monkeypatch.setitem(sys.modules, "speech_recognition", module)
    monkeypatch.setattr(ear_module, "Ear", FakeEar)
    monkeypatch.setattr(voice_module, "Voice", FakeVoice)
    # No optional Vosk model: the Whisper fallback and its startup hint run.
    monkeypatch.setattr(config, "WAKE_VOSK_MODEL_DIR", tmp_path / "no-wake-model")

    return SimpleNamespace(
        module=module, Microphone=Microphone, Recognizer=Recognizer,
        WaitTimeoutError=WaitTimeoutError, Ear=FakeEar, Voice=FakeVoice,
    )


# ------------------------------------------------------------
# --devices
# ------------------------------------------------------------

def _device(index, name, inputs=0, outputs=0):
    return {"index": index, "name": name,
            "max_input_channels": inputs, "max_output_channels": outputs}


DEVICES = [
    _device(0, "Microsoft Sound Mapper - Input", inputs=2),
    _device(1, "Microphone (USB Audio Device)", inputs=1),
    _device(2, "Microsoft Sound Mapper - Output", outputs=2),
    _device(3, "Speakers (Realtek(R) Audio)", outputs=2),
]


def test_devices_are_split_into_inputs_and_outputs():
    text = "\n".join(main.format_devices(DEVICES, default_input=1, default_output=3))

    assert "INPUT DEVICES" in text
    assert "Microphone (USB Audio Device)" in text
    assert "OUTPUT DEVICES" in text
    assert "Speakers (Realtek(R) Audio)" in text
    # an input device is never listed as an output and vice versa
    assert text.count("Microphone (USB Audio Device)") == 1
    assert text.count("Speakers (Realtek(R) Audio)") == 1


def test_the_windows_defaults_are_marked():
    lines = main.format_devices(DEVICES, default_input=1, default_output=3)
    marked_input = next(line for line in lines if "Microphone (USB" in line)
    marked_output = next(line for line in lines if "Speakers (Realtek" in line)

    assert "DEFAULT INPUT" in marked_input
    assert "DEFAULT OUTPUT" in marked_output
    assert "DEFAULT INPUT" not in marked_output
    assert "DEFAULT OUTPUT" not in marked_input
    # the reported indices are the ones settings.json takes
    assert "  1  " in marked_input
    assert "  3  " in marked_output


def test_device_listing_survives_an_unknown_default():
    lines = main.format_devices(DEVICES, default_input=None, default_output=None)
    assert all("DEFAULT" not in line for line in lines)
    assert any("Microphone (USB" in line for line in lines)


def test_device_listing_points_at_input_device_and_the_diagnostics():
    text = "\n".join(main.format_devices(DEVICES, default_input=1, default_output=3))
    assert "INPUT_DEVICE" in text
    assert "--mic-test" in text
    assert "--debug-wake" in text


def test_list_devices_marks_the_sounddevice_defaults(monkeypatch, capfd):
    fake_sd = SimpleNamespace(
        query_devices=lambda: DEVICES,
        default=SimpleNamespace(device=[1, 3]),
    )
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)

    assert main.list_devices() == 0

    output = capfd.readouterr().out
    assert "DEFAULT INPUT" in output
    assert "Microphone (USB Audio Device)" in output


def test_list_devices_reports_missing_sounddevice(monkeypatch, capfd):
    monkeypatch.setitem(sys.modules, "sounddevice", None)
    assert main.list_devices() == 1
    assert "sounddevice not available" in capfd.readouterr().out


# ------------------------------------------------------------
# MICROPHONE STARTUP
# ------------------------------------------------------------

MIC_NAMES = ["Speakers (Realtek(R) Audio)", "Microphone (USB Audio Device)"]


def test_input_device_label_resolves_the_configured_index():
    assert "Microphone (USB Audio Device)" in main.input_device_label(1, MIC_NAMES)
    assert "(device 1)" in main.input_device_label(1, MIC_NAMES)
    assert main.input_device_label(None, MIC_NAMES) == "system default microphone"
    assert main.input_device_label(9, MIC_NAMES) == "device 9"


def test_input_device_label_survives_an_unavailable_device_list(monkeypatch):
    monkeypatch.setitem(sys.modules, "speech_recognition", None)
    assert main.input_device_label(2, []) == "device 2"
    assert main.input_device_label(2) == "device 2"


def test_the_calibrated_threshold_is_capped():
    recognizer = SimpleNamespace(energy_threshold=5000.0)
    calibrated, applied = main.apply_energy_threshold(recognizer)

    assert calibrated == 5000.0
    assert applied == float(config.ENERGY_THRESHOLD_MAX)
    assert recognizer.energy_threshold == float(config.ENERGY_THRESHOLD_MAX)


def test_a_quiet_room_keeps_its_calibrated_threshold():
    recognizer = SimpleNamespace(energy_threshold=205.0)
    calibrated, applied = main.apply_energy_threshold(recognizer)

    assert (calibrated, applied) == (205.0, 205.0)
    assert recognizer.energy_threshold == 205.0


def test_the_energy_cap_can_be_configured(monkeypatch):
    monkeypatch.setattr(config, "ENERGY_THRESHOLD_MAX", 400.0)
    recognizer = SimpleNamespace(energy_threshold=900.0)
    assert main.apply_energy_threshold(recognizer)[1] == 400.0


# ------------------------------------------------------------
# VOICE MODE STARTUP
# ------------------------------------------------------------

def test_voice_mode_opens_the_configured_device_and_caps_the_threshold(
        audio_fakes, session, monkeypatch, capfd):
    monkeypatch.setattr(config, "INPUT_DEVICE", 1)

    main.run_voice_mode(session, always_listening=False)

    microphone = audio_fakes.Microphone.created[-1]
    recognizer = audio_fakes.Recognizer.created[-1]
    assert microphone.requested_index == 1
    assert recognizer.energy_threshold == float(config.ENERGY_THRESHOLD_MAX)
    assert session.voice is not None

    output = capfd.readouterr().out
    assert "Microphone (USB Audio Device)" in output
    assert f"Energy threshold: {config.ENERGY_THRESHOLD_MAX:.0f}" in output
    assert "capped" in output                     # 5000 was measured
    assert "setup_wake_model" in output           # one startup hint for the missing model


def test_voice_mode_uses_the_windows_default_microphone_by_default(
        audio_fakes, session, capfd):
    assert config.INPUT_DEVICE is None

    main.run_voice_mode(session, always_listening=False)

    assert audio_fakes.Microphone.created[-1].requested_index is None
    assert "Microphone (USB Audio Device)" in capfd.readouterr().out


def test_voice_mode_does_not_print_the_wake_hint_when_vosk_is_installed(
        audio_fakes, session, monkeypatch, capfd, tmp_path):
    model_dir = tmp_path / "vosk-model-small-en-us-0.15"
    model_dir.mkdir()
    monkeypatch.setattr(config, "WAKE_VOSK_MODEL_DIR", model_dir)
    fake_vosk = SimpleNamespace(Model=lambda path: object(), KaldiRecognizer=lambda model, rate: None)
    monkeypatch.setitem(sys.modules, "vosk", fake_vosk)

    main.run_voice_mode(session, always_listening=False)

    assert "setup_wake_model" not in capfd.readouterr().out


def _first_clip_then_stop():
    """One captured clip, then Ctrl+C on the next listen()."""

    calls = {"n": 0}

    def hook(recognizer, source):
        calls["n"] += 1
        if calls["n"] == 1:
            return AUDIO_CLIP
        raise KeyboardInterrupt

    return hook


def test_voice_mode_prints_a_wake_debug_line_for_a_hit(audio_fakes, session, monkeypatch, capfd):
    monkeypatch.setattr(config, "WAKE_DEBUG", True)
    audio_fakes.Recognizer.listen_hook = _first_clip_then_stop()
    audio_fakes.Ear.wake_transcript = "hey laura why is the sky blue"

    main.run_voice_mode(session, always_listening=False)

    output = capfd.readouterr().out
    assert ("[wake-debug] engine=whisper lang=en "
            "heard='hey laura why is the sky blue' -> WAKE") in output
    assert session.brain.asked == ["why is the sky blue"]


def test_voice_mode_prints_a_wake_debug_line_for_a_miss(audio_fakes, session, monkeypatch, capfd):
    monkeypatch.setattr(config, "WAKE_DEBUG", True)
    audio_fakes.Recognizer.listen_hook = _first_clip_then_stop()
    audio_fakes.Ear.wake_transcript = "see you later"

    main.run_voice_mode(session, always_listening=False)

    output = capfd.readouterr().out
    assert "[wake-debug] engine=whisper lang=en heard='see you later' -> no wake" in output
    assert session.brain.asked == []              # background speech stays background


def test_voice_mode_is_silent_about_rejected_clips_without_debug(
        audio_fakes, session, monkeypatch, capfd):
    monkeypatch.setattr(config, "WAKE_DEBUG", False)
    audio_fakes.Recognizer.listen_hook = _first_clip_then_stop()
    audio_fakes.Ear.wake_transcript = "see you later"

    main.run_voice_mode(session, always_listening=False)

    assert "[wake-debug]" not in capfd.readouterr().out


def test_debug_wake_flag_enables_the_wake_debug_output(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "WAKE_DEBUG", False)
    monkeypatch.setattr(sys, "argv", ["main.py", "--debug-wake", "--text"])

    seen = {}

    class FakeBrain:
        def __init__(self, memory):
            pass

    monkeypatch.setattr(main, "Memory", lambda: None)
    monkeypatch.setattr(main, "Session", lambda *args, **kwargs: SimpleNamespace())
    monkeypatch.setattr(main, "run_text_mode", lambda session: seen.update(wake_debug=config.WAKE_DEBUG))
    monkeypatch.setitem(sys.modules, "lyra.brain", SimpleNamespace(Brain=FakeBrain))

    main.main()

    assert config.WAKE_DEBUG is True
    assert seen["wake_debug"] is True


def test_wake_debug_stays_off_without_the_flag(monkeypatch):
    monkeypatch.setattr(config, "WAKE_DEBUG", False)
    monkeypatch.setattr(sys, "argv", ["main.py", "--text"])
    monkeypatch.setattr(main, "Memory", lambda: None)
    monkeypatch.setattr(main, "Session", lambda *args, **kwargs: SimpleNamespace())
    monkeypatch.setattr(main, "run_text_mode", lambda session: None)
    monkeypatch.setitem(sys.modules, "lyra.brain", SimpleNamespace(Brain=lambda memory: None))

    main.main()

    assert config.WAKE_DEBUG is False


# ------------------------------------------------------------
# --mic-test
# ------------------------------------------------------------

AUDIO_CLIP = SimpleNamespace(name="one wake clip")


def _clip_from_listen(recognizer, source):
    return AUDIO_CLIP


def test_mic_test_reports_a_recognised_wake_phrase(audio_fakes, capfd):
    audio_fakes.Recognizer.listen_hook = _clip_from_listen

    assert main.run_mic_test(seconds=0.02) == 0

    output = capfd.readouterr().out
    assert "Input device: Microphone (USB Audio Device)" in output
    assert "Peak level" in output
    assert "[wake-debug] engine=whisper lang=en heard='Hey Lyra open notepad' -> WAKE" in output
    assert "Wake match: YES" in output
    assert "Command after the wake phrase: 'open notepad'" in output
    assert "Energy threshold" in output
    # the clip really went through the wake transcriber
    assert audio_fakes.Ear.instances[-1].transcribed == [AUDIO_CLIP]
    assert audio_fakes.Microphone.created[-1].stream.reads > 0


def test_mic_test_reports_a_miss(audio_fakes, capfd):
    audio_fakes.Recognizer.listen_hook = _clip_from_listen
    audio_fakes.Ear.wake_transcript = "see you later"

    assert main.run_mic_test(seconds=0.02) == 1

    output = capfd.readouterr().out
    assert "heard='see you later' -> no wake" in output
    assert "Wake match: NO" in output
    assert "python -m lyra.setup_wake_model" in output


def test_mic_test_reports_a_silent_microphone(audio_fakes, capfd):
    audio_fakes.Microphone.stream_level = 0
    calls = []
    audio_fakes.Recognizer.listen_hook = lambda recognizer, source: calls.append(source)

    assert main.run_mic_test(seconds=0.02) == 1

    assert "Nothing reached the microphone" in capfd.readouterr().out
    assert calls == []                        # never asked the user to speak


def test_mic_test_reports_a_listen_timeout(audio_fakes, capfd):
    def timeout(recognizer, source):
        raise audio_fakes.WaitTimeoutError()

    audio_fakes.Recognizer.listen_hook = timeout

    assert main.run_mic_test(seconds=0.02) == 1
    assert "Nothing was captured" in capfd.readouterr().out


def test_mic_test_reports_a_missing_wake_model_hint(audio_fakes, capfd):
    audio_fakes.Recognizer.listen_hook = _clip_from_listen

    main.run_mic_test(seconds=0.02)

    assert "python -m lyra.setup_wake_model" in capfd.readouterr().out


def test_the_level_meter_bar_grows_with_the_level():
    quiet = main._level_bar(10, peak=1000)
    loud = main._level_bar(900, peak=1000)

    assert len(quiet) == len(loud) == main.MIC_TEST_BAR_WIDTH
    assert quiet.count("#") < loud.count("#")
    assert main._level_bar(1000, peak=1000).count("#") == main.MIC_TEST_BAR_WIDTH
    assert main._level_bar(0, peak=0).count("#") == 0


# ------------------------------------------------------------
# BUG 2 — A WHISPER LOOP IN THE WAKE CLIP IS NEVER A COMMAND
# ------------------------------------------------------------

def test_a_loop_after_the_wake_phrase_wakes_but_is_never_answered(
        audio_fakes, session, monkeypatch, capfd):
    monkeypatch.setattr(config, "WAKE_DEBUG", True)
    audio_fakes.Recognizer.listen_hook = _first_clip_then_stop()
    loop = "Hey Lyra " + " ".join(["परेव"] * 7)
    audio_fakes.Ear.wake_transcript = loop

    main.run_voice_mode(session, always_listening=False)

    output = capfd.readouterr().out
    assert f"heard='{loop}' -> WAKE" in output        # debug shows the raw truth
    assert session.brain.asked == []                  # the loop is never answered
    assert "(awake for" in output                     # the wake itself is kept


def test_a_stutter_after_the_wake_phrase_is_collapsed_before_routing(
        audio_fakes, session, monkeypatch):
    audio_fakes.Recognizer.listen_hook = _first_clip_then_stop()
    audio_fakes.Ear.wake_transcript = "Hey Lyra why why why is the sky blue"

    main.run_voice_mode(session, always_listening=False)

    assert session.brain.asked == ["why is the sky blue"]
