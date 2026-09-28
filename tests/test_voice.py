"""
============================================================
 TESTS — lyra/voice.py
============================================================
 The whole Piper + sounddevice pipeline is faked: a fake
 `piper` module hands back chunks at a chosen sample rate and
 a fake `sounddevice` records everything that gets written to
 the output stream. Nothing here touches a sound card, and no
 voice pack is ever downloaded.

 The bug these guard: Voice used to open the output stream at
 a hard-coded 22050 Hz before the first chunk existed, so any
 voice pack that is not 22.05 kHz came out at the wrong pitch
 (and at the wrong speed).
============================================================
"""

import sys
from types import SimpleNamespace

import numpy as np
import pytest

from lyra import config
from lyra import voice as voice_module


# ------------------------------------------------------------
# FAKES
# ------------------------------------------------------------

class FakeChunk:
    """One Piper audio chunk: PCM bytes plus the rate they are in."""

    def __init__(self, sample_rate, audio_int16_bytes):
        self.sample_rate = sample_rate
        self.audio_int16_bytes = audio_int16_bytes


class FakePiperVoice:
    """Stands in for a loaded piper.PiperVoice."""

    def __init__(self, sample_rate=22050, has_config=True):
        if has_config:
            self.config = SimpleNamespace(sample_rate=sample_rate)
        self.rate = sample_rate
        self.spoken = []

    def synthesize(self, text):
        self.spoken.append(text)
        yield FakeChunk(self.rate, b"\x11\x22" * 40)


class FakeStream:
    """Records the parameters and every buffer the player writes."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.writes = []
        self.started = False
        self.stopped = False
        self.closed = False

    def start(self):
        self.started = True

    def write(self, pcm):
        # Mirror sounddevice's typed-buffer requirement for dtype="int16".
        assert isinstance(pcm, np.ndarray)
        assert pcm.dtype == np.int16
        self.writes.append(pcm.copy())

    def stop(self):
        self.stopped = True

    def close(self):
        self.closed = True

    @property
    def sample_rate(self):
        return self.kwargs["samplerate"]


class FakeSoundDevice:
    """Stands in for the sounddevice module."""

    def __init__(self):
        self.streams = []
        self.played = []
        self.waited = False
        self.stopped = False

    def OutputStream(self, **kwargs):
        stream = FakeStream(**kwargs)
        self.streams.append(stream)
        return stream

    def play(self, data, samplerate=None, device=None):
        self.played.append({
            "data": data,
            "samplerate": samplerate,
            "device": device,
        })

    def wait(self):
        self.waited = True

    def stop(self):
        self.stopped = True


# ------------------------------------------------------------
# FIXTURES
# ------------------------------------------------------------

@pytest.fixture
def pack(monkeypatch):
    """
    Install a fake voice pack and a fake audio device, then build
    a real Voice. Call it with the sample rate the pack reports:

        voice, piper_voice, device = pack(16000)
    """

    def install(sample_rate=22050, has_config=True):

        piper_voice = FakePiperVoice(sample_rate, has_config=has_config)

        fake_piper = SimpleNamespace(
            PiperVoice=SimpleNamespace(load=lambda path: piper_voice)
        )
        monkeypatch.setitem(sys.modules, "piper", fake_piper)
        monkeypatch.setattr(voice_module, "ensure_voice_pack", lambda: "fake.onnx")

        device = FakeSoundDevice()
        monkeypatch.setattr(voice_module, "sd", device, raising=False)
        monkeypatch.setattr(voice_module, "_SD_OK", True)

        return voice_module.Voice(), piper_voice, device

    return install


# ------------------------------------------------------------
# LOADING
# ------------------------------------------------------------

def test_the_voice_takes_its_rate_from_the_pack(pack):
    voice, _piper, _device = pack(16000)
    assert voice.sample_rate == 16000
    assert voice.ok


def test_the_pack_rate_beats_the_built_in_default(pack):
    voice, _piper, _device = pack(22050)
    assert voice.sample_rate == 22050

    voice, _piper, _device = pack(16000)
    assert voice.sample_rate == 16000


def test_a_pack_without_a_rate_falls_back_to_the_default(pack):
    voice, _piper, _device = pack(has_config=False)
    assert voice.sample_rate == 22050


# ------------------------------------------------------------
# PLAYBACK
# ------------------------------------------------------------

def test_playback_uses_the_rate_of_the_audio_written(pack):
    voice, _piper, device = pack(16000)

    voice.speak_stream(iter(["Turned the volume up for you."]))

    stream = device.streams[0]
    assert stream.sample_rate == 16000
    np.testing.assert_array_equal(
        stream.writes[0], np.frombuffer(b"\x11\x22" * 40, dtype=np.int16)
    )
    assert stream.writes[0].dtype == np.int16
    assert stream.started and stream.stopped and stream.closed


def test_a_stale_default_rate_cannot_leak_into_playback(pack):
    # Voice.__init__ may have guessed 22050 before the first chunk
    # arrived; the stream still has to open at the real rate.
    voice, _piper, device = pack(16000)
    voice.sample_rate = 22050

    voice.speak_stream(iter(["This sentence is long enough to be one chunk."]))

    assert device.streams[0].sample_rate == 16000


def test_sentences_are_synthesized_in_order(pack):
    voice, piper_voice, _device = pack(22050)

    voice.speak_stream(iter(["First sentence here.", "Second sentence here."]))

    assert piper_voice.spoken == ["First sentence here.", "Second sentence here."]


def test_spoken_text_is_cleaned_before_synthesis(pack):
    voice, piper_voice, _device = pack()

    voice.speak_stream(iter(["**Volume** is at 40% now"]))

    assert piper_voice.spoken[0] == "Volume is at 40 percent now"


def test_a_pause_is_written_between_sentences(pack):
    voice, _piper, device = pack(16000)

    voice.speak_stream(iter(["One sentence.", "Another sentence."]))

    speech = np.frombuffer(b"\x11\x22" * 40, dtype=np.int16)
    silence = np.zeros(int(16000 * config.VOICE_SENTENCE_SILENCE), dtype=np.int16)
    writes = device.streams[0].writes
    assert len(writes) == 4
    for actual, expected in zip(writes, [speech, silence, speech, silence]):
        np.testing.assert_array_equal(actual, expected)


def test_one_stream_for_the_whole_reply(pack):
    voice, _piper, device = pack()

    voice.speak_stream(iter(["One sentence.", "Another sentence.", "And a third."]))

    assert len(device.streams) == 1


def test_nothing_to_say_opens_no_stream(pack):
    voice, _piper, device = pack()

    voice.speak_stream(iter(["  ", "", None]))
    voice.speak_stream(iter([]))

    assert device.streams == []


def test_speak_splits_text_into_sentences(pack):
    voice, piper_voice, _device = pack()

    voice.speak("First sentence is here. Second sentence is here.")

    assert piper_voice.spoken == [
        "First sentence is here.",
        "Second sentence is here.",
    ]


# ------------------------------------------------------------
# SILENT MODE
# ------------------------------------------------------------

def test_a_broken_voice_prints_instead_of_playing(pack, capfd):
    voice, _piper, device = pack()
    voice.ok = False

    voice.speak_stream(iter(["Hello there.", "  ", None]))

    assert device.streams == []
    assert "Lyra: Hello there." in capfd.readouterr().out


def test_the_beep_uses_the_loaded_rate(pack):
    voice, _piper, device = pack(16000)

    voice.beep()

    assert device.played[0]["samplerate"] == 16000
    assert device.played[0]["device"] == config.OUTPUT_DEVICE
    assert device.waited


def test_multiple_responses_reuse_piper_and_close_each_stream(pack):
    voice, piper_voice, device = pack()

    voice.speak("First response.")
    voice.speak("Second response.")

    assert piper_voice.spoken == ["First response.", "Second response."]
    assert len(device.streams) == 2
    assert all(stream.closed and stream.stopped for stream in device.streams)


def test_pcm_validation_rejects_odd_byte_count(pack):
    voice, _piper, _device = pack()
    with pytest.raises(ValueError, match="even byte count"):
        voice._pcm_to_int16(bytes([0]))


def test_pcm_validation_rejects_unexpected_dtype(pack):
    voice, _piper, _device = pack()
    with pytest.raises(TypeError, match="must be int16"):
        voice._pcm_to_int16(np.zeros(4, dtype=np.float32))


def test_stop_silences_playback(pack):
    voice, _piper, device = pack()

    voice.stop()

    assert device.stopped
