"""
============================================================
 SKILL: FUN
============================================================
 Jokes, coin flips, dice, random numbers. All offline.
============================================================
"""

import random
import re

from ..messages import is_hindi, t

JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "I told my computer I needed a break, and now it won't stop sending me KitKat ads.",
    "Why did the developer go broke? Because he used up all his cache.",
    "There are ten types of people: those who understand binary, and those who don't.",
    "Why was the JavaScript developer sad? Because he didn't Node how to Express himself.",
    "I would tell you a UDP joke, but you might not get it.",
    "My Wi-Fi and I have a lot in common. We both go down when everyone needs us most.",
    "Why do Java developers wear glasses? Because they don't C sharp.",
]

# Every joke above is a pun, and most people have never heard of UDP or
# a JavaScript framework. Spoken aloud there is no way to look it up, so
# the pun is decoded out loud straight after the punchline.
EXPLANATIONS = {
    JOKES[0]: (
        "A bug is a coding error, but it also means an insect, and "
        "insects are drawn to light."
    ),
    JOKES[1]: (
        "Break is the English word for a rest, but it is also a chocolate "
        "bar you snap in two."
    ),
    JOKES[2]: (
        "Cache is a super fast storage area on a computer, and to cache "
        "something also means to hide it, so he spent all his savings."
    ),
    JOKES[3]: (
        "Binary is the ones and zeros that computers read, and the number "
        "ten in binary is written as one zero one zero."
    ),
    JOKES[4]: (
        "Node and Express are two tools that JavaScript programmers use, "
        "but they are also ordinary English words, so the names do double duty."
    ),
    JOKES[5]: (
        "UDP is a way of sending data over the internet that never checks "
        "whether it arrived, so the joke could simply get lost on the way."
    ),
    JOKES[6]: (
        "It is about weak Wi-Fi dropping out at exactly the moment a video "
        "call or a meeting starts."
    ),
    JOKES[7]: (
        "Java is a programming language, and C sharp is pronounced see "
        "sharp, so it sounds like an eye test."
    ),
}


# Hindi mode: short, clean jokes that work in Hindi without an explanation.
HINDI_JOKES = [
    "कंप्यूटर को ठंड क्यों लगी? क्योंकि उसकी विंडो खुली रह गई थी।",
    "मैंने फ़ोन से कहा कि मुझे थोड़ा आराम चाहिए, तो उसकी बैटरी ही लो हो गई।",
    "वाई-फ़ाई और मुझमें एक बात एक जैसी है, दोनों तभी गायब होते हैं जब सबको सबसे ज़्यादा ज़रूरत हो।",
    "टीचर ने पूछा, सबसे ज़्यादा बर्फ़ कहाँ मिलती है? बच्चा बोला, हमारे फ्रिज में, मैडम!",
    "डॉक्टर ने कहा, आपको आराम चाहिए। मरीज़ बोला, पर मैं तो रोज़ ऑफ़िस में ही आराम करता हूँ!",
]


def _joke():
    """The punchline, then the pun in plain words."""

    if is_hindi():
        return random.choice(HINDI_JOKES)

    joke = random.choice(JOKES)
    explanation = EXPLANATIONS.get(joke)

    return f"{joke} {explanation}" if explanation else joke


def handle(text, raw=None):

    text = text.strip()

    if not text:
        return None

    # --------------------------------------------------------
    # JOKES
    # --------------------------------------------------------

    if re.match(r"^(?:tell me |say )?(?:a |another )?joke$|make me laugh", text):
        return _joke()

    if text in ("another one", "one more", "another joke", "one more joke"):
        return _joke()

    # --------------------------------------------------------
    # COIN
    # --------------------------------------------------------

    if re.match(r"^(?:flip|toss)(?: a| the)? coin$", text):
        return random.choice([t("fun.heads"), t("fun.tails")])

    # --------------------------------------------------------
    # DICE
    # --------------------------------------------------------

    match = re.match(r"^roll (?:a |the )?(dice|die|dye)(?: (\d{1,2}) times)?$", text)

    if match:
        times = int(match.group(2) or 1)
        rolls = [str(random.randint(1, 6)) for _ in range(min(times, 10))]

        if len(rolls) == 1:
            return t("fun.die", n=rolls[0])
        return t("fun.rolled", rolls=", ".join(rolls))

    # --------------------------------------------------------
    # RANDOM NUMBER
    # --------------------------------------------------------

    match = re.match(
        r"^(?:pick|choose|give me)? ?(?:a |one )?(?:random )?number"
        r"(?: between (\d{1,6}) and (\d{1,6}))?$",
        text,
    )

    if match:
        low = int(match.group(1) or 1)
        high = int(match.group(2) or 100)

        if low > high:
            low, high = high, low

        return t("fun.number", n=random.randint(low, high))

    return None


def name():
    return "fun"
