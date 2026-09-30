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

def test_a_broken_voice_plays_nothing_and_leaves_printing_to_the_session(pack, capfd):
    # Printing every reply as "Lyra: ..." is the Session's job now; if the
    # Voice also printed in silent mode, every reply would appear twice.
    voice, _piper, device = pack()
    voice.ok = False

    voice.speak_stream(iter(["Hello there.", "  ", None]))

    assert device.streams == []
    assert "Hello there." not in capfd.readouterr().out


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


# ------------------------------------------------------------
# VOICE SPEED  (VOICE_SPEED -> length_scale)
# ------------------------------------------------------------

class ConfigAwareFakePiperVoice(FakePiperVoice):
    """Records the synthesis config the way piper 1.3 accepts it."""

    def __init__(self, sample_rate=22050):
        super().__init__(sample_rate)
        self.configs = []

    def synthesize(self, text, config=None, **kwargs):
        self.configs.append(config)
        self.spoken.append(text)
        yield FakeChunk(self.rate, b"\x11\x22" * 40)


def _pack_with_speed(monkeypatch, speed):
    piper_voice = ConfigAwareFakePiperVoice()

    class FakeSynthesisConfig:
        def __init__(self, length_scale=None):
            self.length_scale = length_scale

    fake_piper = SimpleNamespace(
        PiperVoice=SimpleNamespace(load=lambda path: piper_voice),
        SynthesisConfig=FakeSynthesisConfig,
    )
    monkeypatch.setitem(sys.modules, "piper", fake_piper)
    monkeypatch.setattr(voice_module, "ensure_voice_pack", lambda: "fake.onnx")
    monkeypatch.setattr(voice_module, "sd", FakeSoundDevice(), raising=False)
    monkeypatch.setattr(voice_module, "_SD_OK", True)
    monkeypatch.setattr(config, "VOICE_SPEED", speed)

    return voice_module.Voice(), piper_voice


def test_synthesis_receives_the_inverse_of_voice_speed(monkeypatch):
    voice, piper_voice = _pack_with_speed(monkeypatch, 1.15)

    voice.speak_stream(iter(["One sentence here."]))

    (synth_config,) = piper_voice.configs
    assert synth_config.length_scale == pytest.approx(1.0 / 1.15)


def test_a_slower_voice_gets_a_bigger_length_scale(monkeypatch):
    voice, piper_voice = _pack_with_speed(monkeypatch, 0.8)

    voice.speak_stream(iter(["One sentence here."]))

    assert piper_voice.configs[0].length_scale == pytest.approx(1.25)


def test_old_piper_without_config_still_speaks(monkeypatch):
    # synthesize(text) only — the speed kwargs must degrade gracefully
    voice, _piper = _pack_with_speed(monkeypatch, 1.15)

    def old_synthesize(text):
        yield FakeChunk(22050, b"\x11\x22" * 40)

    _piper.synthesize = old_synthesize

    voice.speak_stream(iter(["One sentence here."]))     # must not raise


# ------------------------------------------------------------
# ATOMIC VOICE DOWNLOAD
# ------------------------------------------------------------

class StreamingResponse:
    def __init__(self, chunks, total=None, ok=True):
        self._chunks = chunks
        self.headers = {"content-length": str(total)} if total else {}
        self._ok = ok

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        if not self._ok:
            raise RuntimeError("HTTP error")

    def iter_content(self, chunk_size=None):
        for chunk in self._chunks:
            yield chunk


def test_download_is_renamed_into_place_only_when_complete(monkeypatch, tmp_path):
    target = tmp_path / "voice.onnx"
    payload = b"0123456789" * 100

    monkeypatch.setattr(
        voice_module.requests, "get",
        lambda url, **kwargs: StreamingResponse([payload], total=len(payload)),
    )

    voice_module._download_file("https://example.invalid/voice.onnx", target)

    assert target.read_bytes() == payload
    assert not (tmp_path / "voice.onnx.part").exists()


def test_a_truncated_download_leaves_no_model_behind(monkeypatch, tmp_path):
    target = tmp_path / "voice.onnx"

    monkeypatch.setattr(
        voice_module.requests, "get",
        lambda url, **kwargs: StreamingResponse([b"12345"], total=1000),
    )

    with pytest.raises(IOError, match="incomplete"):
        voice_module._download_file("https://example.invalid/voice.onnx", target)

    assert not target.exists()
    assert not (tmp_path / "voice.onnx.part").exists()


def test_an_empty_download_is_refused(monkeypatch, tmp_path):
    target = tmp_path / "voice.onnx"

    monkeypatch.setattr(
        voice_module.requests, "get",
        lambda url, **kwargs: StreamingResponse([b""], total=None),
    )

    with pytest.raises(IOError, match="empty"):
        voice_module._download_file("https://example.invalid/voice.onnx", target)

    assert not target.exists()


def test_an_interrupted_download_is_retried_next_run(monkeypatch, tmp_path):
    target = tmp_path / "voice.onnx"

    # a stale .part from a killed previous run must not block the retry
    stale = tmp_path / "voice.onnx.part"
    stale.write_bytes(b"partial junk")

    payload = b"complete voice model"
    monkeypatch.setattr(
        voice_module.requests, "get",
        lambda url, **kwargs: StreamingResponse([payload], total=len(payload)),
    )

    voice_module._download_file("https://example.invalid/voice.onnx", target)

    assert target.read_bytes() == payload
    assert not stale.exists()


def test_ensure_voice_pack_skips_the_download_when_complete(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "VOICE_DIR", tmp_path)
    model = tmp_path / (config.VOICE_MODEL + ".onnx")
    model.write_bytes(b"model")
    (tmp_path / (config.VOICE_MODEL + ".onnx.json")).write_text("{}", encoding="utf-8")

    def refuse(*args, **kwargs):
        raise AssertionError("nothing may be downloaded")

    monkeypatch.setattr(voice_module.requests, "get", refuse)

    assert voice_module.ensure_voice_pack() == model


# ------------------------------------------------------------
# SPEAKER ECHO  (barge-in must not interrupt LYRA with her own voice)
# ------------------------------------------------------------

def test_the_capture_flag_is_off_until_the_watcher_needs_it(pack):
    voice, _piper, _device = pack()

    assert voice.capturing is False

    voice.start_capture()
    assert voice.capturing is True

    voice.end_capture()
    assert voice.capturing is False


def test_what_she_says_is_remembered_for_echo_detection(pack):
    voice, _piper, _device = pack()

    voice.speak_stream(iter(["Opening Notepad for you right now."]))

    assert voice.looks_like_echo("Opening Notepad for you")
    assert not voice.looks_like_echo("play some lo-fi music")


def test_an_empty_phrase_is_never_an_echo(pack):
    voice, _piper, _device = pack()
    voice.remember_spoken("Opening Notepad")

    assert voice.looks_like_echo("") is False
    assert voice.looks_like_echo("   ") is False


def test_the_overlap_needed_for_an_echo_can_be_tightened(pack):
    voice, _piper, _device = pack()
    voice.remember_spoken("Opening Notepad for you")

    # her own words, heard late, with the user's own tail on the end
    heard = "opening notepad for you and play some music"

    assert voice.looks_like_echo(heard)                 # 4 of 7 words
    assert not voice.looks_like_echo(heard, min_overlap=0.9)


def test_her_words_are_forgotten_after_the_echo_window(pack, monkeypatch):
    voice, _piper, _device = pack()
    now = [1000.0]
    monkeypatch.setattr(voice_module.time, "monotonic", lambda: now[0])

    voice.remember_spoken("Opening Notepad for you.")
    assert voice.looks_like_echo("Opening Notepad")

    now[0] += config.INTERRUPT_ECHO_WINDOW_SECONDS + 1

    assert not voice.looks_like_echo("Opening Notepad")


def test_the_remembered_words_do_not_grow_forever(pack, monkeypatch):
    voice, _piper, _device = pack()
    now = [1000.0]
    monkeypatch.setattr(voice_module.time, "monotonic", lambda: now[0])

    voice.remember_spoken("one two three")
    now[0] += config.INTERRUPT_ECHO_WINDOW_SECONDS + 1
    voice.remember_spoken("four five")

    assert [word for word, _stamp in voice._spoken_words] == ["four", "five"]


# ------------------------------------------------------------
# AUTOMATIC ENGLISH / HINDI PACKS
# ------------------------------------------------------------

@pytest.fixture
def bilingual_pack(monkeypatch, tmp_path):
    from pathlib import Path
    voices = {
        config.VOICE_MODEL: FakePiperVoice(22050),
        config.HINDI_VOICE_MODEL: FakePiperVoice(16000),
    }
    downloads = []
    loads = []

    def ensure(model=None):
        model = model or config.VOICE_MODEL
        downloads.append(model)
        return tmp_path / (model + ".onnx")

    def load(path):
        model = Path(path).name.removesuffix(".onnx")
        loads.append(model)
        return voices[model]

    monkeypatch.setitem(sys.modules, "piper", SimpleNamespace(PiperVoice=SimpleNamespace(load=load)))
    monkeypatch.setattr(voice_module, "ensure_voice_pack", ensure)
    device = FakeSoundDevice()
    monkeypatch.setattr(voice_module, "sd", device, raising=False)
    monkeypatch.setattr(voice_module, "_SD_OK", True)
    return SimpleNamespace(
        build=lambda language="en": voice_module.Voice(language=language),
        english=voices[config.VOICE_MODEL], hindi=voices[config.HINDI_VOICE_MODEL],
        device=device, downloads=downloads, loads=loads,
    )


@pytest.mark.parametrize("model", ["hi_IN-priyamvada-medium", "hi_IN-pratham-medium", "hi_IN-rohan-medium"])
def test_hindi_download_urls_use_hi_not_the_old_hardcoded_en(model):
    name = model.split("-")[1]
    onnx, metadata = voice_module._voice_urls(model)
    assert onnx == f"{config.VOICE_REPO}/hi/hi_IN/{name}/medium/{model}.onnx"
    assert metadata == onnx + ".json"


def test_english_download_urls_remain_compatible():
    assert voice_module._voice_urls()[0] == (
        f"{config.VOICE_REPO}/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
    )


def test_hindi_text_is_sent_intact_to_a_hindi_voice(bilingual_pack):
    pack = bilingual_pack
    voice = pack.build()
    text = "बिल्कुल, मैं आपको हिंदी में प्रतिक्रिया दे सकता हूं।"
    assert voice.speak(text) is True
    assert pack.hindi.spoken == [text]
    assert pack.english.spoken == []
    assert pack.device.streams[0].sample_rate == 16000
    assert pack.device.streams[0].writes[0].size > 0
    assert voice.looks_like_echo("मैं आपको हिंदी में प्रतिक्रिया दे सकता हूं")


def test_a_mixed_script_sentence_uses_the_hindi_voice(bilingual_pack):
    pack = bilingual_pack
    voice = pack.build()
    assert voice.speak("मुझे Arijit Singh और jazz पसंद है।") is True
    assert pack.hindi.spoken == ["मुझे Arijit Singh और jazz पसंद है।"]
    assert pack.english.spoken == []


def test_each_language_is_loaded_once_and_downloaded_only_on_first_use(bilingual_pack):
    pack = bilingual_pack
    voice = pack.build()
    assert pack.loads == [config.VOICE_MODEL]
    voice.speak("Hello there.")
    assert pack.loads == [config.VOICE_MODEL]
    voice.speak("नमस्ते, मैं लायरा हूँ।")
    voice.speak("मुझे संगीत पसंद है।")
    assert pack.loads == [config.VOICE_MODEL, config.HINDI_VOICE_MODEL]
    assert pack.downloads == [config.VOICE_MODEL, config.HINDI_VOICE_MODEL]


def test_rate_changes_between_languages_reopen_streams_without_losing_sentences(bilingual_pack):
    pack = bilingual_pack
    voice = pack.build()
    assert voice.speak_stream(iter(["English first.", "फिर हिंदी में जवाब।", "English again."])) is True
    assert [stream.sample_rate for stream in pack.device.streams] == [22050, 16000, 22050]
    assert all(stream.started and stream.closed and stream.stopped for stream in pack.device.streams)
    assert pack.english.spoken == ["English first.", "English again."]
    assert pack.hindi.spoken == ["फिर हिंदी में जवाब।"]
    assert voice._active_stream is None


def test_packs_at_the_same_rate_can_share_one_stream(bilingual_pack):
    pack = bilingual_pack
    pack.hindi.rate = 22050
    voice = pack.build()
    voice.speak_stream(iter(["English first.", "फिर हिंदी में जवाब।", "English again."]))
    assert len(pack.device.streams) == 1
    assert len(pack.device.streams[0].writes) == 6


def test_hindi_voice_test_does_not_need_an_english_pack(bilingual_pack):
    pack = bilingual_pack
    voice = pack.build(language="hi")
    assert voice.ok
    assert pack.loads == [config.HINDI_VOICE_MODEL]
    assert pack.downloads == [config.HINDI_VOICE_MODEL]
    assert voice.speak("नमस्ते, मैं लायरा हूँ।") is True
    assert pack.english.spoken == []
    assert pack.loads == [config.HINDI_VOICE_MODEL]


def test_a_failed_hindi_pack_is_visible_and_does_not_break_english(bilingual_pack, monkeypatch, caplog):
    pack = bilingual_pack
    voice = pack.build()
    failures = []

    def fail(model=None):
        failures.append(model)
        raise OSError("offline")

    monkeypatch.setattr(voice_module, "ensure_voice_pack", fail)
    assert voice.speak_stream(iter(["हिंदी में जवाब।", "English still works."])) is True
    assert pack.english.spoken == ["English still works."]
    assert pack.hindi.spoken == []
    assert "setup_voice --language hi" in caplog.text
    assert voice.speak("हिंदी में फिर जवाब।") is False
    assert failures == [config.HINDI_VOICE_MODEL]  # no download retry on every sentence
    assert voice.ok


def test_empty_audio_from_piper_is_reported_instead_of_silent_success(pack, caplog):
    voice, piper_voice, device = pack()
    piper_voice.synthesize = lambda text: iter([])
    assert voice.speak("This should have been spoken.") is False
    assert "produced no audio" in caplog.text
    assert device.streams == []


def test_canceled_synthesis_is_not_revived_by_the_next_reply(bilingual_pack, monkeypatch):
    import threading
    pack = bilingual_pack
    voice = pack.build()
    entered = threading.Event()
    release = threading.Event()
    completed = threading.Event()
    original_synthesize = voice._synthesize

    def delayed_synthesize(text):
        if text == "नमस्ते।":
            entered.set()
            release.wait(2)
            completed.set()
            return 16000, b"\x11\x22" * 40
        return original_synthesize(text)

    monkeypatch.setattr(voice, "_synthesize", delayed_synthesize)
    worker = threading.Thread(target=voice.speak, args=("नमस्ते।",), daemon=True)
    worker.start()
    assert entered.wait(1)
    voice.stop()
    worker.join(1)
    assert not worker.is_alive(), "stop must not wait for a download/inference to finish"
    assert voice.speak("A new English reply.") is True
    release.set()
    assert completed.wait(1)
    assert len(pack.device.streams) == 1
    assert pack.english.spoken == ["A new English reply."]
    assert not voice.looks_like_echo("नमस्ते")


def test_hindi_packs_are_stored_separately_from_existing_english_packs(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "VOICE_DIR", tmp_path)
    english = tmp_path / (config.VOICE_MODEL + ".onnx")
    english.write_bytes(b"existing English")
    calls = []

    def download(url, path):
        calls.append((url, path))
        path.write_bytes(b"downloaded Hindi")

    monkeypatch.setattr(voice_module, "_download_file", download)
    model = "hi_IN-rohan-medium"
    assert voice_module.ensure_voice_pack(model) == tmp_path / (model + ".onnx")
    assert len(calls) == 2
    assert all("/hi/hi_IN/rohan/medium/" in url for url, _path in calls)
    assert english.read_bytes() == b"existing English"
    calls.clear()
    voice_module.ensure_voice_pack(model)
    assert calls == []


# ------------------------------------------------------------
# SPEECH_LANGUAGE="hi": the Hindi pack speaks everything (brief §7.2)
# ------------------------------------------------------------

def test_hindi_mode_uses_the_hindi_pack_for_every_sentence(bilingual_pack, monkeypatch):
    monkeypatch.setattr(config, "SPEECH_LANGUAGE", "hi")
    voice = voice_module.Voice()                       # no language: follows the mode
    assert voice.ok
    # A sentence with only Latin names would otherwise go to the English pack.
    assert voice._piper_for_text("Ollama") is bilingual_pack.hindi
    assert voice._piper_for_text("नोटपैड खोल रही हूँ।") is bilingual_pack.hindi
    assert config.VOICE_MODEL not in bilingual_pack.loads   # English pack never loaded


def test_auto_mode_still_switches_packs_by_sentence(bilingual_pack):
    voice = bilingual_pack.build()
    assert voice._piper_for_text("Opening Notepad.") is bilingual_pack.english
    assert voice._piper_for_text("नमस्ते") is bilingual_pack.hindi


def test_explicit_english_voice_is_not_forced_in_hindi_mode(bilingual_pack, monkeypatch):
    monkeypatch.setattr(config, "SPEECH_LANGUAGE", "hi")
    voice = bilingual_pack.build("en")
    assert voice._piper_for_text("Hello there.") is bilingual_pack.english


def test_a_missing_hindi_model_names_the_setup_command(bilingual_pack, monkeypatch, capsys):
    monkeypatch.setattr(config, "SPEECH_LANGUAGE", "hi")

    def missing(model=None):
        raise IOError("no network, no pack")

    monkeypatch.setattr(voice_module, "ensure_voice_pack", missing)
    voice = voice_module.Voice()
    out = capsys.readouterr().out
    assert voice.ok is False
    assert "python -m lyra.setup_voice --language hi" in out
    assert "Text replies are still available" in out
