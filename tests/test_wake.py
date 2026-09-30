from lyra import config
from lyra.utils import normalize, strip_wake_word


# ------------------------------------------------------------
# POSITIVE: a greeting plus a mis-heard name
# ------------------------------------------------------------

WAKE_NAMES = (
    "lyra", "laira", "lira", "laura", "later", "leyra", "leira", "lyrah", "bobby",
)


def test_wake_name_variants_are_accepted_only_in_wake_position():
    for name in WAKE_NAMES:
        matched, remainder = strip_wake_word(normalize(f"Hey {name}, open notepad"))
        assert matched, name
        assert remainder == "open notepad"


def test_the_reported_wake_mishearings_are_accepted_after_a_greeting():
    for name in ("lara", "leera", "lyre", "lyrics", "hilera"):
        matched, remainder = strip_wake_word(normalize(f"Hey {name}, open notepad"))
        assert matched, name
        assert remainder == "open notepad"


def test_prefix_glued_to_the_name_still_wakes_lyra():
    for phrase in ("heylyra", "hilyra", "oklyra", "hellolyra", "yolyra"):
        matched, remainder = strip_wake_word(normalize(f"{phrase} open notepad"))
        assert matched, phrase
        assert remainder == "open notepad"


def test_the_reported_phrase_forms_wake_lyra():
    for phrase in ("hailyra", "a lyra", "hey laura", "hi lyra", "hello lyra", "ok lyra"):
        matched, remainder = strip_wake_word(normalize(f"{phrase} open notepad"))
        assert matched, phrase
        assert remainder == "open notepad"


def test_a_mishearing_is_accepted_as_a_whole_utterance():
    assert strip_wake_word(normalize("hey lara")) == (True, "")
    assert strip_wake_word(normalize("a lyra")) == (True, "")
    assert strip_wake_word(normalize("hailyra")) == (True, "")


def test_unseen_spellings_are_still_covered_by_the_fuzzy_candidate_list():
    for token in ("layra", "liraa", "lyrra"):        # not explicit aliases
        assert token not in config.WAKE_ALIASES
        assert strip_wake_word(normalize(f"hey {token} open notepad")) == (True, "open notepad")


# ------------------------------------------------------------
# NEGATIVE: ordinary speech must never wake LYRA
# ------------------------------------------------------------

def test_common_background_phrases_do_not_wake_lyra():
    for phrase in ("see you later", "okay", "hip hop", "hey there", "bobby was here"):
        assert strip_wake_word(normalize(phrase))[0] is False


def test_words_that_merely_start_with_a_greeting_do_not_wake_lyra():
    for phrase in ("hillary clinton", "higher", "hiking", "height", "hint", "hips", "yoga"):
        assert strip_wake_word(normalize(phrase))[0] is False, phrase


def test_a_noisy_word_after_a_greeting_does_not_wake_lyra():
    # "there" and "man" must stay outside the fuzzy distance of every alias.
    for phrase in ("hey there", "hello there", "hey man", "hey you", "hi google"):
        assert strip_wake_word(normalize(phrase))[0] is False, phrase


def test_mishearings_that_are_ordinary_words_need_the_greeting():
    # "later", "lyrics" and "lyre" are real English words: bare they stay
    # commands/background speech, in wake position they wake LYRA.
    for phrase in ("later what time is it", "the lyrics are wrong", "play the lyrics",
                   "lyre bird song", "lara croft is a game"):
        assert strip_wake_word(normalize(phrase))[0] is False, phrase


def test_a_greeting_inside_a_sentence_is_not_a_wake_word():
    for phrase in ("i said hey lyra yesterday", "call me later", "tell her hi lyra"):
        assert strip_wake_word(normalize(phrase))[0] is False, phrase


def test_a_prefix_without_a_name_does_not_wake_lyra():
    for phrase in ("hey", "hello", "hi", "okay", "hai"):
        matched, remainder = strip_wake_word(normalize(phrase))
        assert matched is False
        assert remainder == normalize(phrase)


# ------------------------------------------------------------
# UNCHANGED CONTRACT
# ------------------------------------------------------------

def test_canonical_name_can_be_used_without_greeting():
    assert strip_wake_word("lyra what time is it") == (True, "what time is it")
    assert strip_wake_word("later what time is it")[0] is False


def test_native_script_names_keep_working_bare_and_after_a_prefix():
    assert strip_wake_word(normalize("लायरा मुझे हिंदी में जवाब दो")) == (True, "मुझे हिंदी में जवाब दो")
    assert strip_wake_word(normalize("हे लायरा मुझे हिंदी में जवाब दो")) == (True, "मुझे हिंदी में जवाब दो")
