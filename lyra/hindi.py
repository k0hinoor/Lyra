"""
============================================================
 LYRA HINDI -> INTENT
============================================================
 A small, deterministic, offline rewrite of RECOGNISED Hindi
 command vocabulary into the English phrasing the existing
 skills already understand:

   ब्रेव क्रोम यूट्यूब खोलो   -> "open brave and youtube"
   यूट्यूट्यूब                -> "open youtube"
   नोटपैड खोलो               -> "open notepad"
   आवाज़ बढ़ाओ               -> "volume up"
   Brave YouTube खोलो        -> "open brave and youtube"   (mixed script)

 Rules that keep it safe:
 - Only utterances containing Devanagari are considered, so typed
   English commands in --text mode route exactly as before.
 - EVERY word must be known command vocabulary (a verb, a name, a
   number or a tiny filler such as "को"/"में"/"कृपया"). One unknown
   word and nothing is rewritten, so free-form conversation
   ("मुझे कहानी सुनाओ", "मुझे यूट्यूब पसंद है") always reaches the
   chat model untouched. Nothing is ever translated.
 - No LLM, no network, no new dependency.
============================================================
"""

import re
import unicodedata

from .utils import normalize

# ------------------------------------------------------------
# SPELLING NORMALISATION
# ------------------------------------------------------------
# Whisper spells the same Hindi word several ways: with or without a nukta
# (आवाज़/आवाज), chandrabindu or anusvara (हाँ/हां), candra-o or plain o
# (वॉल्यूम/वोल्यूम). Matching happens on one canonical key.

_KEY_MAP = str.maketrans({
    "\u093c": None,        # nukta
    "\u0901": "\u0902",    # chandrabindu -> anusvara
    "\u0949": "\u094b",    # candra o sign -> o sign
    "\u0911": "\u0913",    # candra O -> O
    "\u0945": "\u0947",    # candra e sign -> e sign
})

# One letter for the stutter pattern (\w does not cover Devanagari vowel
# signs or the virama, so the combining marks are listed explicitly).
_LETTER = r"(?:[^\W\d_]|[\u0900-\u0903\u093a-\u094f\u0951-\u0957\u0962\u0963])"
_STUTTER = re.compile(r"(" + _LETTER + r"{2,}?)\1+")


def has_devanagari(text):
    """True when the text contains at least one Devanagari letter or sign."""

    return any("\u0900" <= char <= "\u097f" for char in text or "")


def _key(word):
    """Canonical spelling of one word (or phrase) for lexicon lookups."""

    # NFD first so precomposed nukta letters (U+0958-U+095F) split into
    # base letter + nukta, which the map then drops.
    return unicodedata.normalize("NFC", unicodedata.normalize("NFD", word).translate(_KEY_MAP))


def spelling_key(text):
    """Canonical spelling of a whole text (nukta/chandrabindu variants folded)."""

    return _key(text or "")


def _destutter(word):
    """Fold a glued stutter: "यूट्यूट्यूब" -> "यूट्यूब". Name lookups only."""

    return _STUTTER.sub(r"\1", word)


def _keyed(table):
    return {_key(phrase): value for phrase, value in table.items()}


# ------------------------------------------------------------
# VOCABULARY
# ------------------------------------------------------------

# Verb phrases -> action. Longest phrase wins ("बंद कर दो" before "बंद").
_VERBS = _keyed({
    # open
    "खोलो": "open", "खोल दो": "open", "खोल दीजिए": "open", "खोलिए": "open",
    "खोल": "open", "ओपन करो": "open", "ओपन कर दो": "open", "ओपन": "open",
    "चालू करो": "open", "चालू कर दो": "open", "चालू": "open", "open": "open",
    # close
    "बंद करो": "close", "बंद कर दो": "close", "बंद कीजिए": "close", "बंद": "close",
    # play
    "बजाओ": "play", "बजा दो": "play", "चलाओ": "play", "चला दो": "play",
    "लगाओ": "play", "लगा दो": "play", "प्ले करो": "play", "प्ले": "play",
    # up
    "बढ़ाओ": "up", "बढ़ा दो": "up", "तेज़ करो": "up", "तेज़ कर दो": "up",
    "ज़्यादा करो": "up", "ज़्यादा कर दो": "up",
    # down
    "कम करो": "down", "कम कर दो": "down", "कम": "down", "धीमा करो": "down",
    "धीमी करो": "down", "धीमा": "down", "घटाओ": "down", "घटा दो": "down",
    # mute / unmute
    "म्यूट करो": "mute", "म्यूट कर दो": "mute", "म्यूट": "mute",
    "अनम्यूट करो": "unmute", "अनम्यूट": "unmute",
    # tell / what is
    "बताओ": "what", "बता दो": "what", "बताइए": "what", "क्या है": "what",
    "कैसा है": "what", "क्या हुआ है": "what",
    # set to a number ("आवाज़ 50 करो")
    "करो": "set", "कर दो": "set", "सेट करो": "set", "सेट कर दो": "set",
    # restart
    "रीस्टार्ट करो": "restart", "रीस्टार्ट कर दो": "restart", "रीस्टार्ट": "restart",
})

# Name phrases -> the English word the skills know. Latin spellings are
# accepted too: Whisper often keeps brand names in Latin inside Hindi speech.
_NAMES = _keyed({
    "ब्रेव": "brave", "क्रोम": "chrome", "गूगल क्रोम": "chrome",
    "एज": "edge", "माइक्रोसॉफ्ट एज": "edge",
    "फायरफॉक्स": "firefox", "फ़ायरफ़ॉक्स": "firefox",
    "यूट्यूब": "youtube", "यू ट्यूब": "youtube",
    "नोटपैड": "notepad", "नोट पैड": "notepad",
    "गूगल": "google",
    "आवाज़": "volume", "वॉल्यूम": "volume", "साउंड": "volume",
    "ब्राइटनेस": "brightness", "चमक": "brightness",
    "गाना": "music", "गाने": "music", "गीत": "music", "म्यूज़िक": "music",
    "समय": "time", "टाइम": "time",
    "मौसम": "weather",
    "तारीख": "date", "तारीख़": "date",
    "कंप्यूटर": "pc", "कम्प्यूटर": "pc", "पीसी": "pc", "सिस्टम": "pc", "लैपटॉप": "pc",
    # Latin names inside Devanagari speech ("Brave Chrome YouTube खोलो")
    "brave": "brave", "chrome": "chrome", "google chrome": "chrome",
    "edge": "edge", "firefox": "firefox", "youtube": "youtube",
    "notepad": "notepad", "google": "google", "volume": "volume",
    "brightness": "brightness",
})

_BROWSERS = ("brave", "chrome", "edge", "firefox")
_SITES = {"youtube", "google"}
_OPENABLE = set(_BROWSERS) | _SITES | {"notepad"}
_KNOBS = {"volume", "brightness"}

# Words that carry no command meaning of their own.
_FILLER = {_key(word) for word in (
    "कृपया", "प्लीज़", "please", "ज़रा", "को", "का", "की", "के", "में", "पर",
    "भी", "तो", "ना", "जी", "अभी", "और", "प्रतिशत", "परसेंट", "percent", "आज",
)}

# "थोड़ा" / "बहुत" size the step of a volume/brightness change.
_SMALL = {_key("थोड़ा"), _key("थोड़ी")}
_BIG = {_key("बहुत"), _key("ज़्यादा")}

# Whole utterances with a fixed meaning.
_PHRASES = _keyed({
    "कितने बजे हैं": "what time is it",
    "कितने बज गए": "what time is it",
    "कितने बज गए हैं": "what time is it",
    "टाइम क्या हुआ है": "what time is it",
    "समय क्या हुआ है": "what time is it",
    "रुको": "stop", "रुक जाओ": "stop", "स्टॉप": "stop", "बस करो": "stop",
})

_LONGEST_PHRASE = max(len(phrase.split()) for phrase in list(_VERBS) + list(_NAMES))


# ------------------------------------------------------------
# PARSE
# ------------------------------------------------------------

def _number(word):
    """"50" / "५०" -> 50; None for anything else."""

    if word and all(unicodedata.digit(char, None) is not None for char in word):
        return int("".join(str(unicodedata.digit(char)) for char in word))
    return None


def _parse(words):
    """(verbs, names, number, size) for a fully understood utterance, else None."""

    verbs, names = [], []
    number = None
    size = ""
    index = 0

    while index < len(words):
        for span in range(min(_LONGEST_PHRASE, len(words) - index), 0, -1):
            phrase = " ".join(words[index:index + span])
            if phrase in _NAMES:
                names.append(_NAMES[phrase])
                break
            if phrase in _VERBS:
                verbs.append(_VERBS[phrase])
                break
        else:
            word = words[index]
            span = 1
            value = _number(word)
            if value is not None and number is None:
                number = value
            elif word in _SMALL:
                size = " a bit"
            elif word in _BIG:
                size = " a lot"
            elif word in _FILLER:
                pass
            elif _NAMES.get(_destutter(word)) in _OPENABLE:
                # A stuttered brand name ("यूट्यूट्यूब"). Only openable names
                # are rescued this way; ordinary words are never folded.
                names.append(_NAMES[_destutter(word)])
            else:
                return None                     # unknown word: not a command
        index += span

    return verbs, names, number, size


def _dedupe(items):
    out = []
    for item in items:
        if item not in out:
            out.append(item)
    return out


def _compose(verbs, names, number, size):
    """English command for one parsed utterance, or None."""

    verbs = _dedupe(verbs)
    names = _dedupe(names)

    # "आवाज़ 50 कर दो": the bare "करो" is only a verb next to a number.
    if len(verbs) > 1 and "set" in verbs:
        verbs.remove("set")
    if len(verbs) > 1:
        return None
    verb = verbs[0] if verbs else None

    if verb == "set" and number is None:
        return None
    if number is not None and verb not in ("set", "up", "down"):
        return None

    # --- a bare name: "यूट्यूट्यूब" -> open YouTube -----------------
    if verb is None:
        if len(names) == 1 and names[0] in _OPENABLE and not size:
            return f"open {names[0]}"
        return None

    if verb == "open":
        if names == ["volume"]:
            return "unmute"
        if not names or not set(names) <= _OPENABLE:
            return None
        browsers = [name for name in names if name in _BROWSERS]
        others = [name for name in names if name not in _BROWSERS]
        if len(others) > 1:
            return None
        if not others:
            return f"open {browsers[0]}"        # "ब्रेव क्रोम खोलो": the first browser named
        if browsers:
            return f"open {browsers[0]} and {others[0]}"
        return f"open {others[0]}"

    if verb == "close":
        if names == ["volume"]:
            return "mute"
        if names == ["pc"]:
            return "shut down the pc"
        if names == ["music"]:
            return "pause music"
        if len(names) == 1 and names[0] in _SITES:
            return "close tab"
        if len(names) == 1 and names[0] in _OPENABLE:
            return f"close {names[0]}"
        return None

    if verb == "play":
        if not names or names == ["music"]:
            return "play music" if names else "play"
        if "youtube" in names and set(names) <= {"youtube", "music"}:
            return "open youtube"
        return None

    if verb in ("up", "down"):
        if len(names) != 1 or names[0] not in _KNOBS:
            return None
        if number is not None:
            return f"turn {names[0]} {verb} by {number}"
        return f"{names[0]} {verb}{size}"

    if verb == "set":
        if len(names) != 1 or names[0] not in _KNOBS:
            return None
        return f"set {names[0]} to {number}"

    if verb in ("mute", "unmute"):
        if names and names != ["volume"]:
            return None
        return verb

    if verb == "what":
        topic = {
            ("time",): "what time is it",
            ("weather",): "weather",
            ("date",): "what is the date",
            ("volume",): "what is the volume",
            ("brightness",): "what is the brightness",
        }
        return topic.get(tuple(names))

    if verb == "restart":
        return "restart the pc" if names == ["pc"] else None

    return None


def to_command(text):
    """English command for recognised Hindi command vocabulary, else None.

    Returns None for text without Devanagari, for anything containing a word
    outside the command vocabulary, and for combinations that do not form a
    command the skills support. Never translates conversation.
    """

    if not has_devanagari(text):
        return None

    words = [_key(word) for word in normalize(text).split()]
    if not words:
        return None

    phrase = " ".join(words)
    if phrase in _PHRASES:
        return _PHRASES[phrase]

    parsed = _parse(words)
    if parsed is None:
        return None

    return _compose(*parsed)
