"""
============================================================
 LYRA UTILS
============================================================
 Text helpers: normalization, wake-word matching,
 name correction and streaming sentence splitting.
============================================================
"""

import re

from . import config

# ------------------------------------------------------------
# NORMALIZE
# ------------------------------------------------------------

def normalize(text):
    """Lowercase, strip punctuation (keep apostrophes), collapse spaces."""

    text = text.lower().strip()
    text = re.sub(r"[^\w\s']+", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ------------------------------------------------------------
# CORRECT LYRA NAME IN TRANSCRIPTION
# ------------------------------------------------------------

_NAME_PATTERN = re.compile(
    r"\b(" + "|".join(config.WAKE_ALIASES) + r")\b",
    re.IGNORECASE
)


def correct_name(text):
    """Capitalize every mis-heard variant of 'Lyra' in a transcript."""

    return _NAME_PATTERN.sub("Lyra", text)


# ------------------------------------------------------------
# WAKE WORD MATCHING
# ------------------------------------------------------------

def strip_wake_word(normalized_text):
    """
    Detect 'lyra' / 'hey lyra' / 'ok lyra' ... at the start.

    Returns (matched, remainder).
    remainder == ""  means the user only said the wake word.
    """

    tokens = normalized_text.split()

    if not tokens:
        return False, ""

    # "hey lyra ..." style
    if (
        len(tokens) >= 2
        and tokens[0] in config.WAKE_PREFIXES
        and tokens[1] in config.WAKE_ALIASES
    ):
        return True, " ".join(tokens[2:]).strip()

    # "lyra ..." style
    if tokens[0] in config.WAKE_ALIASES:
        return True, " ".join(tokens[1:]).strip()

    return False, normalized_text


# ------------------------------------------------------------
# TERMINATE / SLEEP PHRASES
# ------------------------------------------------------------

TERMINATE_PHRASES = {
    "terminate execution",
    "lyra terminate execution",
    "terminate execution lyra",
    "goodbye lyra",
    "lyra goodbye",
    "bye lyra",
    "shut yourself down",
    "power off lyra",
    "exit lyra",
    "quit lyra",
}

SLEEP_PHRASES = {
    "go to sleep",
    "sleep",
    "go back to sleep",
    "that's all",
    "thats all",
    "that will be all",
    "nothing",
    "never mind",
    "nevermind",
}

THANKS_PHRASES = {"thanks", "thank you", "thank you lyra", "thanks lyra", "shukriya"}


def is_terminate(normalized_text):
    return normalized_text in TERMINATE_PHRASES


def is_sleep(normalized_text):
    return normalized_text in SLEEP_PHRASES


def is_thanks(normalized_text):
    return normalized_text in THANKS_PHRASES


# ------------------------------------------------------------
# CLEAN TEXT FOR VOICE
# ------------------------------------------------------------

def clean_for_voice(text):
    """
    Make LLM output speakable by Piper:
    strip markdown symbols, emojis and non-ASCII chars,
    turn % and ° into words.
    """

    text = re.sub(r"```.*?```", " code block ", text, flags=re.DOTALL)
    text = re.sub(r"[*_`#>\[\]|]", " ", text)
    text = text.replace("%", " percent")
    text = text.replace("°C", " degrees").replace("°F", " degrees").replace("°", " degrees")
    text = text.replace("&", " and ")

    # keep ASCII only (this also removes emojis)
    cleaned = "".join(char for char in text if ord(char) < 128)

    # collapse whitespace / newlines
    cleaned = re.sub(r"\s+", " ", cleaned)

    return cleaned.strip()


# ------------------------------------------------------------
# STREAMING SENTENCE SPLITTER
# ------------------------------------------------------------

_BOUNDARY = re.compile(r"[.!?][\"')\]]?\s")
_RUNAWAY_CHARS = 400        # force a split if no punctuation for this long


class SentenceSplitter:
    """
    Feed it LLM tokens as they stream in; it emits complete
    sentences the moment they are ready so TTS can start early.
    """

    def __init__(self, min_len=24):
        self.min_len = min_len
        self.buf = ""

    def feed(self, text):
        self.buf += text
        out = []
        start = 0

        for match in _BOUNDARY.finditer(self.buf):
            end = match.end()
            if end - start >= self.min_len:
                out.append(self.buf[start:end].strip())
                start = end

        # runaway guard: no punctuation for a long stretch
        if len(self.buf) - start > _RUNAWAY_CHARS:
            cut = self.buf.rfind(" ", start + _RUNAWAY_CHARS // 2)
            if cut != -1:
                out.append(self.buf[start:cut].strip())
                start = cut + 1

        self.buf = self.buf[start:]

        return [s for s in out if s]

    def finish(self):
        rest = self.buf.strip()
        self.buf = ""
        return rest


def split_sentences(text, min_len=24):
    """Split a full text into sentence chunks (for plain speak())."""

    splitter = SentenceSplitter(min_len)
    out = splitter.feed(text + " ")
    tail = splitter.finish()

    if tail:
        out.append(tail)

    return out
