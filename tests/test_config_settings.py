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
