"""
============================================================
 LYRA VOICE
============================================================
 Piper text-to-speech with streaming playback.

 Speed tricks:
 - the voice pack auto-downloads on first run
 - sentences are synthesized in a background producer
   thread while the previous one is playing (gapless
   OutputStream, no play/stop gaps)

 Barge-in support:
 - every spoken word is remembered for a short window, so the
   microphone can tell the user's voice from LYRA's own words
   coming back through the speakers
============================================================
"""

import collections
import logging
import os
import queue
import threading
import time

import numpy as np
import requests

from . import config
from .utils import clean_for_voice, normalize, speech_language, split_sentences
from .voice_catalog import parse_voice_model

log = logging.getLogger(__name__)

try:
    import sounddevice as sd
    _SD_OK = True
except Exception:
    _SD_OK = False


# ------------------------------------------------------------
# VOICE PACK AUTO-DOWNLOAD
# ------------------------------------------------------------

def _voice_urls(model=None):
    """HuggingFace URLs, using the voice's language (not hard-coded /en)."""
    model = model or config.VOICE_MODEL
    language, family, name, quality = parse_voice_model(model)
    base = f"{config.VOICE_REPO}/{language}/{family}/{name}/{quality}/{model}"
    return base + ".onnx", base + ".onnx.json"


def _download_file(url, path):
    """Download atomically: temp file first, size check, then rename.

    An interrupted download leaves only the .part file behind, never a
    corrupt voice model that would fail to load on the next start.
    """

    temp_path = path.with_name(path.name + ".part")

    if temp_path.exists():
        temp_path.unlink()

    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()

        total = int(response.headers.get("content-length", 0))
        done = 0

        with open(temp_path, "wb") as f:

            for chunk in response.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
                done += len(chunk)

                if total:
                    percent = done * 100 // total
                    print(f"\r  {percent}%  ({done // (1024 * 1024)} MB)"
                          f"{' ' * 8}", end="", flush=True)

    print(" done.")

    size = temp_path.stat().st_size

    if size == 0:
        temp_path.unlink(missing_ok=True)
        raise IOError(f"Downloaded file is empty: {url}")

    if total and size != total:
        temp_path.unlink(missing_ok=True)
        raise IOError(
            f"Download incomplete ({size} of {total} bytes): {url}"
        )

    os.replace(temp_path, path)


def ensure_voice_pack(model=None):
    """Download an English or Hindi pack if missing; return its model path."""
    model = model or config.VOICE_MODEL
    model_url, json_url = _voice_urls(model)  # validate before constructing local paths
    model_path = config.VOICE_DIR / (model + ".onnx")
    json_path = config.VOICE_DIR / (model + ".onnx.json")

    if model_path.exists() and json_path.exists():
        return model_path

    config.VOICE_DIR.mkdir(parents=True, exist_ok=True)

    for url, path in [(json_url, json_path), (model_url, model_path)]:

        if path.exists():
            continue

        print(f"Downloading voice pack: {path.name} ...")
        _download_file(url, path)

    return model_path


# ------------------------------------------------------------
# VOICE
# ------------------------------------------------------------

class Voice:

    def __init__(self, language="en"):

        if language not in {"en", "hi"}:
            raise ValueError("Voice language must be en or hi")
        self._models = {"en": config.VOICE_MODEL, "hi": config.HINDI_VOICE_MODEL}
        self._primary_model = self._models[language]
        self._voices = {}
        self._failed_models = set()
        self._voice_load_lock = threading.Lock()
        self.ok = False
        self.sample_rate = 22050
        self._play_lock = threading.RLock()
        self._active_stream = None
        self._speaking_event = threading.Event()
        self._stop_event = threading.Event()
        # Barge-in: what she has just said, and the flag the barge-in
        # watcher sets while it is reading the microphone.
        self._spoken_words = collections.deque()
        self._spoken_lock = threading.Lock()
        self._capture_event = threading.Event()

        if not _SD_OK:
            print("sounddevice not available — running silent.")
            return

        try:
            from piper import PiperVoice

            model_path = ensure_voice_pack() if language == "en" else ensure_voice_pack(self._primary_model)

            print(f"Loading Lyra's voice ({self._primary_model})...")

            self.piper = PiperVoice.load(str(model_path))
            self._voices[self._primary_model] = self.piper

            # Not every Piper voice is 22.05 kHz. Asking the loaded pack for
            # its rate keeps a 16 kHz voice from being played back too fast.
            self.sample_rate = int(
                getattr(getattr(self.piper, "config", None), "sample_rate", 0)
                or self.sample_rate
            )

            self.ok = True

            print("Lyra's voice loaded.")

        except Exception:
            log.exception("Piper voice load failed")
            print("Lyra will run without speech.")

    # --------------------------------------------------------
    # SYNTHESIZE
    # --------------------------------------------------------

    @staticmethod
    def _synthesis_config():
        """VOICE_SPEED as a Piper SynthesisConfig, or None if unavailable.

        length_scale is the inverse of speed: 1.15x speed means the
        synthesizer stretches each sound to 1/1.15 of its length.
        """

        speed = float(getattr(config, "VOICE_SPEED", 1.0) or 1.0)

        try:
            try:
                from piper import SynthesisConfig
            except ImportError:
                from piper.synthesize import SynthesisConfig
        except Exception:
            return None

        try:
            return SynthesisConfig(length_scale=1.0 / speed)
        except Exception:
            return None

    def _piper_for_text(self, text):
        """Lazy-load each language once; never send Hindi to an English pack."""
        language = speech_language(text)
        model = self._models[language]
        if model == self._primary_model:
            return self.piper
        with self._voice_load_lock:
            if model in self._failed_models:
                raise RuntimeError(f"Voice {model} is unavailable; run python -m lyra.setup_voice --language {language}")
            if model not in self._voices:
                try:
                    from piper import PiperVoice
                    path = ensure_voice_pack(model)
                    print(f"Loading Lyra's {language} voice ({model})...")
                    self._voices[model] = PiperVoice.load(str(path))
                except Exception as error:
                    self._failed_models.add(model)
                    raise RuntimeError(
                        f"Could not load {model}. Run python -m lyra.setup_voice "
                        f"--language {language}, then restart LYRA. Text replies are still available."
                    ) from error
            return self._voices[model]

    def _piper_chunks(self, text):
        """Language-appropriate synthesis, VOICE_SPEED and old-API fallback."""

        piper = self._piper_for_text(text)
        synth_config = self._synthesis_config()

        if synth_config is not None:
            try:
                return piper.synthesize(text, config=synth_config)
            except TypeError:
                log.debug("Piper does not accept a config object; using kwargs")

        try:
            return piper.synthesize(
                text, length_scale=1.0 / float(getattr(config, "VOICE_SPEED", 1.0) or 1.0)
            )
        except TypeError:
            return piper.synthesize(text)

    def _synthesize(self, text):
        """
        text -> (sample_rate, int16 PCM bytes).

        The rate is the one the synthesized audio is really in, which is
        the only safe thing to open the output stream with. Returns
        (0, b"") for text that cleans away to nothing.
        """

        text = clean_for_voice(text)

        if not text:
            return 0, b""

        chunks = []
        rate = 0

        for chunk in self._piper_chunks(text):
            sample_rate = int(getattr(chunk, "sample_rate", 0) or 0)
            if sample_rate <= 0:
                raise ValueError(f"Piper returned invalid sample rate: {sample_rate}")
            if rate and sample_rate != rate:
                raise ValueError(f"Piper changed sample rate mid-utterance: {rate} -> {sample_rate}")
            rate = sample_rate

            pcm = getattr(chunk, "audio_int16_bytes", None)
            if pcm is not None:
                if not isinstance(pcm, (bytes, bytearray, memoryview)):
                    raise TypeError(
                        "Piper audio_int16_bytes must be bytes-like; received "
                        f"{type(pcm).__name__}"
                    )
                raw = bytes(pcm)
            else:
                pcm = getattr(chunk, "audio", None)
                audio = self._pcm_to_int16(pcm, context="Piper audio chunk")
                raw = audio.tobytes()

            if len(raw) == 0 or len(raw) % 2:
                raise ValueError(f"Piper returned invalid 16-bit PCM buffer ({len(raw)} bytes)")
            log.debug(
                "Piper chunk type=%s sample_rate=%d sample_width=2 pcm_bytes=%d",
                type(chunk).__name__, sample_rate, len(raw),
            )
            chunks.append(raw)

        if not chunks:
            raise ValueError("Piper produced no audio for non-empty speech text")
        return rate, b"".join(chunks)

    # --------------------------------------------------------
    # PLAY HELPERS
    # --------------------------------------------------------

    @staticmethod
    def _pcm_to_int16(pcm, context="audio"):
        """Validate raw 16-bit PCM and expose it as a sounddevice array."""

        if isinstance(pcm, np.ndarray):
            if pcm.dtype != np.int16:
                raise TypeError(
                    f"{context} must be int16; received NumPy dtype {pcm.dtype}"
                )
            if not pcm.flags.c_contiguous:
                pcm = np.ascontiguousarray(pcm)
            return pcm

        if not isinstance(pcm, (bytes, bytearray, memoryview)):
            raise TypeError(
                f"{context} must be PCM bytes or a NumPy int16 array; "
                f"received {type(pcm).__name__}"
            )

        pcm_bytes = memoryview(pcm)
        if pcm_bytes.nbytes % np.dtype(np.int16).itemsize:
            raise ValueError(
                f"{context} has {pcm_bytes.nbytes} bytes; 16-bit PCM must "
                "have an even byte count"
            )

        # Piper audio_int16_bytes contains signed 16-bit PCM. frombuffer
        # views those samples without copying the full synthesized buffer.
        audio = np.frombuffer(pcm_bytes, dtype=np.int16)
        if audio.dtype != np.int16:  # Defensive contract check for playback.
            raise TypeError(f"{context} conversion produced {audio.dtype}, expected int16")
        return audio

    def _silence(self, sample_rate=None):
        """A short PCM silence for a natural pause between sentences."""

        rate = sample_rate or self.sample_rate

        return b"\x00\x00" * int(rate * config.VOICE_SENTENCE_SILENCE)

    @property
    def is_speaking(self):
        return self._speaking_event.is_set()

    @property
    def capturing(self):
        """True while the barge-in watcher is reading the microphone."""
        return self._capture_event.is_set()

    def start_capture(self):
        self._capture_event.set()

    def end_capture(self):
        self._capture_event.clear()

    # --------------------------------------------------------
    # SPEAKER ECHO
    # --------------------------------------------------------
    # With the speakers on, the microphone hears LYRA as well as the
    # user. Every word she speaks is remembered for a short window;
    # a phrase that is mostly those words is her echo, not a command.

    def remember_spoken(self, sentence):
        """Record the words of one spoken sentence for echo detection."""

        words = normalize(sentence or "").split()

        if not words:
            return

        now = time.monotonic()
        cutoff = now - config.INTERRUPT_ECHO_WINDOW_SECONDS

        with self._spoken_lock:
            for word in words:
                self._spoken_words.append((word, now))
            while self._spoken_words and self._spoken_words[0][1] < cutoff:
                self._spoken_words.popleft()

    def looks_like_echo(self, heard, min_overlap=0.5):
        """True when enough of the heard words are ones she just said."""

        words = normalize(heard or "").split()

        if not words:
            return False

        cutoff = time.monotonic() - config.INTERRUPT_ECHO_WINDOW_SECONDS

        with self._spoken_lock:
            recent = {word for word, stamp in self._spoken_words if stamp >= cutoff}

        if not recent:
            return False

        overlap = sum(1 for word in words if word in recent)

        return overlap / len(words) >= min_overlap

    def beep(self):
        """Play the attention tone without overlapping speech playback."""
        with self._play_lock:
            self._speaking_event.set()
            try:
                return self._beep_locked()
            finally:
                self._speaking_event.clear()

    def _beep_locked(self):
        if not self.ok:
            return

        sr = self.sample_rate
        t1 = np.linspace(0, 0.07, int(sr * 0.07), endpoint=False)
        t2 = np.linspace(0, 0.07, int(sr * 0.07), endpoint=False)

        tone = np.concatenate([
            np.sin(2 * np.pi * 880 * t1),
            np.sin(2 * np.pi * 1245 * t2),
        ])

        pcm = (tone * 32767 * 0.22).astype(np.int16)

        try:
            sd.play(pcm, samplerate=sr, device=config.OUTPUT_DEVICE)
            sd.wait()
        except Exception:
            log.exception("Attention beep playback failed")

    # --------------------------------------------------------
    # SPEAK
    # --------------------------------------------------------

    def speak(self, text):
        """Speak a fixed text (splits into sentences internally)."""

        if not text:
            return

        return self.speak_stream(iter(split_sentences(text)))

    def speak_stream(self, sentences):
        """Serialize speech, switching local voice packs by sentence language."""
        with self._play_lock:
            self._speaking_event.set()
            try:
                return self._speak_stream_locked(sentences)
            finally:
                self._speaking_event.clear()

    def _speak_stream_locked(self, sentences):
        """Synthesize ahead while playing through one output stream."""
        # A canceled producer may still be finishing inference/downloads.
        # Give each reply its own event so the next reply cannot revive it.
        stop_event = threading.Event()
        self._stop_event = stop_event

        if not self.ok:
            # Silent mode. Printing is the Session's job (it always prints
            # every reply as "Lyra: ..."), so here the sentences are only
            # drained — printing twice would duplicate every line.
            for _sentence in sentences:
                pass
            return False

        # Replies are bounded by LYRA's output token limit; an unbounded queue
        # avoids a producer deadlock if device playback aborts mid-reply.
        synth_queue = queue.Queue()

        # ----------------------------------------------------
        # PRODUCER: synthesize ahead into the queue
        # ----------------------------------------------------

        def producer():
            try:
                for sentence in sentences:
                    if stop_event.is_set():
                        break
                    sentence = (sentence or "").strip()
                    if not sentence:
                        continue
                    try:
                        rate, pcm = self._synthesize(sentence)
                        if pcm and not stop_event.is_set():
                            self.remember_spoken(sentence)
                            synth_queue.put((rate, pcm))
                    except Exception:
                        # A missing Hindi pack must be visible, not silent,
                        # and must not prevent later English sentences.
                        log.exception("Speech synthesis failed for language=%s", speech_language(sentence))
            except Exception:
                log.exception("Speech sentence stream failed")
            finally:
                synth_queue.put(None)

        thread = threading.Thread(target=producer, daemon=True)
        thread.start()

        # ----------------------------------------------------
        # CONSUMER: gapless playback through one stream
        # ----------------------------------------------------
        # The stream is opened on the first chunk, at that chunk's real
        # rate: the producer is already running, so opening it up front
        # could pick a rate before the voice pack has had its say.

        stream = None
        rate = self.sample_rate
        played_anything = False

        try:

            while not stop_event.is_set():
                try:
                    item = synth_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                if item is None or stop_event.is_set():
                    break

                chunk_rate, pcm = item
                pcm_array = self._pcm_to_int16(pcm, context="Piper audio")
                chunk_rate = int(chunk_rate or rate)
                if chunk_rate <= 0:
                    raise ValueError(f"Invalid Piper sample rate: {chunk_rate}")

                # Different packs may use 16 kHz and 22.05 kHz in the same
                # reply. Close/reopen instead of distorting pitch or failing.
                if stream is not None and chunk_rate != rate:
                    self._close_stream(stream)
                    stream = None

                if stream is None:
                    rate = chunk_rate or rate
                    if rate <= 0:
                        raise ValueError(f"Invalid playback sample rate: {rate}")
                    if hasattr(sd, "check_output_settings"):
                        sd.check_output_settings(
                            device=config.OUTPUT_DEVICE, channels=1,
                            dtype="int16", samplerate=rate,
                        )
                    log.debug(
                        "Opening output device=%r sample_rate=%d channels=1 dtype=int16",
                        config.OUTPUT_DEVICE, rate,
                    )
                    stream = sd.OutputStream(
                        samplerate=rate,
                        channels=1,
                        dtype="int16",
                        device=config.OUTPUT_DEVICE,
                    )
                    self._active_stream = stream
                    stream.start()

                if stop_event.is_set():
                    break

                # sounddevice expects typed int16 arrays, not raw bytes.
                stream.write(pcm_array)
                played_anything = True

                if config.VOICE_SENTENCE_SILENCE > 0:
                    silence = self._silence(rate)
                    stream.write(self._pcm_to_int16(silence, context="sentence silence"))

        except Exception:
            log.exception("Piper/sounddevice playback failed")

        finally:
            stop_event.set()
            if stream is not None:
                self._close_stream(stream)

        return played_anything

    def _close_stream(self, stream):
        try:
            stream.stop()
        except Exception:
            pass
        try:
            stream.close()
        except Exception:
            log.exception("Voice stream close failed")
        finally:
            self._active_stream = None

    def stop(self):
        """Abort active stream or simple playback without waiting on speak()."""
        self._stop_event.set()
        stream = self._active_stream
        if stream is not None:
            abort = getattr(stream, "abort", None)
            try:
                (abort or stream.stop)()
            except Exception as error:
                print(f"Voice stop error: {error}")
        if _SD_OK:
            try:
                sd.stop()
            except Exception as error:
                print(f"Audio device stop error: {error}")
