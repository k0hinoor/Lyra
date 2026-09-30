"""
============================================================
 LYRA CONFIGURATION
============================================================
 Every knob of the assistant lives in this one file.
 Change values here — never touch the other code.
============================================================
"""

import json
import os
import sys
from pathlib import Path

from .voice_catalog import parse_voice_model

# ------------------------------------------------------------
# PATHS / USER DATA
# ------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
if os.environ.get("LYRA_DATA_DIR"):
    DATA_DIR = Path(os.environ["LYRA_DATA_DIR"]).expanduser()
elif sys.platform.startswith("win"):
    DATA_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "Lyra"
else:
    DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "lyra"

MODELS_DIR = DATA_DIR / "models"
VOICE_DIR = MODELS_DIR / "voice"
MEMORY_FILE = DATA_DIR / "memory.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
LOG_DIR = DATA_DIR / "logs"
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

# Save only clear first-person likes/dislikes, never model-inferred facts.
# Explicit remember/forget commands still work when this is disabled.
AUTO_REMEMBER_PREFERENCES = True

# ------------------------------------------------------------
# EARS  (faster-whisper speech-to-text)
# ------------------------------------------------------------

# Use multilingual names (without .en) for English, Hindi and Hinglish.
# "base" = quick on CPU | "small" = more accurate Hindi, but slower/larger.
WHISPER_MODEL = "base"
WHISPER_LANGUAGE = "auto"     # auto-detect each utterance; or force "en" / "hi"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE = "int8"      # int8 = fast on CPU
WHISPER_BEAM = 3              # 1 = fastest; 3–5 improves decoding at a CPU cost

# Words Whisper keeps mis-hearing ("brave" -> "breathe",
# "terminate" -> "terminal"). Passed to faster-whisper as hotwords.
WHISPER_HOTWORDS = (
    "Lyra Brave Chrome YouTube Notepad terminate execution "
    "लायरा लाइरा ब्रेव क्रोम यूट्यूब नोटपैड"
)

# ------------------------------------------------------------
# VOICE  (Piper text-to-speech)
# ------------------------------------------------------------

VOICE_MODEL = "en_US-lessac-medium"       # English replies
HINDI_VOICE_MODEL = "hi_IN-priyamvada-medium"  # Hindi / mixed-script replies
# Hindi alternatives: hi_IN-pratham-medium, hi_IN-rohan-medium.
# List/download choices with: python -m lyra.setup_voice --list

VOICE_REPO = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
VOICE_SENTENCE_SILENCE = 0.10       # small natural gap between streamed sentences (sec)

VOICE_SPEED = 1.15                  # speaking speed multiplier (clamped to 0.8-1.5)
VOICE_SPEED_MIN = 0.8
VOICE_SPEED_MAX = 1.5

OUTPUT_DEVICE = None                # None = Windows default output.
                                    # Run `python main.py --devices` to list
                                    # yours, then set the index (e.g. 5).

# ------------------------------------------------------------
# LISTENING
# ------------------------------------------------------------

WAKE_MODE = "wake"            # "wake" = say "Hey Lyra" first | "always" = react to everything
WAKE_WORD = "lyra"

# How Whisper commonly mis-hears the name — all treated as the wake word.
WAKE_NATIVE_NAMES = ["लायरा", "लाइरा", "लीरा", "लैरा", "लाय्रा"]
WAKE_ALIASES = ["lyra", "laira", "lira", "laura", "later", "leyra", "leira", "lyrah"] + WAKE_NATIVE_NAMES
WAKE_EXPLICIT_VARIANTS = ["bobby"]  # accepted only after a wake prefix, per user testing

WAKE_PREFIXES = [
    "hey", "ok", "okay", "hi", "hello", "yo", "hay",
    "हे", "हेय", "हाय", "हेलो", "हैलो", "नमस्ते", "ओके",
]

FOLLOW_UP_SECONDS = 12        # after a reply, Lyra stays awake this long —
                              # you can keep talking without repeating the wake word

SPEAK_BEEP = True             # short beep when Lyra wakes up / goes to sleep

PAUSE_THRESHOLD = 0.7         # silence that ends your sentence.
                              # (was 1.5 in the old brain — this alone saves ~0.8s per turn)
NON_SPEAKING_DURATION = 0.4
PHRASE_TIME_LIMIT = 15        # max seconds for one utterance
LISTEN_TIMEOUT = 8            # give up on silence after this

# ------------------------------------------------------------
# BARGE-IN  (talking over LYRA while she speaks)
# ------------------------------------------------------------
# The microphone keeps listening while she talks. A sustained voice
# (not a cough, not her own voice from the speakers) stops playback
# immediately and the captured phrase becomes the next command.
# Raise the multiplier on a room where the mic over-hears; lower it
# where her own voice comes back through the speakers.

INTERRUPT_ENERGY_MULTIPLIER = 2.0      # x the calibrated noise floor
INTERRUPT_ENERGY_MULTIPLIER_MIN = 1.0
INTERRUPT_ENERGY_MULTIPLIER_MAX = 10.0

INTERRUPT_MIN_VOICE_SECONDS = 0.15     # voice long enough to be a barge-in
INTERRUPT_SILENCE_SECONDS = 0.5        # trailing silence that ends the phrase
INTERRUPT_PHRASE_LIMIT = 10            # never capture more than this
INTERRUPT_ECHO_WINDOW_SECONDS = 30     # how long her own words stay "spoken"

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

# Optional user overrides. Only known, non-secret settings are read here;
# environment variables (LYRA_OLLAMA_MODEL, etc.) take precedence.
WAKE_VOSK_MODEL_DIR = MODELS_DIR / "vosk-model-small-en-us-0.15"
WAKE_WINDOW_SECONDS = 4.0
WAKE_FUZZY_MAX_DISTANCE = 2
LOG_LEVEL = "INFO"
CONSOLE_LOG_LEVEL = "WARNING"       # console shows only warnings/errors; the
                                    # log file keeps full INFO detail
GITHUB_REPOSITORY = "k0hinoor/Lyra"

# Preferred browser for web commands ("brave", "chrome", "edge" or "firefox").
# Empty string = use the Windows default browser.
BROWSER = ""

# Canonical browser names accepted in settings/env, with spoken aliases.
BROWSER_ALIASES = {
    "brave": "brave",
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "edge",
    "microsoft edge": "edge",
    "firefox": "firefox",
    "mozilla firefox": "firefox",
}


def clamp_voice_speed(value):
    """Parse a speaking-speed multiplier; clamp to the supported range.

    Returns None for values that are not numbers at all.
    """
    try:
        speed = float(value)
    except (TypeError, ValueError):
        return None
    return max(VOICE_SPEED_MIN, min(VOICE_SPEED_MAX, speed))


def clamp_interrupt_multiplier(value):
    """Parse the barge-in energy multiplier; clamp to the supported range.

    Returns None for values that are not numbers at all.
    """
    try:
        multiplier = float(value)
    except (TypeError, ValueError):
        return None
    return max(
        INTERRUPT_ENERGY_MULTIPLIER_MIN,
        min(INTERRUPT_ENERGY_MULTIPLIER_MAX, multiplier),
    )


def normalize_browser_name(value):
    """Canonical browser name, '' for the system default, None if unknown."""
    if value is None:
        return None
    name = str(value).strip().casefold()
    if not name:
        return ""
    return BROWSER_ALIASES.get(name)

_SETTINGS = {
    "OLLAMA_MODEL": "OLLAMA_MODEL",
    "VOICE_MODEL": "VOICE_MODEL",
    "HINDI_VOICE_MODEL": "HINDI_VOICE_MODEL",
    "AUTO_REMEMBER_PREFERENCES": "AUTO_REMEMBER_PREFERENCES",
    "VOICE_SPEED": "VOICE_SPEED",
    "INTERRUPT_ENERGY_MULTIPLIER": "INTERRUPT_ENERGY_MULTIPLIER",
    "BROWSER": "BROWSER",
    "OUTPUT_DEVICE": "OUTPUT_DEVICE",
    "WAKE_FUZZY_MAX_DISTANCE": "WAKE_FUZZY_MAX_DISTANCE",
    "WAKE_WINDOW_SECONDS": "WAKE_WINDOW_SECONDS",
    "WHISPER_MODEL": "WHISPER_MODEL",
    "WHISPER_LANGUAGE": "WHISPER_LANGUAGE",
    "WHISPER_BEAM": "WHISPER_BEAM",
    "OLLAMA_URL": "OLLAMA_URL",
    "LOG_LEVEL": "LOG_LEVEL",
    "CONSOLE_LOG_LEVEL": "CONSOLE_LOG_LEVEL",
}

def normalize_whisper_language(value):
    """Settings-friendly language values; None means an invalid selection."""
    aliases = {"auto": "auto", "en": "en", "english": "en", "hi": "hi", "hindi": "hi"}
    return aliases.get(str(value).strip().casefold())


def parse_boolean(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return {"true": True, "false": False, "1": True, "0": False}.get(value.strip().lower())
    return None


def _parse_setting(target, value):
    """Use identical validation for settings.json and LYRA_* overrides."""
    if target == "OUTPUT_DEVICE":
        return None if value is None else int(value)
    if target == "WAKE_FUZZY_MAX_DISTANCE":
        value = int(value)
        if not 0 <= value <= 2:
            raise ValueError("must be between 0 and 2")
    elif target == "WAKE_WINDOW_SECONDS":
        value = float(value)
        if not 1.0 <= value <= 8.0:
            raise ValueError("must be between 1 and 8 seconds")
    elif target in ("LOG_LEVEL", "CONSOLE_LOG_LEVEL"):
        value = str(value).upper()
        if value not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("invalid logging level")
    elif target == "VOICE_SPEED":
        value = clamp_voice_speed(value)
        if value is None:
            raise ValueError("must be a number for speaking speed")
    elif target == "INTERRUPT_ENERGY_MULTIPLIER":
        value = clamp_interrupt_multiplier(value)
        if value is None:
            raise ValueError("must be a number for the interrupt multiplier")
    elif target == "BROWSER":
        value = normalize_browser_name(value)
        if value is None:
            raise ValueError("must be brave, chrome, edge, firefox or empty")
    elif target == "WHISPER_BEAM":
        value = int(value)
        if not 1 <= value <= 5:
            raise ValueError("must be between 1 and 5")
    elif target == "WHISPER_LANGUAGE":
        value = normalize_whisper_language(value)
        if value is None:
            raise ValueError("must be auto, en or hi")
    elif target == "AUTO_REMEMBER_PREFERENCES":
        value = parse_boolean(value)
        if value is None:
            raise ValueError("must be true or false")
    elif target in ("VOICE_MODEL", "HINDI_VOICE_MODEL"):
        language, *_ = parse_voice_model(value)
        expected = "hi" if target == "HINDI_VOICE_MODEL" else "en"
        if language != expected:
            raise ValueError(f"{target} must be a {expected} Piper voice")
    elif not isinstance(value, str) or not value.strip():
        raise ValueError("must be a non-empty string")
    return value


try:
    with SETTINGS_FILE.open("r", encoding="utf-8") as _settings_file:
        _user_settings = json.load(_settings_file)
    if isinstance(_user_settings, dict):
        for _key, _target in _SETTINGS.items():
            if _key not in _user_settings:
                continue
            try:
                globals()[_target] = _parse_setting(_target, _user_settings[_key])
            except (TypeError, ValueError) as _error:
                import logging
                logging.getLogger(__name__).warning("Ignoring invalid setting %s: %s", _key, _error)
except FileNotFoundError:
    pass
except (OSError, ValueError) as _error:
    import logging
    logging.getLogger(__name__).warning("Could not load settings file: %s", _error)

for _key, _target in _SETTINGS.items():
    _env_key = "LYRA_" + _key
    if _env_key in os.environ:
        try:
            globals()[_target] = _parse_setting(_target, os.environ[_env_key])
        except (TypeError, ValueError) as _error:
            import logging
            logging.getLogger(__name__).warning("Ignoring invalid environment setting %s: %s", _env_key, _error)
