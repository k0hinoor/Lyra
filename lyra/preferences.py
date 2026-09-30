"""Extract explicit first-person tastes, not guesses from the chat model.

This deliberately accepts simple assertions only. Questions, quotations,
hypotheticals and statements about other people do not become memories.
English, Hindi and a common romanized Hindi form are supported.
"""

import re
import unicodedata

MAX_PREFERENCE_LENGTH = 160
MAX_PREFERENCES_PER_TURN = 6

_VERBS = (
    r"don't (?:really )?(?:like|enjoy)|do not (?:really )?(?:like|enjoy)|"
    r"no longer (?:like|enjoy)|dislike|hate|like|love|enjoy|prefer"
)
_ENGLISH = re.compile(
    rf"^(?:(?:so|well|actually|personally|honestly|also)[, ]+)*"
    rf"i (?:really |absolutely )?(?P<verb>{_VERBS}) (?P<topic>.+)$",
    re.IGNORECASE,
)
_HINDI = re.compile(
    r"^मुझे (?P<topic>.+?) (?:बहुत |काफी |काफ़ी |बिल्कुल )?"
    r"(?:(?P<before>नहीं )?पसंद(?P<after> नहीं)?|(?P<dislike>नापसंद)) "
    r"(?:है|हैं)$"
)
_ROMANIZED = re.compile(
    r"^mujhe (?P<topic>.+?) (?:bahut |bilkul )?"
    r"(?P<before>nahi |nahin )?pasand(?P<after> nahi| nahin)? (?:hai|hain)$",
    re.IGNORECASE,
)
_CLAUSE_BOUNDARY = re.compile(
    rf"\s+(?:but|and|while)\s+(?=(?:i )?(?:really |absolutely )?(?:{_VERBS})\b)"
    r"|\s+(?:लेकिन|पर)\s+"
    r"|\s+और\s+(?=मुझे )",
    re.IGNORECASE,
)
_UNCERTAIN_OR_REQUEST = re.compile(
    r"\b(?:maybe|perhaps|if|might|used to|not sure|joking|"
    r"can you|could you|would you|please|don't remember|do not remember|"
    r"don't save|do not save|forget this|"
    r"(?:and|but|then) (?:turn|set|open|launch|play|press|click|write|type))\b"
    r"|शायद|अगर|याद मत|मत याद",
    re.IGNORECASE,
)


_TASTE_QUESTION = re.compile(
    r"^(?:(?:so|well|actually)[, ]+)?"
    r"(?:(?:do|would) you (?:really )?(?:like|love|enjoy|prefer|hate|dislike)\b"
    r"|(?:what|which) (?:music|song|songs|genre|genres|artists?) do you (?:like|prefer)\b)",
    re.IGNORECASE,
)


def is_taste_conversation(text):
    """An opinion/assertion is chat, even when too complex to save safely.

    This intent check is deliberately separate from extraction. A sentence
    such as 'I like to open Notepad and write stories' is not permission to
    dispatch a desktop action plan.
    """
    text = unicodedata.normalize("NFC", text or "").replace("’", "'")
    text = re.sub(r"\s+", " ", text).strip(" ,;.!।॥")
    return bool(
        _TASTE_QUESTION.match(text) or _ENGLISH.fullmatch(text)
        or _HINDI.fullmatch(text) or _ROMANIZED.fullmatch(text)
    )


def extract_preferences(text):
    """Return bounded (likes/dislikes, topic) pairs stated by the user.

    Never infer a preference from a request to play music or from LYRA's
    own reply. A repeated topic is updated by Memory, not accumulated as
    contradictory facts.
    """
    text = unicodedata.normalize("NFC", text or "").replace("’", "'")
    text = re.sub(r"\s+", " ", text).strip()
    if not text or any(char in text for char in '?"“”`'):
        return []
    if _UNCERTAIN_OR_REQUEST.search(text):
        return []

    preferences = []
    previous_language = None
    for clause in _CLAUSE_BOUNDARY.split(text):
        clause = clause.strip(" ,;.!।॥")
        # "I like jazz but don't like rap" shares the same subject.
        if previous_language == "en" and re.match(rf"^(?:{_VERBS})\b", clause, re.I):
            clause = "I " + clause
        elif previous_language == "hi" and not clause.startswith("मुझे "):
            clause = "मुझे " + clause

        match = _ENGLISH.fullmatch(clause)
        if match:
            previous_language = "en"
            verb = match.group("verb").casefold()
            polarity = "dislikes" if verb.startswith(("don't", "do not", "no longer")) \
                or verb in {"dislike", "hate"} else "likes"
        else:
            match = _HINDI.fullmatch(clause)
            if match:
                previous_language = "hi"
                polarity = "dislikes" if any(match.group(key) for key in ("before", "after", "dislike")) \
                    else "likes"
            else:
                match = _ROMANIZED.fullmatch(clause)
                if not match:
                    continue
                previous_language = "romanized"
                polarity = "dislikes" if match.group("before") or match.group("after") else "likes"

        topic = match.group("topic").strip(" ,;.!।॥")
        topic = re.sub(r"\s+(?:anymore|now|these days|at all)$", "", topic, flags=re.I)
        # Complex statements stay in short-term chat, rather than saving a
        # fragment, a second sentence, a negated object or an instruction.
        if not topic or len(topic) > MAX_PREFERENCE_LENGTH \
                or re.match(r"^(?:not|no)\b|^नहीं", topic, re.I) \
                or topic.startswith("'") \
                or re.search(r"[;!।॥]|\.\s+(?:i|you|he|she|they|we)\b", topic, re.I):
            continue
        pair = (polarity, topic)
        if pair not in preferences:
            preferences.append(pair)
        if len(preferences) >= MAX_PREFERENCES_PER_TURN:
            break
    return preferences
