"""
============================================================
 TESTS — lyra/skills/fun.py
============================================================
"""

import re

import pytest

from lyra.skills import fun


# ------------------------------------------------------------
# JOKES
# ------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "tell me a joke",
    "say a joke",
    "another joke",
    "make me laugh",
    "joke",
])
def test_joke_requests_are_handled(text):
    assert fun.handle(text) in fun.JOKES


def test_joke_never_returns_an_unknown_question():
    assert fun.handle("what is the meaning of life") is None


# ------------------------------------------------------------
# COIN
# ------------------------------------------------------------

@pytest.mark.parametrize("text", ["flip a coin", "toss a coin", "flip coin", "toss the coin"])
def test_coin_flip(text):
    assert fun.handle(text) in ("Heads.", "Tails.")


# ------------------------------------------------------------
# DICE
# ------------------------------------------------------------

@pytest.mark.parametrize("text", ["roll a dice", "roll the die", "roll dice"])
def test_single_die(text):
    assert re.match(r"^It's a [1-6]\.$", fun.handle(text))


def test_multiple_dice():
    reply = fun.handle("roll a dice 5 times")
    assert reply.startswith("You rolled ")
    assert len(re.findall(r"\b[1-6]\b", reply)) == 5


def test_dice_roll_count_is_capped():
    reply = fun.handle("roll a dice 50 times")
    assert len(re.findall(r"\b[1-6]\b", reply)) == 10


# ------------------------------------------------------------
# RANDOM NUMBER
# ------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "pick a number between 1 and 100",
    "give me a random number",
    "number",
    "choose a number",
])
def test_random_number_request(text):
    assert re.match(r"^Your number is \d+\.$", fun.handle(text))


def test_random_number_stays_in_range(monkeypatch):
    monkeypatch.setattr(fun.random, "randint", lambda low, high: low)
    assert fun.handle("number between 5 and 9") == "Your number is 5."


def test_random_number_swaps_reversed_bounds(monkeypatch):
    monkeypatch.setattr(fun.random, "randint", lambda low, high: high)
    assert fun.handle("number between 90 and 10") == "Your number is 90."


def test_fun_ignores_empty_input():
    assert fun.handle("") is None
    assert fun.handle("   ") is None
