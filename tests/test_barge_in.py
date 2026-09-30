"""
============================================================
 TESTS — barge-in  (interrupt LYRA by talking over her)
============================================================
 The microphone, the voice and the transcriber are all faked:
 a scripted int16 microphone stream, a voice that counts how
 many chunks it "speaks" for, and a fake `speech_recognition`
 module installed in sys.modules. No sound card, no microphone
 and no network is ever touched.
============================================================
"""

import queue
import sys
import threading
from types import SimpleNamespace

import numpy as np
import pytest

import main
from lyra import config
from lyra.utils import STOP_SPEECH_PHRASES, normalize


# Every barge-in test needs these two: speech_recognition is imported
# lazily inside the polling code, so the fake must be importable.
SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2
CHUNK = 64

CHUNK_SECONDS = CHUNK / SAMPLE_RATE
VOICED_NEEDED = max(1, int(config.INTERRUPT_MIN_VOICE_SECONDS / CHUNK_SECONDS))
SILENCE_NEEDED = max(1, int(config.INTERRUPT_SILENCE_SECONDS / CHUNK_SECONDS))

LOUD = 8000            # well above the thresholds used below
QUIET = 0


# ------------------------------------------------------------
# FAKES
# ------------------------------------------------------------

class FakeAudioData:
    """Stands in for speech_recognition.AudioData."""

    def __init__(self, frame_data, sample_rate, sample_width):
        self.frame_data = frame_data
        self.sample_rate = sample_rate
        self.sample_width = sample_width


def _chunk(amplitude, frames=CHUNK):
    return np.full(frames, amplitude, dtype=np.int16).tobytes()


def script(pattern):
    """'lllqqq' -> that many loud and quiet microphone chunks."""
    return [_chunk(LOUD if step == "l" else QUIET) for step in pattern]


class FakeStream:
    """Hands out scripted chunks; silence once the script runs out."""

    def __init__(self, chunks, chunk=CHUNK):
        self.chunks = list(chunks)
        self.chunk = chunk
        self.reads = 0

    def read(self, size):
        # the real MicrophoneStream.read() takes the frame count only
        assert size == self.chunk
        self.reads += 1
        return self.chunks.pop(0) if self.chunks else _chunk(QUIET, self.chunk)


class FakeMic:
    """Just enough of speech_recognition.Microphone to be polled."""

    def __init__(self, chunks, sample_rate=SAMPLE_RATE, sample_width=SAMPLE_WIDTH,
                 chunk=CHUNK):
        self.stream = FakeStream(chunks, chunk)
        self.SAMPLE_RATE = sample_rate
        self.SAMPLE_WIDTH = sample_width
        self.CHUNK = chunk


class FakeVoice:
    """A Voice that speaks for a fixed number of polls, then finishes."""

    def __init__(self, speak_reads=None, echo_words=()):
        self._speak_reads = speak_reads          # None = still talking
        self.stop_calls = 0
        self.capturing_now = False
        self.capture_calls = 0
        self.echo_words = set(echo_words)

    @property
    def is_speaking(self):
        if self._speak_reads is None:
            return True
        if self._speak_reads <= 0:
            return False
        self._speak_reads -= 1
        return True

    @property
    def capturing(self):
        return self.capturing_now

    def stop(self):
        self.stop_calls += 1

    def start_capture(self):
        self.capturing_now = True
        self.capture_calls += 1

    def end_capture(self):
        self.capturing_now = False

    def looks_like_echo(self, heard, min_overlap=0.5):
        words = set(normalize(heard or "").split())
        if not words:
            return False
        return len(words & self.echo_words) / len(words) >= min_overlap


class FakeEar:
    """Returns one scripted transcript, whatever audio it is given."""

    def __init__(self, heard="open notepad"):
        self.heard = heard
        self.transcribed = 0

    def transcribe_audio(self, audio):
        self.transcribed += 1
        return self.heard


def fake_recognizer(energy_threshold=200.0):
    return SimpleNamespace(energy_threshold=energy_threshold)


# ------------------------------------------------------------
# FIXTURES
# ------------------------------------------------------------

@pytest.fixture
def fake_sr(monkeypatch):
    """Install a fake speech_recognition module (only AudioData is used)."""
    module = SimpleNamespace(AudioData=FakeAudioData)
    monkeypatch.setitem(sys.modules, "speech_recognition", module)
    return module


@pytest.fixture
def out_queue():
    return queue.Queue()


# ------------------------------------------------------------
# LEVEL OF ONE MICROPHONE CHUNK
# ------------------------------------------------------------

def test_silence_has_no_level():
    assert main._chunk_rms(_chunk(QUIET)) == 0.0


def test_a_loud_chunk_measures_close_to_its_amplitude():
    assert main._chunk_rms(_chunk(10000)) == pytest.approx(10000.0, rel=1e-3)


def test_a_quiet_but_real_room_tone_is_far_below_speech():
    assert main._chunk_rms(_chunk(200)) < main._chunk_rms(_chunk(4000))


# ------------------------------------------------------------
# POLLING WHILE SHE SPEAKS
# ------------------------------------------------------------

def test_a_reply_she_finishes_alone_is_never_interrupted(fake_sr):
    voice = FakeVoice(speak_reads=5)
    mic = FakeMic(script("l" * 5))

    assert main._poll_for_interrupt(mic, voice, 500) is None
    assert voice.stop_calls == 0
    assert mic.stream.reads == 5


def test_a_short_blip_is_ignored(fake_sr):
    # a cough, a keyboard, a door: loud, but far too brief
    voice = FakeVoice(speak_reads=VOICED_NEEDED + 5)
    mic = FakeMic(script("l" * 3 + "q" * (VOICED_NEEDED + 2)))

    assert main._poll_for_interrupt(mic, voice, 500) is None
    assert voice.stop_calls == 0


def test_sustained_voice_stops_her_and_captures_the_phrase(fake_sr):
    voice = FakeVoice()                              # never stops by itself
    mic = FakeMic(script("l" * (VOICED_NEEDED + SILENCE_NEEDED + 20)))

    audio = main._poll_for_interrupt(mic, voice, 500)

    assert voice.stop_calls == 1, "playback must stop at once"
    assert isinstance(audio, FakeAudioData)
    assert audio.sample_rate == SAMPLE_RATE
    assert audio.sample_width == SAMPLE_WIDTH
    # the barge-in itself plus the tail up to the pause, no more
    assert len(audio.frame_data) == (
        VOICED_NEEDED + SILENCE_NEEDED
    ) * CHUNK * SAMPLE_WIDTH


def test_the_capture_stops_at_the_phrase_limit(fake_sr, monkeypatch):
    monkeypatch.setattr(config, "INTERRUPT_PHRASE_LIMIT", 0)
    voice = FakeVoice(speak_reads=VOICED_NEEDED)
    mic = FakeMic(script("l" * 500))

    audio = main._poll_for_interrupt(mic, voice, 500)

    assert voice.stop_calls == 1
    assert len(audio.frame_data) == VOICED_NEEDED * CHUNK * SAMPLE_WIDTH


def test_the_captured_audio_is_labelled_with_the_microphone_format(fake_sr):
    # Whisper must not be handed audio that claims to be a rate it is not:
    # the format comes from the live microphone, never from a guess.
    voice = FakeVoice(speak_reads=200)
    mic = FakeMic([_chunk(LOUD, 1024)] * 60, sample_rate=44100,
                  sample_width=2, chunk=1024)

    audio = main._poll_for_interrupt(mic, voice, 500)

    assert voice.stop_calls == 1
    assert audio.sample_rate == 44100
    assert audio.sample_width == 2
    assert len(audio.frame_data) % (1024 * 2) == 0
    assert len(audio.frame_data) > 0


def test_the_microphone_is_opened_at_whispers_rate():
    assert main.MIC_SAMPLE_RATE == 16000


def test_speech_after_a_pause_keeps_the_phrase_open(fake_sr):
    # the pause that ends the phrase has to be a full half second of
    # silence, not ten chunks in the middle of a sentence
    voice = FakeVoice(speak_reads=VOICED_NEEDED)
    mic = FakeMic(script(
        "l" * VOICED_NEEDED + "q" * 10 + "l" * 10
    ))

    audio = main._poll_for_interrupt(mic, voice, 500)

    assert voice.stop_calls == 1
    assert mic.stream.reads == VOICED_NEEDED + 10 + 10 + SILENCE_NEEDED
    assert len(audio.frame_data) == (
        VOICED_NEEDED + SILENCE_NEEDED
    ) * CHUNK * SAMPLE_WIDTH


# ------------------------------------------------------------
# ONE WATCH CYCLE
# ------------------------------------------------------------

def test_a_real_command_is_queued(fake_sr, out_queue):
    voice = FakeVoice()
    mic = FakeMic(script("l" * (VOICED_NEEDED + SILENCE_NEEDED + 5)))
    ear = FakeEar("open notepad")

    main._watch_once(voice, mic, fake_recognizer(), ear, out_queue)

    assert out_queue.get_nowait() == "open notepad"
    assert voice.stop_calls == 1
    assert voice.capturing_now is False, "the capture flag must be released"


def test_her_own_voice_from_the_speakers_is_dropped(fake_sr, out_queue):
    voice = FakeVoice(echo_words={"opening", "notepad", "for", "you"})
    mic = FakeMic(script("l" * (VOICED_NEEDED + SILENCE_NEEDED + 5)))
    ear = FakeEar("Opening Notepad for you.")

    main._watch_once(voice, mic, fake_recognizer(), ear, out_queue)

    assert out_queue.empty()


def test_filler_noise_is_dropped(fake_sr, out_queue):
    for heard in ("okay", "hmm", "um"):
        voice = FakeVoice()
        mic = FakeMic(script("l" * (VOICED_NEEDED + SILENCE_NEEDED + 5)))
        main._watch_once(voice, mic, fake_recognizer(), FakeEar(heard), out_queue)

    assert out_queue.empty()


def test_nothing_recognised_is_dropped(fake_sr, out_queue):
    voice = FakeVoice()
    mic = FakeMic(script("l" * (VOICED_NEEDED + SILENCE_NEEDED + 5)))

    main._watch_once(voice, mic, fake_recognizer(), FakeEar(""), out_queue)

    assert out_queue.empty()


def test_a_reply_that_finished_alone_is_not_transcribed(fake_sr, out_queue):
    voice = FakeVoice(speak_reads=4)
    mic = FakeMic(script("q" * 20))
    ear = FakeEar("open notepad")

    main._watch_once(voice, mic, fake_recognizer(), ear, out_queue)

    assert out_queue.empty()
    assert ear.transcribed == 0


@pytest.mark.parametrize("phrase", sorted(STOP_SPEECH_PHRASES))
def test_a_stop_phrase_is_kept_even_when_it_matches_her_own_words(
        fake_sr, out_queue, phrase):
    # "stop"/"be quiet" is exactly what she may have just said, but the
    # user must always be able to shut her up by talking over her.
    voice = FakeVoice(echo_words=set(normalize(phrase).split()))
    mic = FakeMic(script("l" * (VOICED_NEEDED + SILENCE_NEEDED + 5)))

    main._watch_once(voice, mic, fake_recognizer(), FakeEar(phrase), out_queue)

    assert out_queue.get_nowait() == phrase


def test_the_capture_flag_stays_set_while_the_phrase_is_transcribed(
        fake_sr, out_queue):
    # While it is set, the main loop must not start its own listen(): both
    # would read the same stream and the phrase would be cut in half.
    seen = []
    voice = FakeVoice(speak_reads=VOICED_NEEDED)
    mic = FakeMic(script("l" * (VOICED_NEEDED + 10)))

    class SlowEar:
        def transcribe_audio(self, audio):
            seen.append(voice.capturing)
            return "open notepad"

    main._watch_once(voice, mic, fake_recognizer(), SlowEar(), out_queue)

    assert seen == [True]
    assert voice.capturing_now is False


def test_the_capture_flag_is_released_even_when_capture_fails(
        fake_sr, out_queue, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("microphone stream closed")

    monkeypatch.setattr(main, "_poll_for_interrupt", boom)
    voice = FakeVoice()

    with pytest.raises(RuntimeError):
        main._watch_once(voice, FakeMic([]), fake_recognizer(),
                         FakeEar(), out_queue)

    assert voice.capture_calls == 1
    assert voice.capturing_now is False


# ------------------------------------------------------------
# THE INTERRUPT THRESHOLD
# ------------------------------------------------------------

def test_the_barge_in_threshold_is_above_the_room_noise(fake_sr, out_queue):
    # A calibrated floor of 300 x2.0 = 600 stays above this 500 tone.
    voice = FakeVoice(speak_reads=60)
    mic = FakeMic([_chunk(500)] * 60)

    main._watch_once(voice, mic, fake_recognizer(300.0), FakeEar(), out_queue)

    assert out_queue.empty()
    assert voice.stop_calls == 0


def test_a_higher_multiplier_needs_a_louder_barge_in(fake_sr, monkeypatch):
    # The same 1000-level tone interrupts with the default multiplier and
    # is ignored when the room is noisy enough to need a stricter one.
    monkeypatch.setattr(config, "INTERRUPT_ENERGY_MULTIPLIER", 1.0)
    voice = FakeVoice(speak_reads=60)
    mic = FakeMic([_chunk(1000)] * 60)
    main._watch_once(voice, mic, fake_recognizer(300.0), FakeEar(), queue.Queue())
    assert voice.stop_calls == 1

    monkeypatch.setattr(config, "INTERRUPT_ENERGY_MULTIPLIER", 10.0)
    quiet_voice = FakeVoice(speak_reads=60)
    quiet_mic = FakeMic([_chunk(1000)] * 60)
    main._watch_once(quiet_voice, quiet_mic, fake_recognizer(300.0),
                     FakeEar(), queue.Queue())
    assert quiet_voice.stop_calls == 0
    assert quiet_voice.capturing_now is False


# ------------------------------------------------------------
# THE WATCHER THREAD
# ------------------------------------------------------------

def test_the_watcher_only_listens_while_she_speaks(monkeypatch):
    calls = []
    slept = []
    stop = threading.Event()

    monkeypatch.setattr(main, "_watch_once", lambda *a: calls.append(1))

    def fake_sleep(seconds):
        slept.append(seconds)
        stop.set()

    monkeypatch.setattr(main.time, "sleep", fake_sleep)

    main._interrupt_watcher(FakeVoice(speak_reads=0), None, None, None,
                            queue.Queue(), stop)

    assert calls == []
    assert slept == [0.05]


def test_the_watcher_survives_a_failing_capture(monkeypatch):
    calls = []
    stop = threading.Event()

    def flaky(*args):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("stream gone")
        stop.set()

    monkeypatch.setattr(main, "_watch_once", flaky)
    monkeypatch.setattr(main.time, "sleep", lambda seconds: None)

    main._interrupt_watcher(FakeVoice(), None, None, None, queue.Queue(), stop)

    assert len(calls) == 2


def test_the_watcher_stops_when_asked(monkeypatch):
    stop = threading.Event()
    stop.set()

    monkeypatch.setattr(
        main, "_watch_once",
        lambda *a: pytest.fail("the watcher must not run after stop_event"),
    )

    main._interrupt_watcher(FakeVoice(), None, None, None, queue.Queue(), stop)


# ------------------------------------------------------------
# HANDLING THE INTERRUPTING PHRASE
# ------------------------------------------------------------

pytestmark = pytest.mark.usefixtures("pc")


@pytest.mark.parametrize("phrase", [
    "stop", "stop talking", "be quiet", "shut up", "silence", "hush",
    "hold on", "wait", "lyra stop", "lyra be quiet",
])
def test_a_stop_phrase_just_stops_the_speech(session, fake_brain, capfd, phrase):
    assert main._handle_interrupt(session, phrase, always_listening=True) is False

    out = capfd.readouterr().out
    assert "Okay." in out
    assert fake_brain.asked == [], "silence must not become a chat question"


@pytest.mark.parametrize("phrase, stops_lyra", [
    ("stop talking", True),
    ("quiet", True),
    ("lyra shut up", True),
    ("lyra wait", True),
    ("wait for the download", False),
    ("why is the sky blue", False),
])
def test_only_a_stop_phrase_halts_lyra(session, fake_brain, capfd,
                                       phrase, stops_lyra):
    main._handle_interrupt(session, phrase, always_listening=True)

    said_okay = "Lyra: Okay." in capfd.readouterr().out
    assert said_okay is stops_lyra
    assert bool(fake_brain.asked) is not stops_lyra, \
        "an ordinary sentence is a real command, not a halt"


def test_a_real_command_captured_over_her_is_carried_out(session, fake_brain, pc):
    assert main._handle_interrupt(session, "open notepad",
                                  always_listening=True) is False

    assert pc.started == ["notepad"]
    assert fake_brain.asked == []


def test_the_wake_word_is_stripped_from_an_interrupt(session, pc):
    main._handle_interrupt(session, "Hey Lyra, open notepad",
                           always_listening=False)

    assert pc.started == ["notepad"]


def test_a_bare_wake_word_over_her_does_nothing(session, fake_brain, pc, capfd):
    assert main._handle_interrupt(session, "hey lyra",
                                  always_listening=False) is False

    out = capfd.readouterr().out
    assert "Lyra:" not in out
    assert fake_brain.asked == []
    assert pc.started == []


def test_filler_over_her_stays_silent(session, fake_brain, capfd):
    assert main._handle_interrupt(session, "hmm", always_listening=True) is False

    assert "Lyra:" not in capfd.readouterr().out
    assert fake_brain.asked == []


def test_terminate_over_her_still_goes_offline(session, capfd):
    assert main._handle_interrupt(session, "terminate execution",
                                  always_listening=True) is True

    assert "Goodbye" in capfd.readouterr().out


def test_the_interrupting_phrase_is_printed_and_transcribed(session, pc, capfd):
    main._handle_interrupt(session, "open notepad", always_listening=True)

    assert "You: open notepad" in capfd.readouterr().out
    assert session.last_heard == "open notepad"


def test_stop_during_a_planner_task_cancels_it(session, capfd):
    session.task_active = True

    assert main._handle_interrupt(session, "stop", always_listening=True) is False

    assert session.task_executor.stop_requested
    assert "Stopping the active task safely." in capfd.readouterr().out


def test_a_confirmation_can_still_be_answered_over_her(session, capfd):
    from lyra.skills.base import Confirmation

    ran = []
    session.pending_confirmation = Confirmation(
        prompt="Are you sure?",
        action=lambda: ran.append("ran"),
        say_on_confirm="Doing it.",
    )

    main._handle_interrupt(session, "confirm", always_listening=True)

    assert ran == ["ran"]
    assert "Doing it." in capfd.readouterr().out


def test_a_filler_over_her_is_never_dropped_while_a_confirmation_waits(
        session, fake_brain):
    from lyra.skills.base import Confirmation

    session.pending_confirmation = Confirmation(
        prompt="Are you sure?",
        action=lambda: None,
        say_on_confirm="Doing it.",
    )

    main._handle_interrupt(session, "okay", always_listening=True)

    assert fake_brain.asked == ["okay"], \
        "the phrase reached the session instead of being discarded"
