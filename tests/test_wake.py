from lyra.utils import normalize, strip_wake_word


def test_wake_name_variants_are_accepted_only_in_wake_position():
    for name in ("lyra", "laira", "lira", "laura", "later", "leyra", "leira", "lyrah", "bobby"):
        matched, remainder = strip_wake_word(normalize(f"Hey {name}, open notepad"))
        assert matched, name
        assert remainder == "open notepad"


def test_common_background_phrases_do_not_wake_lyra():
    for phrase in ("see you later", "okay", "hip hop", "hey there", "bobby was here"):
        assert strip_wake_word(normalize(phrase))[0] is False


def test_canonical_name_can_be_used_without_greeting():
    assert strip_wake_word("lyra what time is it") == (True, "what time is it")
    assert strip_wake_word("later what time is it")[0] is False
