"""
============================================================
 SKILL: FUN
============================================================
 Jokes, coin flips, dice, random numbers. All offline.
============================================================
"""

import random
import re

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


def handle(text, raw=None):

    text = text.strip()

    if not text:
        return None

    # --------------------------------------------------------
    # JOKES
    # --------------------------------------------------------

    if re.match(r"^(?:tell me |say )?(?:a |another )?joke$|make me laugh", text):
        return random.choice(JOKES)

    if text in ("another one", "one more", "another joke", "one more joke"):
        return random.choice(JOKES)

    # --------------------------------------------------------
    # COIN
    # --------------------------------------------------------

    if re.match(r"^(?:flip|toss)(?: a| the)? coin$", text):
        return random.choice(["Heads.", "Tails."])

    # --------------------------------------------------------
    # DICE
    # --------------------------------------------------------

    match = re.match(r"^roll (?:a |the )?(dice|die|dye)(?: (\d{1,2}) times)?$", text)

    if match:
        times = int(match.group(2) or 1)
        rolls = [str(random.randint(1, 6)) for _ in range(min(times, 10))]

        if len(rolls) == 1:
            return f"It's a {rolls[0]}."
        return "You rolled " + ", ".join(rolls) + "."

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

        return f"Your number is {random.randint(low, high)}."

    return None


def name():
    return "fun"
