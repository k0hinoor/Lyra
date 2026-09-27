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
============================================================
"""

import queue
import threading

import numpy as np
import requests

from . import config
from .utils import clean_for_voice, split_sentences

try:
    import sounddevice as sd
    _SD_OK = True
except Exception:
    _SD_OK = False


# ------------------------------------------------------------
# VOICE PACK AUTO-DOWNLOAD
# ------------------------------------------------------------

def _voice_urls():
    """HuggingFace URLs for the .onnx model and its .json config."""

    model = config.VOICE_MODEL                      # e.g. en_US-amy-medium
    family, rest = model.split("-", 1)              # en_US | amy-medium
    name, quality = rest.rsplit("-", 1)             # amy    | medium

    base = f"{config.VOICE_REPO}/en/{family}/{name}/{quality}/{model}"

    return base + ".onnx", base + ".onnx.json"


def ensure_voice_pack():
    """Download the voice pack if missing. Returns the model path."""

    model_path = config.VOICE_DIR / (config.VOICE_MODEL + ".onnx")
    json_path = config.VOICE_DIR / (config.VOICE_MODEL + ".onnx.json")

    if model_path.exists() and json_path.exists():
        return model_path

    config.VOICE_DIR.mkdir(parents=True, exist_ok=True)

    for url, path in [(_voice_urls()[1], json_path), (_voice_urls()[0], model_path)]:

        if path.exists():
            continue

        print(f"Downloading voice pack: {path.name} ...")

        with requests.get(url, stream=True, timeout=60) as response:
            response.raise_for_status()

            total = int(response.headers.get("content-length", 0))
            done = 0

            with open(path, "wb") as f:

                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
                    done += len(chunk)

                    if total:
                        percent = done * 100 // total
                        print(f"\r  {percent}%  ({done // (1024 * 1024)} MB)"
                              f"{' ' * 8}", end="", flush=True)

        print(" done.")

    return model_path


# ------------------------------------------------------------
# VOICE
# ------------------------------------------------------------

class Voice:

    def __init__(self):

        self.ok = False
        self.sample_rate = 22050

        if not _SD_OK:
            print("sounddevice not available — running silent.")
            return

        try:
            from piper import PiperVoice

            model_path = ensure_voice_pack()

            print("Loading Lyra's voice...")

            self.piper = PiperVoice.load(str(model_path))
            self.ok = True

            print("Lyra's voice loaded.")

        except Exception as e:
            print(f"Voice load error: {e}")
            print("Lyra will run without speech.")

    # --------------------------------------------------------
    # SYNTHESIZE
    # --------------------------------------------------------

    def _synthesize(self, text):
        """text -> int16 PCM bytes at self.sample_rate ('' if empty)."""

        text = clean_for_voice(text)

        if not text:
            return b""

        chunks = []

        for chunk in self.piper.synthesize(text):

            pcm = getattr(chunk, "audio_int16_bytes", None)

            if pcm is None:
                pcm = getattr(chunk, "audio", b"")

            rate = getattr(chunk, "sample_rate", None)

            if rate:
                self.sample_rate = rate

            chunks.append(pcm)

        return b"".join(chunks)

    # --------------------------------------------------------
    # PLAY HELPERS
    # --------------------------------------------------------

    def _silence(self):
        """A short PCM silence for a natural pause between sentences."""

        return b"\x00\x00" * int(self.sample_rate * config.VOICE_SENTENCE_SILENCE)

    def beep(self):
        """Short two-tone attention beep."""

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
        except Exception as e:
            print(f"Beep error: {e}")

    # --------------------------------------------------------
    # SPEAK
    # --------------------------------------------------------

    def speak(self, text):
        """Speak a fixed text (splits into sentences internally)."""

        if not text:
            return

        self.speak_stream(iter(split_sentences(text)))

    def speak_stream(self, sentences):
        """
        Consume an iterator/generator of sentence strings and
        speak them pipelined: while one sentence is playing,
        the next is already being synthesized.
        """

        if not self.ok:
            # silent mode — just print
            for sentence in sentences:
                if sentence and sentence.strip():
                    print("Lyra:", sentence)
            return

        synth_queue = queue.Queue(maxsize=8)

        # ----------------------------------------------------
        # PRODUCER: synthesize ahead into the queue
        # ----------------------------------------------------

        def producer():

            try:
                for sentence in sentences:

                    sentence = (sentence or "").strip()

                    if not sentence:
                        continue

                    pcm = self._synthesize(sentence)

                    if pcm:
                        synth_queue.put(pcm)

            except Exception as e:
                print(f"Voice synth error: {e}")

            finally:
                synth_queue.put(None)

        thread = threading.Thread(target=producer, daemon=True)
        thread.start()

        # ----------------------------------------------------
        # CONSUMER: gapless playback through one stream
        # ----------------------------------------------------

        stream = None

        try:
            stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                device=config.OUTPUT_DEVICE,
            )
            stream.start()

            while True:

                pcm = synth_queue.get()

                if pcm is None:
                    break

                stream.write(pcm)

                if config.VOICE_SENTENCE_SILENCE > 0:
                    stream.write(self._silence())

            stream.stop()

        except Exception as e:
            print(f"Voice playback error: {e}")

        finally:
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass

    def stop(self):
        """Cut off current playback immediately."""

        if _SD_OK:
            try:
                sd.stop()
            except Exception:
                pass
