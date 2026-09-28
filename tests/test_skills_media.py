"""
============================================================
 TESTS — lyra/skills/media.py
============================================================
"""

import pytest

from lyra.skills import media


# ------------------------------------------------------------
# VOLUME
# ------------------------------------------------------------

def test_read_volume(volume):
    volume["level"] = 42
    assert media.handle("volume") == "Volume is at 42 percent."


def test_set_absolute_volume(volume):
    assert media.handle("set volume to 70") == "Volume set to 70 percent."
    assert volume["level"] == 70


def test_set_volume_percent_suffix(volume):
    assert media.handle("set volume to 25 percent") == "Volume set to 25 percent."
    assert volume["level"] == 25


def test_volume_up(volume):
    volume["level"] = 30
    assert media.handle("volume up") == "Volume set to 40 percent."


def test_volume_down_with_a_step(volume):
    volume["level"] = 50
    assert media.handle("volume down 20") == "Volume set to 30 percent."


@pytest.mark.parametrize("text", ["increase the volume", "turn the volume up", "volume louder"])
def test_volume_up_phrasings_use_a_default_step(volume, text):
    volume["level"] = 30
    assert media.handle(text) == "Volume set to 40 percent."
    assert volume["level"] == 40


def test_volume_up_with_an_explicit_step(volume):
    volume["level"] = 30
    assert media.handle("raise volume 5") == "Volume set to 35 percent."


@pytest.mark.parametrize("text", ["decrease the volume", "lower volume"])
def test_volume_down_phrasings(volume, text):
    volume["level"] = 30
    assert media.handle(text) == "Volume set to 20 percent."


def test_volume_is_clamped_to_100(volume):
    volume["level"] = 95
    assert media.handle("volume up") == "Volume set to 100 percent."


def test_volume_is_clamped_to_zero(volume):
    volume["level"] = 5
    assert media.handle("volume down") == "Volume set to 0 percent."


def test_mute_and_unmute(volume):
    assert media.handle("mute") == "Muted."
    assert volume["muted"] is True

    assert media.handle("unmute") == "Unmuted."
    assert volume["muted"] is False


def test_mute_volume_phrasing(volume):
    assert media.handle("mute volume") == "Muted."
    assert volume["muted"] is True


def test_volume_without_pycaw_reports_it(monkeypatch):
    monkeypatch.setattr(media, "_AUDIO_OK", False)
    assert "pycaw" in media.handle("volume")


# ------------------------------------------------------------
# BRIGHTNESS
# ------------------------------------------------------------

def test_read_brightness(brightness):
    brightness.level = 65
    assert media.handle("brightness") == "Brightness is at 65 percent."


def test_set_brightness(brightness):
    assert media.handle("set brightness to 80") == "Brightness set to 80 percent."
    assert brightness.level == 80


def test_brightness_up_and_down(brightness):
    assert media.handle("brightness up") == "Brightness set to 60 percent."
    assert media.handle("brightness down 20") == "Brightness set to 40 percent."


def test_brightness_is_clamped(brightness):
    brightness.level = 95
    assert media.handle("brightness up") == "Brightness set to 100 percent."
    brightness.level = 3
    assert media.handle("brightness down") == "Brightness set to 0 percent."


def test_brightness_failure_is_reported(monkeypatch, brightness):
    def boom():
        raise RuntimeError("no monitor")

    monkeypatch.setattr(brightness, "get_brightness", boom)
    assert media.handle("brightness") == "I couldn't read the brightness."


def test_brightness_without_the_package_reports_it(monkeypatch):
    monkeypatch.setattr(media, "_BRIGHTNESS_OK", False)
    assert "screen-brightness-control" in media.handle("brightness")


# ------------------------------------------------------------
# PLAYBACK KEYS
# ------------------------------------------------------------

@pytest.mark.parametrize("text, key, reply", [
    ("play", "playpause", "Playing."),
    ("play music", "playpause", "Playing."),
    ("pause", "playpause", "Paused."),
    ("next track", "nexttrack", "Next track."),
    ("previous track", "prevtrack", "Previous track."),
])
def test_playback_keys(autogui, text, key, reply):
    assert media.handle(text) == reply
    assert autogui.pressed(key)


# ------------------------------------------------------------
# NOT MINE
# ------------------------------------------------------------

@pytest.mark.parametrize("text", ["open notepad", "what time is it", ""])
def test_other_commands_are_left_alone(autogui, volume, brightness, text):
    assert media.handle(text) is None
