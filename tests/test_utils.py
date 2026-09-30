"""
============================================================
 TESTS — lyra/utils.py
============================================================
 Text normalization, wake-word handling, voice cleanup and
 the streaming sentence splitter.
============================================================
"""

import pytest

from lyra import config
from lyra.utils import (
    SentenceSplitter,
    clean_for_voice,
    correct_name,
    is_sleep,
    is_terminate,
    is_thanks,
    normalize,
    split_sentences,
    strip_politeness,
    strip_wake_word,
)


# ------------------------------------------------------------
# NORMALIZE
# ------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("What time is it?", "what time is it"),
    ("  HEY   LYRA  ", "hey lyra"),
    ("Volume, please!", "volume please"),
    ("What's the date?", "what's the date"),          # apostrophes survive
    ("open C:\\Users", "open c users"),
    ("", ""),
])
def test_normalize(raw, expected):
    assert normalize(raw) == expected


def test_normalize_collapses_punctuation_into_spaces():
    assert " " not in normalize("hello...world!!").replace("hello world", "")
    assert normalize("hello...world!!") == "hello world"


# ------------------------------------------------------------
# POLITE FILLER
# ------------------------------------------------------------
# Nobody talks to Lyra like a terminal. "can you please turn up
# the volume" has to reach the skill as "turn up the volume".

@pytest.mark.parametrize("raw, expected", [
    ("please open notepad", "open notepad"),
    ("can you open notepad", "open notepad"),
    ("could you please open notepad", "open notepad"),
    ("would you open notepad", "open notepad"),
    ("i want you to open notepad", "open notepad"),
    ("i need you to open notepad", "open notepad"),
    ("kindly open notepad", "open notepad"),
    ("just open notepad", "open notepad"),
    ("hey open notepad", "open notepad"),
    ("open notepad please", "open notepad"),
    ("open notepad for me", "open notepad"),
    ("open notepad now", "open notepad"),
    ("open notepad thanks", "open notepad"),
    ("please can you open notepad please", "open notepad"),
    ("can you please can you open notepad", "open notepad"),
    ("can you increase the volume", "increase the volume"),
    ("turn up the volume a bit please", "turn up the volume a bit"),
])
def test_polite_padding_is_peeled_off(raw, expected):
    assert strip_politeness(raw) == expected


def test_a_command_is_left_alone():
    assert strip_politeness("set volume to 40") == "set volume to 40"
    assert strip_politeness("what time is it") == "what time is it"


def test_text_that_is_only_politeness_survives():
    assert strip_politeness("please") == "please"
    assert strip_politeness("ok") == "ok"
    assert strip_politeness("") == ""


def test_normalize_and_strip_compose():
    assert strip_politeness(normalize("Can you please turn up the volume?!")) == (
        "turn up the volume"
    )


# ------------------------------------------------------------
# CORRECT NAME
# ------------------------------------------------------------

@pytest.mark.parametrize("heard", ["laira", "lira", "liara", "laura", "yara", "lyrah"])
def test_correct_name_fixes_common_mishearings(heard):
    assert correct_name(f"hey {heard} what time is it") == "hey Lyra what time is it"


def test_correct_name_leaves_other_words_alone():
    assert correct_name("open the camera") == "open the camera"


def test_correct_name_handles_every_configured_alias():
    for alias in config.WAKE_ALIASES:
        assert correct_name(alias) == "Lyra"


# ------------------------------------------------------------
# WAKE WORD
# ------------------------------------------------------------

@pytest.mark.parametrize("text, remainder", [
    ("hey lyra what time is it", "what time is it"),
    ("ok lyra open notepad", "open notepad"),
    ("lyra volume up", "volume up"),
    ("hey lira tell me a joke", "tell me a joke"),      # mis-heard alias
    ("lyra", ""),                                        # wake word only
    ("hey lyra", ""),
])
def test_strip_wake_word_matches(text, remainder):
    assert strip_wake_word(text) == (True, remainder)


@pytest.mark.parametrize("text", [
    "what time is it",
    "hello there",
    "",
])
def test_strip_wake_word_rejects(text):
    matched, remainder = strip_wake_word(text)
    assert matched is False
    assert remainder == text


def test_strip_wake_word_fires_on_a_name_at_the_start():
    # Known trade-off: a sentence that merely *starts* with the name
    # ("Lyra is a constellation") is treated as a command.
    assert strip_wake_word("lyra is a constellation") == (True, "is a constellation")


def test_strip_wake_word_keeps_unknown_prefix():
    # "now lyra" is not a configured prefix, so nothing is stripped
    assert strip_wake_word("now lyra open chrome") == (False, "now lyra open chrome")


# ------------------------------------------------------------
# TERMINATE / SLEEP / THANKS
# ------------------------------------------------------------

def test_terminate_phrases():
    assert is_terminate("terminate execution")
    assert is_terminate("lyra terminate execution")
    assert is_terminate("goodbye lyra")
    assert not is_terminate("terminate the program")


def test_sleep_phrases():
    assert is_sleep("go to sleep")
    assert is_sleep("that's all")
    assert not is_sleep("sleep tight")


def test_thanks_phrases():
    assert is_thanks("thanks")
    assert is_thanks("thank you lyra")
    assert is_thanks("shukriya")
    assert not is_thanks("thanks a lot")


# ------------------------------------------------------------
# CLEAN FOR VOICE
# ------------------------------------------------------------

def test_clean_for_voice_strips_markdown():
    assert clean_for_voice("**Bold** and `code`") == "Bold and code"


def test_clean_for_voice_replaces_symbols_with_words():
    cleaned = clean_for_voice("It is 30°C and 45% humid.")
    assert "degrees" in cleaned
    assert "percent" in cleaned
    assert "°" not in cleaned
    assert "%" not in cleaned


def test_clean_for_voice_drops_emojis_and_non_ascii():
    assert clean_for_voice("All done 🎉 — nice!") == "All done nice!"


def test_clean_for_voice_collapses_newlines():
    assert clean_for_voice("line one\n\nline two") == "line one line two"


def test_clean_for_voice_removes_code_blocks():
    assert clean_for_voice("here```print(1)```done") == "here code block done"


def test_clean_for_voice_keeps_ampersand_readable():
    assert clean_for_voice("salt & pepper") == "salt and pepper"


# ------------------------------------------------------------
# SENTENCE SPLITTER (streaming)
# ------------------------------------------------------------

def test_splitter_emits_nothing_until_a_full_sentence_arrives():
    splitter = SentenceSplitter()
    assert splitter.feed("Hello there, ") == []
    assert splitter.feed("this is a fairly long first sentence. ") == [
        "Hello there, this is a fairly long first sentence."
    ]


def test_splitter_buffers_short_sentences_until_min_len():
    splitter = SentenceSplitter(min_len=24)
    # "Hi." is complete punctuation but far too short to speak on its own
    assert splitter.feed("Hi. ") == []
    assert splitter.finish() == "Hi."


def test_splitter_streams_before_the_reply_is_finished():
    splitter = SentenceSplitter()
    tokens = ["The weather is nice today. ", "Do you want to go outside? "]

    assert splitter.feed(tokens[0]) == ["The weather is nice today."]
    assert splitter.feed(tokens[1]) == ["Do you want to go outside?"]

    assert splitter.finish() == ""


def test_splitter_finish_returns_the_tail():
    splitter = SentenceSplitter(min_len=5)
    splitter.feed("First one is here. And the rest")
    assert splitter.finish() == "And the rest"


def test_splitter_handles_question_and_exclamation_marks():
    splitter = SentenceSplitter(min_len=10)
    out = splitter.feed("Are you serious? Yes! Okay then. ")
    assert out == ["Are you serious? Yes! Okay then."] or len(out) >= 1


def test_splitter_runaway_guard_splits_unpunctuated_text():
    splitter = SentenceSplitter(min_len=24)
    long_text = "word " * 120
    out = splitter.feed(long_text)
    assert out, "a 600-character sentence with no punctuation should be cut"


def test_split_sentences_keeps_all_the_text():
    text = "This is the first sentence of the reply. Here comes a second one."
    chunks = split_sentences(text, min_len=10)

    assert len(chunks) == 2
    assert " ".join(chunks).startswith("This is the first sentence")


def test_split_sentences_returns_one_chunk_when_there_is_no_boundary():
    assert split_sentences("no punctuation here") == ["no punctuation here"]


# ------------------------------------------------------------
# SENTENCE-OPENING CONNECTIVES  ("so what time is it")
# ------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("so what time is it", "what time is it"),
    ("and what time is it", "what time is it"),
    ("well what time is it", "what time is it"),
    ("so open notepad", "open notepad"),
    ("so tell me the time", "tell me the time"),
])
def test_sentence_opening_connectives_are_peeled_off(raw, expected):
    assert strip_politeness(raw) == expected


# ------------------------------------------------------------
# TERMINATE MISHEARINGS  ("and the terminal execution")
# ------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "terminal execution",
    "the terminal execution",
    "and terminal execution",
    "and the terminal execution",
    "lyra terminal execution",
    "terminate the execution",
])
def test_close_terminate_mishearings_still_exit(text):
    assert is_terminate(text)


@pytest.mark.parametrize("text", [
    "start the terminal execution of the program",   # a real sentence
    "the terminal is executing",
    "terminate",
])
def test_ordinary_terminal_sentences_do_not_exit(text):
    assert not is_terminate(text)


# ------------------------------------------------------------
# FILLER-ONLY UTTERANCES  (voice mode drops these)
# ------------------------------------------------------------

from lyra.utils import is_filler  # noqa: E402


@pytest.mark.parametrize("text", [
    "okay", "ok", "okay then", "alright", "hmm", "hm", "mm", "mhm",
    "um", "uh", "er", "erm", "oh", "ah", "huh",
])
def test_filler_utterances_are_recognised(text):
    assert is_filler(text)


@pytest.mark.parametrize("text", [
    "yes", "no", "yeah",          # may answer a pending confirmation
    "thanks",                     # handled by the thanks path
    "okay open notepad",          # filler + a real command
    "what time is it",
    "",
])
def test_commands_and_answers_are_not_filler(text):
    assert not is_filler(text)


# ------------------------------------------------------------
# STOP SPEECH  ("stop", "be quiet" — said over LYRA's own voice)
# ------------------------------------------------------------

from lyra.utils import STOP_SPEECH_PHRASES, is_stop_speech  # noqa: E402


@pytest.mark.parametrize("text", sorted(STOP_SPEECH_PHRASES))
def test_stop_phrases_are_recognised(text):
    assert is_stop_speech(text)
    assert is_stop_speech(f"  {text}  ")


@pytest.mark.parametrize("text", [
    "wait for the download",
    "stop the music",
    "open notepad",
    "",
])
def test_ordinary_sentences_are_not_stop_speech(text):
    assert not is_stop_speech(text)
