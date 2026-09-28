"""
============================================================
 LYRA CONFIGURATION
============================================================
 Every knob of the assistant lives in this one file.
 Change values here — never touch the other code.
============================================================
"""

from pathlib import Path

# ------------------------------------------------------------
# PATHS
# ------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
VOICE_DIR = MODELS_DIR / "voice"

MEMORY_FILE = BASE_DIR / "memory.json"
SCREENSHOT_DIR = Path.home() / "Pictures" / "Lyra"

# ------------------------------------------------------------
# OWNER
# ------------------------------------------------------------

USER_NAME = "SRK"
DEFAULT_CITY = "Bhubaneswar"        # used when you ask just "weather"

# ------------------------------------------------------------
# BRAIN  (local LLM served by Ollama)
# ------------------------------------------------------------

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "phi4-mini:3.8b"

OLLAMA_KEEP_ALIVE = "30m"     # keep model in RAM between commands = no reload lag
OLLAMA_TIMEOUT = 120          # seconds
MAX_REPLY_TOKENS = 220        # caps rambling, keeps spoken answers quick
HISTORY_MESSAGES = 12         # short-term context lines sent to the brain

# ------------------------------------------------------------
# EARS  (faster-whisper speech-to-text)
# ------------------------------------------------------------

# "tiny.en" = fastest | "base.en" = balanced (default) | "small.en" = most accurate
WHISPER_MODEL = "base.en"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE = "int8"      # int8 = fast on CPU
WHISPER_BEAM = 1              # 1 = fastest, plenty accurate for voice commands

# ------------------------------------------------------------
# VOICE  (Piper text-to-speech)
# ------------------------------------------------------------

VOICE_MODEL = "en_US-amy-medium"    # female voice, natural and fast
# Other good options:  en_US-lessac-high, en_GB-jenny-high, en_US-hattie-medium

VOICE_REPO = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
VOICE_SENTENCE_SILENCE = 0.10       # small natural gap between streamed sentences (sec)

OUTPUT_DEVICE = None                # None = Windows default output.
                                    # Run `python main.py --devices` to list
                                    # yours, then set the index (e.g. 5).

# ------------------------------------------------------------
# LISTENING
# ------------------------------------------------------------

WAKE_MODE = "wake"            # "wake" = say "Hey Lyra" first | "always" = react to everything
WAKE_WORD = "lyra"

# How Whisper commonly mis-hears the name — all treated as the wake word.
WAKE_ALIASES = ["lyra", "laira", "lira", "liara", "lara", "laura", "yara", "lyrah", "lerae"]

WAKE_PREFIXES = ["hey", "ok", "okay", "hi", "hello", "yo", "hay"]

FOLLOW_UP_SECONDS = 12        # after a reply, Lyra stays awake this long —
                              # you can keep talking without repeating the wake word

SPEAK_BEEP = True             # short beep when Lyra wakes up / goes to sleep

PAUSE_THRESHOLD = 0.7         # silence that ends your sentence.
                              # (was 1.5 in the old brain — this alone saves ~0.8s per turn)
NON_SPEAKING_DURATION = 0.4
PHRASE_TIME_LIMIT = 15        # max seconds for one utterance
LISTEN_TIMEOUT = 8            # give up on silence after this

# ------------------------------------------------------------
# SAFETY  (shutdown / restart / sleep need confirmation)
# ------------------------------------------------------------

CONFIRM_WORDS = ["confirm", "yes", "yeah", "do it", "proceed", "sure", "go ahead", "haan", "haan ji"]
CANCEL_WORDS = ["cancel", "no", "nope", "stop", "abort", "do not", "dont", "nahi", "nahin", "nah"]

SHUTDOWN_DELAY = 5            # seconds between confirmed shutdown and the actual shutdown

# ------------------------------------------------------------
# HEARING / SCREEN SAFETY
# ------------------------------------------------------------
# Volume and brightness never go past these, no matter what is
# asked for. Drop MAX_VOLUME to 70 if the speakers are loud.

MAX_VOLUME = 100
MAX_BRIGHTNESS = 100
