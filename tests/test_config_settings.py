"""
============================================================
 TESTS — settings parsing helpers in lyra/config.py
============================================================
 (VOICE_SPEED clamping and BROWSER normalisation; the JSON/env
 plumbing reads these same helpers.)
============================================================
"""

import json
import os
import subprocess
import sys

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


# ------------------------------------------------------------
# CALIBRATED ENERGY THRESHOLD
# ------------------------------------------------------------

def test_the_default_energy_cap_stops_a_noisy_calibration_from_muting_the_mic():
    assert config.ENERGY_THRESHOLD_MAX == 1000
    assert config.clamp_energy_threshold(5000) == 1000


@pytest.mark.parametrize("value, expected", [
    (205.0, 205.0),          # the threshold a normal room calibrates
    ("800", 800.0),
    (1000, 1000.0),
    (5000, 1000.0),          # noisy room -> capped
    (0, 1.0),                # zero floor would make room noise "speech"
    (-3, 1.0),
])
def test_calibrated_thresholds_are_clamped(value, expected):
    assert config.clamp_energy_threshold(value) == expected


def test_the_cap_follows_a_configured_ceiling(monkeypatch):
    monkeypatch.setattr(config, "ENERGY_THRESHOLD_MAX", 400.0)
    assert config.clamp_energy_threshold(5000) == 400.0
    assert config.clamp_energy_threshold(250) == 250.0


@pytest.mark.parametrize("value", ["loud", None, "", "n/a"])
def test_a_non_numeric_calibration_is_rejected(value):
    assert config.clamp_energy_threshold(value) is None


def test_the_cap_can_be_raised_from_settings():
    assert config._parse_setting("ENERGY_THRESHOLD_MAX", "2500") == 2500.0
    assert config._parse_setting("ENERGY_THRESHOLD_MAX", 250) == 250.0


@pytest.mark.parametrize("value", [0, -10, "loud", None])
def test_an_unusable_energy_cap_is_rejected(value):
    with pytest.raises(ValueError):
        config._parse_setting("ENERGY_THRESHOLD_MAX", value)


# ------------------------------------------------------------
# INPUT DEVICE / WAKE DEBUG
# ------------------------------------------------------------

def test_the_default_input_device_is_the_windows_default():
    assert config.INPUT_DEVICE is None


@pytest.mark.parametrize("value, expected", [
    (None, None), ("", None), ("  ", None),          # default device
    (1, 1), ("1", 1), (5, 5), (" 7 ", 7),            # explicit index
])
def test_input_device_parses_like_the_output_device(value, expected):
    assert config._parse_setting("INPUT_DEVICE", value) == expected
    assert config._parse_setting("OUTPUT_DEVICE", value) == expected


@pytest.mark.parametrize("value", ["usb", "Microphone (USB Audio Device)", 1.5])
def test_an_invalid_input_device_is_rejected(value):
    with pytest.raises(ValueError):
        config._parse_setting("INPUT_DEVICE", value)


def test_wake_debug_is_off_by_default():
    assert config.WAKE_DEBUG is False


@pytest.mark.parametrize("value, expected", [
    (True, True), (False, False), ("true", True), ("false", False),
])
def test_wake_debug_setting_is_boolean(value, expected):
    assert config._parse_setting("WAKE_DEBUG", value) is expected


def test_invalid_wake_debug_setting_is_rejected():
    with pytest.raises(ValueError):
        config._parse_setting("WAKE_DEBUG", "sometimes")


def test_new_settings_reach_the_runtime_from_json_and_environment(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({
        "INPUT_DEVICE": 1, "WAKE_DEBUG": False, "ENERGY_THRESHOLD_MAX": 250,
    }))
    environment = {key: value for key, value in os.environ.items() if not key.startswith("LYRA_")}
    environment.update(
        LYRA_DATA_DIR=str(tmp_path),
        LYRA_INPUT_DEVICE="2",
        LYRA_WAKE_DEBUG="true",
        LYRA_ENERGY_THRESHOLD_MAX="800",
    )
    result = subprocess.run([
        sys.executable, "-c",
        "from lyra import config; import json; print(json.dumps(["
        "config.INPUT_DEVICE, config.WAKE_DEBUG, config.ENERGY_THRESHOLD_MAX]))",
    ], capture_output=True, text=True, env=environment, check=True)

    assert json.loads(result.stdout) == [2, True, 800.0]


def test_new_settings_work_from_json_alone(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({
        "INPUT_DEVICE": 3, "WAKE_DEBUG": "true", "ENERGY_THRESHOLD_MAX": 250,
    }))
    environment = {key: value for key, value in os.environ.items() if not key.startswith("LYRA_")}
    environment["LYRA_DATA_DIR"] = str(tmp_path)
    result = subprocess.run([
        sys.executable, "-c",
        "from lyra import config; import json; print(json.dumps(["
        "config.INPUT_DEVICE, config.WAKE_DEBUG, config.ENERGY_THRESHOLD_MAX]))",
    ], capture_output=True, text=True, env=environment, check=True)

    assert json.loads(result.stdout) == [3, True, 250.0]


def test_the_settings_example_documents_the_new_keys():
    example = json.loads(
        (config.BASE_DIR / "config" / "settings.example.json").read_text(encoding="utf-8")
    )
    assert example["INPUT_DEVICE"] is None
    assert example["WAKE_DEBUG"] is False
    assert example["ENERGY_THRESHOLD_MAX"] == 1000
