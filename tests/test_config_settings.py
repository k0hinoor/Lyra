"""
============================================================
 TESTS — settings parsing helpers in lyra/config.py
============================================================
 (VOICE_SPEED clamping and BROWSER normalisation; the JSON/env
 plumbing reads these same helpers.)
============================================================
"""

import pytest

from lyra import config


# ------------------------------------------------------------
# VOICE SPEED
# ------------------------------------------------------------

def test_default_voice_speed_is_a_little_faster():
    assert config.VOICE_SPEED == 1.15


@pytest.mark.parametrize("value, expected", [
    (1.0, 1.0),
    ("1.2", 1.2),
    (1.15, 1.15),
    (0.8, 0.8),
    (1.5, 1.5),
])
def test_voice_speed_values_inside_the_range_pass(value, expected):
    assert config.clamp_voice_speed(value) == expected


@pytest.mark.parametrize("value, expected", [
    (0.1, 0.8),          # too slow -> clamped up
    (0.0, 0.8),
    (-1, 0.8),
    (3.0, 1.5),          # too fast -> clamped down
    (99, 1.5),
    ("5", 1.5),
])
def test_voice_speed_is_clamped(value, expected):
    assert config.clamp_voice_speed(value) == expected


@pytest.mark.parametrize("value", ["fast", None, "", "n/a"])
def test_non_numeric_voice_speed_is_rejected(value):
    assert config.clamp_voice_speed(value) is None


# ------------------------------------------------------------
# BROWSER
# ------------------------------------------------------------

def test_default_browser_is_the_windows_default():
    assert config.BROWSER == ""


@pytest.mark.parametrize("value, expected", [
    ("brave", "brave"),
    ("Brave", "brave"),
    ("chrome", "chrome"),
    ("Google Chrome", "chrome"),
    ("edge", "edge"),
    ("Microsoft Edge", "edge"),
    ("firefox", "firefox"),
    ("Mozilla Firefox", "firefox"),
    ("", ""),                       # empty = system default
    ("  ", ""),
])
def test_browser_names_are_normalised(value, expected):
    assert config.normalize_browser_name(value) == expected


@pytest.mark.parametrize("value", ["netscape", "safari", "internet explorer", "12"])
def test_unknown_browsers_are_rejected(value):
    assert config.normalize_browser_name(value) is None


# ------------------------------------------------------------
# BARGE-IN ENERGY MULTIPLIER
# ------------------------------------------------------------

def test_the_default_barge_in_threshold_is_twice_the_room_noise():
    assert config.INTERRUPT_ENERGY_MULTIPLIER == 2.0


@pytest.mark.parametrize("value, expected", [
    (1.0, 1.0),
    (2, 2.0),
    ("3.5", 3.5),
    (10, 10.0),
])
def test_barge_in_multipliers_inside_the_range_pass(value, expected):
    assert config.clamp_interrupt_multiplier(value) == expected


@pytest.mark.parametrize("value, expected", [
    (0.5, 1.0),          # at/below the floor -> never interrupt
    (0, 1.0),
    (-4, 1.0),
    (99, 10.0),          # above the ceiling -> a cough would interrupt
    ("50", 10.0),
])
def test_barge_in_multiplier_is_clamped(value, expected):
    assert config.clamp_interrupt_multiplier(value) == expected


@pytest.mark.parametrize("value", ["loud", None, "", "n/a"])
def test_non_numeric_barge_in_multiplier_is_rejected(value):
    assert config.clamp_interrupt_multiplier(value) is None


def test_the_barge_in_timings_are_usable():
    assert 0 < config.INTERRUPT_MIN_VOICE_SECONDS <= 1
    assert config.INTERRUPT_SILENCE_SECONDS > config.INTERRUPT_MIN_VOICE_SECONDS
    assert 1 <= config.INTERRUPT_PHRASE_LIMIT <= 30
    assert config.INTERRUPT_ECHO_WINDOW_SECONDS >= config.INTERRUPT_PHRASE_LIMIT


# ------------------------------------------------------------
# WHISPER HOTWORDS
# ------------------------------------------------------------

@pytest.mark.parametrize("word", [
    "Lyra", "Brave", "Chrome", "YouTube", "Notepad", "terminate execution",
])
def test_the_vocabulary_hotwords_are_configured(word):
    assert word in config.WHISPER_HOTWORDS


# ------------------------------------------------------------
# DEFAULT VOICE
# ------------------------------------------------------------

def test_default_voice_model_is_lessac():
    assert config.VOICE_MODEL == "en_US-lessac-medium"


# ------------------------------------------------------------
# MULTILINGUAL SETTINGS
# ------------------------------------------------------------

@pytest.mark.parametrize("value, expected", [
    ("auto", "auto"), ("HI", "hi"), ("Hindi", "hi"), ("en", "en"), ("English", "en"),
    ("klingon", None), (None, None), ("", None),
])
def test_whisper_language_settings_are_normalized(value, expected):
    assert config.normalize_whisper_language(value) == expected


@pytest.mark.parametrize("value, expected", [
    (True, True), (False, False), ("true", True), ("false", False),
    ("1", True), ("0", False), ("yes please", None), (None, None),
])
def test_auto_memory_setting_uses_a_real_boolean(value, expected):
    assert config.parse_boolean(value) is expected


@pytest.mark.parametrize("setting, value", [
    ("HINDI_VOICE_MODEL", "en_US-lessac-medium"),
    ("VOICE_MODEL", "hi_IN-pratham-medium"),
    ("HINDI_VOICE_MODEL", "../hi_IN-pratham-medium"),
    ("WHISPER_LANGUAGE", "es"),
    ("AUTO_REMEMBER_PREFERENCES", "sometimes"),
])
def test_invalid_bilingual_settings_are_rejected(setting, value):
    with pytest.raises(ValueError):
        config._parse_setting(setting, value)


def test_defaults_support_english_and_hindi_without_english_only_whisper():
    assert config.WHISPER_MODEL == "base"
    assert config.WHISPER_LANGUAGE == "auto"
    assert config.HINDI_VOICE_MODEL == "hi_IN-priyamvada-medium"
    assert config.AUTO_REMEMBER_PREFERENCES is True


@pytest.mark.parametrize("value, expected", [(1, 1), ("3", 3), (5, 5)])
def test_whisper_beam_size_can_be_tuned_for_cpu_latency(value, expected):
    assert config._parse_setting("WHISPER_BEAM", value) == expected


@pytest.mark.parametrize("value", [0, 6, "fast"])
def test_invalid_whisper_beam_sizes_are_rejected(value):
    with pytest.raises(ValueError):
        config._parse_setting("WHISPER_BEAM", value)
