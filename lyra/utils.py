"""
============================================================
 LYRA UTILS
============================================================
 Text helpers: normalization, wake-word matching,
 name correction and streaming sentence splitting.
============================================================
"""

import re
import unicodedata

from . import config

# ------------------------------------------------------------
# NORMALIZE
# ------------------------------------------------------------

def normalize(text):
    """Lowercase, strip punctuation (keep apostrophes), collapse spaces."""

    text = unicodedata.normalize("NFC", text).lower().strip()
    # Python's \w excludes combining marks. Dropping those destroys Hindi
    # vowels/nuktas (पसंद -> पस द) before wake matching or command routing.
    text = "".join(
        char if char.isalnum() or char in "_'" or char.isspace()
        or unicodedata.category(char).startswith("M") else " "
        for char in text
    )
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ------------------------------------------------------------
# POLITE FILLER
# ------------------------------------------------------------
# People talk to an assistant, they don't type commands:
#   "can you please turn up the volume" -> "turn up the volume"
# The skills only know the bare verb, so the padding comes off
# here, once, before anything tries to match the command.

_LEADING_FILLER = (
    "i want you to", "i need you to", "i would like you to", "i'd like you to",
    "id like you to", "i want to", "i need to", "can you please",
    "could you please", "would you please", "will you please",
    "can you", "could you", "would you", "will you", "do you", "are you",
    "please", "kindly", "just", "right now", "now", "hey", "ok", "okay",
    "yo", "hi", "hello", "um", "uh", "er", "erm", "hmm",
    # Sentence-opening connectives people say out loud: "so what time is it",
    # "and what time is it", "well what time is it".
    "so", "and", "well",
)

_TRAILING_FILLER = (
    "right now", "now", "please", "for me", "okay", "ok", "thanks",
    "thank you",
)


def strip_politeness(text):
    """
    Peel conversational padding off both ends of a command.

    Never returns an empty string — text that is nothing but filler
    ("please") is handed back untouched for the brain to answer.
    """

    if not text:
        return text

    original = text
    stripped = text
    changed = True

    while changed and stripped:

        changed = False

        for filler in _LEADING_FILLER:
            if stripped.startswith(filler + " "):
                stripped = stripped[len(filler) + 1:].strip()
                changed = True
                break
        else:
            for filler in _TRAILING_FILLER:
                if stripped.endswith(" " + filler):
                    stripped = stripped[: -(len(filler) + 1)].strip()
                    changed = True
                    break

    return stripped or original


# ------------------------------------------------------------
# CORRECT LYRA NAME IN TRANSCRIPTION
# ------------------------------------------------------------

_NAME_PATTERN = re.compile(
    r"(?<![\w\u0900-\u097f])("
    + "|".join(re.escape(name) for name in config.WAKE_ALIASES + ["liara", "yara"])
    + r")(?![\w\u0900-\u097f])",
    re.IGNORECASE
)


def correct_name(text):
    """Capitalize every mis-heard variant of 'Lyra' in a transcript."""

    return _NAME_PATTERN.sub("Lyra", text)


# ------------------------------------------------------------
# WAKE WORD MATCHING
# ------------------------------------------------------------

def _edit_distance(left, right, max_distance=None):
    """Small bounded Levenshtein distance, sufficient for one wake token."""
    if abs(len(left) - len(right)) > (max_distance if max_distance is not None else max(len(left), len(right))):
        return (max_distance or 0) + 1
    previous = list(range(len(right) + 1))
    for row, char_left in enumerate(left, 1):
        current = [row]
        for column, char_right in enumerate(right, 1):
            current.append(min(
                current[-1] + 1,
                previous[column] + 1,
                previous[column - 1] + (char_left != char_right),
            ))
        if max_distance is not None and min(current) > max_distance:
            return max_distance + 1
        previous = current
    return previous[-1]


def _is_wake_name(token, fuzzy=False):
    token = token.casefold()
    if token in config.WAKE_ALIASES:
        return True
    if token in config.WAKE_EXPLICIT_VARIANTS:
        return True
    if fuzzy:
        return min(
            (_edit_distance(token, candidate, config.WAKE_FUZZY_MAX_DISTANCE)
             for candidate in ("lyra", "laira", "lira", "laura", "later", "leyra", "leira", "lyrah")),
            default=99,
        ) <= config.WAKE_FUZZY_MAX_DISTANCE
    return False


def strip_wake_word(normalized_text):
    """Match a wake phrase at the utterance start without broad word lists.

    Fuzzy matching is restricted to the name immediately after a wake prefix;
    ordinary speech such as "see you later" therefore cannot wake LYRA.
    """
    tokens = normalized_text.split()
    if not tokens:
        return False, ""

    if len(tokens) >= 2 and tokens[0] in config.WAKE_PREFIXES:
        if _is_wake_name(tokens[1], fuzzy=True):
            return True, " ".join(tokens[2:]).strip()
        return False, normalized_text

    if tokens[0] == config.WAKE_WORD or tokens[0] in config.WAKE_NATIVE_NAMES:
        return True, " ".join(tokens[1:]).strip()
    return False, normalized_text


# ------------------------------------------------------------
# TERMINATE / SLEEP PHRASES
# ------------------------------------------------------------

TERMINATE_PHRASES = {
    "terminate execution",
    "lyra terminate execution",
    "terminate execution lyra",
    "terminate the execution",
    # Close Whisper mishearings of "terminate execution" ("terminal",
    # "and the ..."). Kept exact-match so ordinary sentences cannot exit.
    "terminal execution",
    "the terminal execution",
    "and terminal execution",
    "and the terminal execution",
    "lyra terminal execution",
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

# Said over LYRA's own speech to shut it up (barge-in). Exact matches
# only, so "wait for the download" is never taken as a stop.
STOP_SPEECH_PHRASES = {
    "stop", "stop talking", "stop it", "be quiet", "quiet",
    "shut up", "silence", "hush", "hold on", "wait",
    "lyra stop", "stop lyra", "lyra be quiet", "lyra shut up",
    "lyra quiet", "lyra wait",
}

# Acknowledgements and noises that are not commands. Voice mode drops these
# instead of sending them to the chat model. Kept small and conservative:
# "yes" / "no" stay OUT because they may answer a pending confirmation.
FILLER_UTTERANCES = {
    "okay", "ok", "okay then", "ok then", "alright", "all right",
    "hmm", "hm", "mm", "mhm", "mhmm", "huh",
    "um", "uh", "er", "erm", "oh", "ah", "ooh",
    "so", "well", "and",        # bare connectives with no content
    "right then", "fair enough",
}


def is_filler(normalized_text):
    """True for utterances that carry no command ("Okay.", "hmm", ...)."""
    return normalized_text.strip() in FILLER_UTTERANCES


def is_terminate(normalized_text):
    return normalized_text in TERMINATE_PHRASES


def is_sleep(normalized_text):
    return normalized_text in SLEEP_PHRASES


def is_thanks(normalized_text):
    return normalized_text in THANKS_PHRASES


def is_stop_speech(normalized_text):
    """True for "stop", "be quiet", "shut up" — said over LYRA's speech."""
    return normalized_text.strip() in STOP_SPEECH_PHRASES


# ------------------------------------------------------------
# CLEAN TEXT FOR VOICE
# ------------------------------------------------------------

def speech_language(text):
    """Select a Hindi pack when an utterance contains Devanagari letters.

    Latin-only English uses the English pack. Mixed Hindi/English sentences
    use Hindi; romanized Hindi is intentionally not guessed from spelling.
    """
    return "hi" if any(
        "\u0900" <= char <= "\u097f" and unicodedata.category(char)[0] in {"L", "M"}
        for char in text
    ) else "en"


def clean_for_voice(text):
    """
    Make LLM output speakable by Piper:
    strip markdown symbols and emojis while preserving Unicode letters,
    turn % and ° into words.
    """

    text = re.sub(r"```.*?```", " code block ", text, flags=re.DOTALL)
    text = re.sub(r"[*_`#>\[\]|]", " ", text)
    hindi = speech_language(text) == "hi"
    text = text.replace("%", " प्रतिशत" if hindi else " percent")
    degrees = " डिग्री" if hindi else " degrees"
    text = text.replace("°C", degrees).replace("°F", degrees).replace("°", degrees)
    text = text.replace("&", " और " if hindi else " and ")
    text = text.replace("—", " ").replace("–", " ")

    # Hindi (and other scripts) must retain their vowels/combining marks.
    # Emoji symbols and their variation selectors are not speech content.
    cleaned = "".join(
        char for char in unicodedata.normalize("NFC", text)
        if char not in "\ufe0e\ufe0f" and (
            char.isascii() or unicodedata.category(char)[0] in {"L", "M", "N"}
            or char in "।॥…“”‘’"
        )
    )

    # collapse whitespace / newlines
    cleaned = re.sub(r"\s+", " ", cleaned)

    return cleaned.strip()


# ------------------------------------------------------------
# STREAMING SENTENCE SPLITTER
# ------------------------------------------------------------

_BOUNDARY = re.compile(r"(?:[.!?][\"')\]]?\s|[।॥][\"')\]]?\s*)")
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
