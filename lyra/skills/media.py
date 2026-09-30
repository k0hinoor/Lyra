"""
============================================================
 SKILL: MEDIA
============================================================
 Volume, brightness and media playback keys.

 Speech is not terminal input. "can you please turn the volume
 up a bit", "it is way too quiet", "set volume to sixty" and
 "turn it up to sixty" all reach the same skill, but as
 different words. Each one is reduced to (subject, action,
 amount) and then EXECUTED — Lyra does the job instead of
 reciting where the button lives.
============================================================
"""

import re

from .. import config
from ..messages import t
from ..utils import normalize

try:
    import pyautogui
    pyautogui.PAUSE = 0
    _PYAUTOGUI_OK = True
except Exception:
    _PYAUTOGUI_OK = False

try:
    import screen_brightness_control as sbc
    _BRIGHTNESS_OK = True
except Exception:
    _BRIGHTNESS_OK = False

_AUDIO_OK = False

try:
    from ctypes import POINTER, cast

    from comtypes import CLSCTX_ALL

    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    _AUDIO_OK = True
except Exception:
    pass



DEFAULT_STEP = 10           # "volume up" with no number moves ten points
SMALL_STEP = 5              # "... a bit"
BIG_STEP = 25               # "... a lot"


# ------------------------------------------------------------
# COMMAND VOCABULARY
# ------------------------------------------------------------

# Words that say WHAT is being controlled.
_SUBJECTS = {
    "volume": "volume", "vol": "volume", "sound": "volume", "audio": "volume",
    "speaker": "volume", "speakers": "volume", "playback": "volume",
    "music": "volume", "loudness": "volume", "loud": "volume",
    "quiet": "volume",
    "brightness": "brightness", "bright": "brightness", "dark": "brightness",
    "dim": "brightness", "screen": "brightness", "display": "brightness",
    "monitor": "brightness", "backlight": "brightness",
}

# "louder" is a subject AND a direction — it names the thing and the change.
_COMPARATIVES = {
    "louder": ("volume", 1), "quieter": ("volume", -1), "softer": ("volume", -1),
    "brighter": ("brightness", 1), "darker": ("brightness", -1),
    "dimmer": ("brightness", -1),
}

# Words that survive a "battery is too low" style complaint but carry no
# subject of their own.
_TOPIC_ONLY = {
    "loud": "volume", "quiet": "volume",
    "bright": "brightness", "dark": "brightness", "dim": "brightness",
}

_UP_WORDS = {
    "up", "louder", "higher", "increase", "increased", "increasing",
    "raise", "raised", "boost", "bumped", "bump", "amplify", "crank",
}

_DOWN_WORDS = {
    "down", "quieter", "lower", "lowered", "decrease", "decreased",
    "decreasing", "reduce", "reduced", "softer", "drop", "less", "dim",
}

# Verbs that make a bare "up"/"down" a real command.
_CONTROL_VERBS = {
    "turn", "turned", "turning", "make", "made", "set", "put", "change",
    "adjust", "move", "crank", "push", "bring", "go", "bump", "boost",
    "raise", "raised", "increase", "increased", "lower", "lowered",
    "decrease", "decreased", "reduce", "reduced", "drop", "keep", "try",
    "get", "give", "take",
}

# Verbs that mean "set an absolute level", not "move by a step".
_ABSOLUTE_VERBS = {"set", "put", "make", "change", "adjust", "move"}

# Everything a legitimate level command may contain. One unknown word
# (e.g. "scroll" in "scroll down the screen") means it is not ours.
_ALLOWED = (
    _CONTROL_VERBS
    | _UP_WORDS
    | _DOWN_WORDS
    | set(_SUBJECTS)
    | set(_COMPARATIVES)
    | set(_TOPIC_ONLY)
    | {
        "to", "at", "by", "a", "bit", "little", "slightly", "lot", "way",
        "much", "some", "step", "steps", "percent", "pct", "off", "all",
        "mute", "unmute", "silent", "silence", "shush",
        "low", "high", "what", "whats", "how", "much", "check", "current",
        "tell", "exactly",
    }
)

# A command that names no knob at all: "turn it up", "raise it", "louder".
# Only honoured when a verb is there too, so a stray "up" isn't a command.
_PRONOUN_OK = _CONTROL_VERBS | _UP_WORDS | _DOWN_WORDS | {"it", "that", "this"}

# Never treat these as an action, whatever else the sentence looks like.
_QUESTION_WORDS = {"why", "how", "what", "whats", "where", "when", "who", "which", "explain"}

# Words allowed when the command is only a question about the current level.
_READ_OK = {
    "level", "levels", "status", "how", "what", "whats", "howmuch",
    "current", "now", "check", "tell", "is", "are", "right", "again",
    "exactly", "at", "much",
}

# Complaints, checked on the raw words — "too" is dropped as filler later.
_TOO_QUIET = re.compile(
    r"\btoo (?:quiet|low|soft|small|faint|dark|dim)\b"
    r"|\b(?:cant|can ?not|cannot|unable ?to) hear\b"
    r"|\bnot (?:hearing|loud enough|hearing anything)\b"
    r"|\bno (?:sound|audio)\b"
    r"|\b(?:barely|hardly) (?:hear|audible)\b"
)

_TOO_LOUD = re.compile(
    r"\btoo (?:loud|noisy|high|sharp|strong|bright)\b"
    r"|\b(?:blasting|deafening|ear ?splitting)\b"
    r"|\btoo much\b"
)

# "I can't hear you" — no knob named, but the meaning is unmistakable.
_CANNOT_HEAR = re.compile(
    r"\b(?:cant|can ?not|cannot|unable ?to) hear\b|\bnot hearing (?:you|anything)\b"
)

# Opinion/taste language must not disappear as "filler" and turn
# "do you like music?" into a volume read, or "I like my music louder"
# into a volume change. "I would like you to turn it up" remains a request.
_OPINION = re.compile(
    r"^(?:(?:so|well|actually) )?"
    r"(?:(?:do|does|did|would) (?:you|he|she) |(?:i|you|he|she) )?"
    r"(?:really )?(?:like|love|enjoy|prefer|hate|dislike)\b"
)
_READ_KNOBS = {"volume", "vol", "brightness", "loudness", "backlight"}

# Spoken numbers -> digits.
_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}

_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}

_NAMED_LEVELS = {
    "half": 50, "full": 100, "max": 100, "maximum": 100, "min": 0,
    "minimum": 0, "muted": 0, "hundred": 100,
}

# Conversational filler — none of it changes what the user wants.
_FILLER = {
    "a", "an", "the", "my", "me", "mine", "i", "we", "us", "our", "its",
    "it", "this", "that", "these", "those", "there", "here", "to", "for",
    "of", "on", "in", "at", "by", "from", "with", "into", "is", "are",
    "am", "be", "been", "being", "do", "does", "did", "have", "has",
    "please", "pls", "can", "could", "would", "will", "shall", "should",
    "may", "might", "must", "you", "u", "your", "yours", "lyra", "hey",
    "hi", "hello", "ok", "okay", "just", "kindly", "now", "right", "well",
    "so", "then", "also", "too", "very", "really", "actually", "quite",
    "um", "uh", "er", "erm", "hmm", "all", "some", "thing", "stuff",
    "computer", "pc", "system", "device", "percent", "pct", "level",
    "levels", "status", "i'd", "id", "im", "ive", "lets", "let", "gonna",
    "wanna", "like", "need", "want", "would've", "could've",
}

_SMALL_WORDS = {"bit", "little", "slightly", "small"}
_BIG_WORDS = {"lot", "way", "much", "loads", "heaps"}


# ------------------------------------------------------------
# SPEECH -> (subject, action, amount)
# ------------------------------------------------------------

def _words(text):
    """Lowercase word list, apostrophes removed ("it's" -> "its")."""

    cleaned = text.lower().replace("’", "").replace("'", "")
    # Keep non-English words as unknown content, rather than discarding
    # them and accidentally executing the remaining English word(s).
    return normalize(cleaned).split()


def _subject_of(words):
    """
    Which knob is the user talking about, and any direction a
    comparative adjective carries. None means "not a level command".
    """

    subject = None
    direction = 0

    for word in words:

        if subject is None:
            subject = _SUBJECTS.get(word) or _TOPIC_ONLY.get(word)

        if not direction and word in _COMPARATIVES:
            subject = _COMPARATIVES[word][0]
            direction = _COMPARATIVES[word][1]

    return subject, direction


def _names_a_knob(words):
    """True when the text mentions volume or brightness at all."""

    return any(
        word in _SUBJECTS or word in _TOPIC_ONLY or word in _COMPARATIVES
        for word in words
    )


def _spelled_out_numbers(words):
    """Turn spoken numbers into digit strings: "twenty five" -> "25"."""

    out = []
    i = 0

    while i < len(words):

        word = words[i]

        if word in _NAMED_LEVELS:
            out.append(str(_NAMED_LEVELS[word]))
            i += 1
            continue

        if word in _TENS:
            nxt = words[i + 1] if i + 1 < len(words) else None
            if nxt in _UNITS:
                out.append(str(_TENS[word] + _UNITS[nxt]))
                i += 2
                continue
            out.append(str(_TENS[word]))
            i += 1
            continue

        if word in _UNITS:
            out.append(str(_UNITS[word]))
            i += 1
            continue

        out.append(word)
        i += 1

    return out


def _content(words):
    """Filler-free command words, numbers already as digits."""

    return [w for w in _spelled_out_numbers(words) if w not in _FILLER]


def _is_known(words):
    """False when an unfamiliar word is present — the text isn't ours."""

    return all(w in _ALLOWED or w.isdigit() for w in words)


def _step_of(words, default):
    """How far to move: an explicit number, or 'a bit' / 'a lot'."""

    for word in words:
        if word.isdigit():
            return int(word)

    if any(w in _SMALL_WORDS for w in words):
        return SMALL_STEP

    if any(w in _BIG_WORDS for w in words):
        return BIG_STEP

    return default


def _target_of(words, named_level=False):
    """
    The absolute level asked for, or None.

    "set volume to 50", "volume to fifty", "turn the volume up to 60",
    "make volume 40" and "full volume" all name a destination;
    "turn it up by 5" does not. Run this on the words BEFORE filler
    is dropped, because the destination marker is the word "to".
    """

    for index, word in enumerate(words):

        if word not in ("to", "at"):
            continue

        for later in words[index + 1:]:
            if later in _FILLER:
                continue
            if later.isdigit():
                return int(later)
            break

    if named_level:
        for word in words:
            if word.isdigit():
                return int(word)

    if any(w in _ABSOLUTE_VERBS for w in words):
        for word in words:
            if word.isdigit():
                return int(word)

    return None


def _level_command(text):
    """
    Returns (subject, action, amount) or None.

      subject  "volume" | "brightness"
      action   "read" | "up" | "down" | "set" | "mute" | "unmute"
      amount   step for "up"/"down", absolute level for "set"
    """

    words = _words(text)

    if not words or _OPINION.match(" ".join(words)):
        return None

    content = _content(words)
    spoken = _spelled_out_numbers(words)     # filler still in, numbers as digits
    is_question = bool(set(words) & _QUESTION_WORDS)

    # ---- mute / unmute with no knob named at all: "mute." -------
    # Naming a knob is what keeps "silence the notification" and
    # "the battery is too low" away from the volume control.

    if not _names_a_knob(words):

        if not is_question:

            if "unmute" in content:
                return "volume", "unmute", None

            # `content and` matters: an utterance made only of filler
            # ("hey lyra", "okay", "hmm", or Whisper hearing "you" in
            # background noise) leaves `content` empty, and the empty set
            # is a subset of every set, so it used to read as "mute".
            if content and set(content) <= {"mute", "silent", "silence", "shush"}:
                return "volume", "mute", None

            if _CANNOT_HEAR.search(" ".join(words)):
                return "volume", "up", _step_of(content, DEFAULT_STEP)

            # "turn it up", "raise it" — a verb with a direction and
            # no knob named still means the sound.
            if (
                all(w in _PRONOUN_OK or w.isdigit() for w in content)
                and set(content) & _CONTROL_VERBS
                and set(content) & (_UP_WORDS | _DOWN_WORDS)
            ):
                action = "up" if set(content) & _UP_WORDS else "down"
                return "volume", action, _step_of(content, DEFAULT_STEP)

        return None

    subject, comparative = _subject_of(words)

    if subject is None:
        return None                       # nothing that sounds like a knob

    if not _is_known(content):
        return None                       # "scroll down the screen", "open sound"

    # ---- mute / unmute -----------------------------------------

    if "unmute" in content:
        return subject, "unmute", None

    if any(w in ("mute", "silent", "silence") for w in content):
        return subject, "mute", None

    if subject == "volume" and "off" in content and (
        {"turn", "turning", "turned", "switch", "shut"} & set(content)
    ):
        return subject, "mute", None

    # ---- absolute level ----------------------------------------

    named_level = any(w in _NAMED_LEVELS for w in words)
    target = _target_of(spoken, named_level)

    if target is not None:
        return subject, "set", target

    # ---- direction ---------------------------------------------

    direction = 0

    for word in content:
        if word in _UP_WORDS:
            direction = 1
            break
        if word in _DOWN_WORDS:
            direction = -1
            break

    if not direction:
        direction = comparative

    if not direction:
        spoken = " ".join(words)
        if _TOO_QUIET.search(spoken):
            direction = 1
        elif _TOO_LOUD.search(spoken):
            direction = -1

    if direction:
        action = "up" if direction > 0 else "down"
        return subject, action, _step_of(content, DEFAULT_STEP)

    # ---- just asking what it is right now ----------------------

    explicit_read = bool(set(words) & (_READ_KNOBS | {"level", "levels"})) or (
        bool(set(words) & {"how", "what", "whats", "check", "current", "tell"})
        and bool(set(words) & set(_TOPIC_ONLY))
    )
    if explicit_read and all(w in _READ_OK or w in _SUBJECTS or w in _TOPIC_ONLY for w in content):
        return subject, "read", None

    return None


# ------------------------------------------------------------
# VOLUME INTERFACE
# ------------------------------------------------------------

def _volume_interface():

    from comtypes import CoInitialize

    try:
        CoInitialize()
    except Exception:
        pass

    device = AudioUtilities.GetSpeakers()

    # pycaw 20251023 and later wrap the speakers in an AudioDevice that
    # has no Activate() of its own and exposes the endpoint volume as a
    # property instead. Older releases return the raw IMMDevice, which
    # has to be activated by hand. The class is checked (not the
    # instance) so a real COM error inside the property is not mistaken
    # for "old pycaw".
    if hasattr(type(device), "EndpointVolume"):
        return device.EndpointVolume

    interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)

    return cast(interface, POINTER(IAudioEndpointVolume))


def _current_volume():
    volume = _volume_interface()
    return round(volume.GetMasterVolumeLevelScalar() * 100)


def _set_volume(percent):
    percent = max(0, min(100, int(percent)))
    volume = _volume_interface()
    volume.SetMasterVolumeLevelScalar(percent / 100.0, None)
    return percent


def _is_muted():
    try:
        return bool(_volume_interface().GetMute())
    except Exception:
        return False


def _set_muted(muted):
    _volume_interface().SetMute(1 if muted else 0, None)


def _clamp(value, ceiling):
    return max(0, min(int(value), int(ceiling)))


# ------------------------------------------------------------
# EXECUTE
# ------------------------------------------------------------

def _run_volume(action, amount):

    if not _AUDIO_OK:
        return t("media.no_pycaw")

    try:

        if action == "read":
            return t("media.volume_is", level=_current_volume())

        if action == "mute":
            _set_muted(True)
            return t("media.muted")

        if action == "unmute":
            _set_muted(False)
            return t("media.unmuted")

        ceiling = config.MAX_VOLUME

        if action == "set":
            wanted = amount
            level = _set_volume(_clamp(amount, ceiling))
        else:
            wanted = None
            current = _current_volume()
            level = _set_volume(
                _clamp(current + amount if action == "up" else current - amount,
                       ceiling)
            )

    except Exception as e:
        print(f"Volume error: {e}")
        return (
            t("media.volume_read_failed")
            if action == "read"
            else t("media.volume_change_failed")
        )

    if action == "up" and _is_muted():
        # raising a muted volume is a no-op — say it out loud instead of failing
        try:
            _set_muted(False)
        except Exception as e:
            print(f"Unmute error: {e}")
            return t("media.volume_still_muted", level=level)
        return t("media.unmuted_volume_set", level=level)

    if wanted is not None and wanted > ceiling:
        return t("media.volume_set_max", level=level)

    return t("media.volume_set", level=level)


def _run_brightness(action, amount):

    if not _BRIGHTNESS_OK:
        return t("media.no_brightness")

    ceiling = config.MAX_BRIGHTNESS

    try:

        if action == "read":
            return t("media.brightness_is", level=sbc.get_brightness()[0])

        if action == "set":
            wanted = amount
            level = _clamp(amount, ceiling)
        else:
            wanted = None
            current = sbc.get_brightness()[0]
            level = _clamp(
                current + amount if action == "up" else current - amount,
                ceiling,
            )

        sbc.set_brightness(level)

    except Exception as e:
        print(f"Brightness error: {e}")
        return (
            t("media.brightness_read_failed")
            if action == "read"
            else t("media.brightness_change_failed")
        )

    if wanted is not None and wanted > ceiling:
        return t("media.brightness_set_max", level=level)

    return t("media.brightness_set", level=level)


# ------------------------------------------------------------
# MEDIA KEYS
# ------------------------------------------------------------

def _press_media(key):
    pyautogui.press(key)


_MEDIA_NOUN = r"(?:music|song|songs|video|media|track|tracks|playback|playlist|audio)"


# ------------------------------------------------------------
# HANDLE
# ------------------------------------------------------------

def handle(text, raw=None):

    text = text.strip()

    if not text:
        return None

    # "full screen" means the F11 toggle (windows skill) — it used to be
    # parsed as level "full" of subject "screen" and blast brightness to
    # 100%. ("full volume" / "full brightness" stay legitimate.)
    if re.search(r"\bfull ?(?:screen|display)\b", text.lower()):
        return None

    # --------------------------------------------------------
    # VOLUME / BRIGHTNESS  (executed, never explained)
    # --------------------------------------------------------

    command = _level_command(text)

    if command is not None:
        subject, action, amount = command

        if subject == "volume":
            return _run_volume(action, amount)

        return _run_brightness(action, amount)

    # --------------------------------------------------------
    # PLAYBACK KEYS
    # --------------------------------------------------------

    if not _PYAUTOGUI_OK:
        return None

    lowered = text.lower()
    optional = rf"(?: (?:some |the |this |my )?{_MEDIA_NOUN})?"
    required = rf"(?: (?:some |the |this |my )?{_MEDIA_NOUN})"

    if re.match(rf"^(?:play|resume|start){optional}$", lowered):
        _press_media("playpause")
        return t("media.playing")

    if re.match(rf"^pause{optional}$", lowered) \
            or re.match(rf"^(?:stop|halt){required}$", lowered):
        _press_media("playpause")
        return t("media.paused")

    if re.match(r"^(?:next|skip)(?: (?:the |this )?(?:track|song|video|media))?$", lowered) \
            or re.match(rf"^skip (?:to )?(?:the )?next{required}$", lowered):
        _press_media("nexttrack")
        return t("media.next")

    if re.match(r"^(?:previous|last)(?: (?:the )?(?:track|song|video|media))?$", lowered):
        _press_media("prevtrack")
        return t("media.previous")

    return None


def name():
    return "media"
