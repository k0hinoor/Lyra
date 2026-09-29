"""
============================================================
 TESTS — lyra/skills/media.py
============================================================
"""

import pytest

from lyra import config
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
# HOW PEOPLE ACTUALLY SAY IT
# ------------------------------------------------------------
# The original failure: Lyra answered "right-click the sound icon"
# because the phrasing missed the skill and fell through to the brain.
# Every line below has to EXECUTE, not be explained.

@pytest.mark.parametrize("text", [
    "please increase the volume",
    "can you turn up the volume",
    "could you turn up the volume please",
    "turn up my volume",
    "raise the volume a bit",
    "make it louder",
    "louder please",
    "boost the volume",
    "crank up the volume",
    "turn the music up",
    "turn it up",
    "raise it",
    "push the volume up",
    "turn the volume all the way up",
])
def test_every_spoken_way_of_asking_for_louder_is_acted_on(volume, text):
    volume["level"] = 30

    reply = media.handle(text)

    assert reply is not None, "must be executed, never handed to the brain"
    assert volume["level"] > 30


@pytest.mark.parametrize("text", [
    "please turn down the volume",
    "can you make it quieter",
    "turn it down",
    "lower it",
    "turn the music down",
    "reduce the volume",
])
def test_every_spoken_way_of_asking_for_quieter_is_acted_on(volume, text):
    volume["level"] = 60

    reply = media.handle(text)

    assert reply is not None, "must be executed, never handed to the brain"
    assert volume["level"] < 60


@pytest.mark.parametrize("text", [
    "it's too quiet",
    "the sound is too low",
    "volume is too low",
    "i can't hear you",
    "i can't hear anything",
    "it's too loud",
    "the sound is too loud",
    "it's too dark",
    "it's too bright",
])
def test_complaints_are_fixed_not_explained(volume, text):
    volume["level"] = 40

    assert media.handle(text) is not None


@pytest.mark.parametrize("text, expected", [
    ("set the volume to sixty", 60),
    ("set the volume to forty five", 45),
    ("volume to 80", 80),
    ("increase the volume to 60", 60),
    ("turn the volume up to a hundred", 100),
    ("make volume 40", 40),
    ("full volume", 100),
    ("max volume", 100),
    ("half volume", 50),
])
def test_absolute_targets(volume, text, expected):
    assert media.handle(text) == f"Volume set to {expected} percent."
    assert volume["level"] == expected


@pytest.mark.parametrize("text, step", [
    ("volume up a bit", 5),
    ("turn the volume up slightly", 5),
    ("turn the volume up a lot", 25),
    ("turn it up by 5", 5),
    ("volume up 20", 20),
])
def test_step_size_follows_the_request(volume, text, step):
    volume["level"] = 40

    assert media.handle(text) == f"Volume set to {40 + step} percent."


@pytest.mark.parametrize("text", [
    "what's the volume",
    "how loud is it",
    "volume level",
    "check the volume",
    "current volume",
])
def test_asking_about_the_volume_reads_it_out(volume, text):
    volume["level"] = 33
    assert media.handle(text) == "Volume is at 33 percent."
    assert volume["level"] == 33, "asking must not change anything"


@pytest.mark.parametrize("text", ["mute the sound", "silence the audio", "mute my speaker",
                                  "turn off the sound"])
def test_mute_phrasings(volume, text):
    assert media.handle(text) == "Muted."
    assert volume["muted"] is True


def test_unmute_phrasings(volume, text="unmute the sound"):
    assert media.handle(text) == "Unmuted."
    assert volume["muted"] is False


def test_turning_it_up_while_muted_also_unmutes(volume):
    volume["level"] = 10
    volume["muted"] = True

    reply = media.handle("turn up the volume")

    assert "Unmuted" in reply
    assert volume["muted"] is False
    assert volume["level"] == 20


def test_volume_never_goes_past_the_configured_ceiling(volume, monkeypatch):
    monkeypatch.setattr(config, "MAX_VOLUME", 70)
    volume["level"] = 60

    assert media.handle("set volume to 100") == (
        "Volume set to 70 percent, that is the maximum."
    )
    assert volume["level"] == 70


def test_volume_failures_are_reported(monkeypatch, volume):
    def boom():
        raise RuntimeError("no audio device")

    monkeypatch.setattr(media, "_current_volume", boom)

    assert media.handle("volume") == "I couldn't read the volume."
    assert media.handle("volume up") == "I couldn't change the volume."


# ------------------------------------------------------------
# WHAT THE SKILL MUST NOT SWALLOW
# ------------------------------------------------------------
# A level command is a small, closed world. One word that does not
# belong means the text belongs to another skill (or to the brain).

@pytest.mark.parametrize("text", [
    "scroll down the screen",
    "zoom in",
    "print screen",
    "show desktop",
    "play music",
    "play music on spotify",
    "open sound settings",
    "open display settings",
    "open my music folder",
    "search for volume",
    "the battery is too low",
    "the room is too noisy",
    "it's too late",
    "silence the notification",
    "why can't i hear the birds",
    "what volume should i use",
    "dark mode",
    "power off",
    "tell me a joke",
])
def test_other_commands_are_left_to_their_own_skill(volume, text):
    assert media.handle(text) is None


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


# ------------------------------------------------------------
# BRIGHTNESS, SPOKEN LIKE PEOPLE SPEAK
# ------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("make the screen brighter", 60),
    ("increase the brightness", 60),
    ("it's too dark", 60),
    ("brightness up 20", 70),
    ("turn the brightness down", 40),
    ("it's too bright", 40),
    ("dim the screen", 40),
    ("set the brightness to eighty", 80),
])
def test_brightness_phrasings(brightness, text, expected):
    brightness.level = 50

    assert media.handle(text) == f"Brightness set to {expected} percent."
    assert brightness.level == expected


def test_brightness_can_be_asked_about(brightness):
    brightness.level = 35
    assert media.handle("how bright is the screen") == "Brightness is at 35 percent."


# ------------------------------------------------------------
# PLAYBACK
# ------------------------------------------------------------

@pytest.mark.parametrize("text, key, reply", [
    ("play", "playpause", "Playing."),
    ("play music", "playpause", "Playing."),
    ("pause", "playpause", "Paused."),
    ("stop the music", "playpause", "Paused."),
    ("skip to the next song", "nexttrack", "Next track."),
    ("next track", "nexttrack", "Next track."),
    ("previous track", "prevtrack", "Previous track."),
])
def test_more_playback_keys(autogui, text, key, reply):
    assert media.handle(text) == reply
    assert autogui.pressed(key)


# ------------------------------------------------------------
# FILLER ALONE IS NOT A COMMAND  (it used to mean "mute")
# ------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "you", "okay", "ok", "hmm", "um", "so", "hello", "hi", "hey", "please",
    "lyra", "hey lyra", "ok lyra", "right",
])
def test_filler_alone_never_mutes(text, volume):
    assert media._level_command(text) is None
    media.handle(text)
    assert volume["calls"] == []
    assert volume["muted"] is False


def test_a_real_mute_still_mutes(volume):
    media.handle("mute")
    assert volume["muted"] is True


# ------------------------------------------------------------
# BOTH PYCAW API SHAPES
# ------------------------------------------------------------

@pytest.fixture
def fake_pycaw(monkeypatch):
    """Minimal comtypes/pycaw names so _volume_interface can run anywhere."""
    import sys
    import types

    monkeypatch.setitem(sys.modules, "comtypes", types.SimpleNamespace(CoInitialize=lambda: None))
    monkeypatch.setattr(media, "IAudioEndpointVolume",
                        types.SimpleNamespace(_iid_="IID_IAudioEndpointVolume"), raising=False)
    monkeypatch.setattr(media, "CLSCTX_ALL", 23, raising=False)
    monkeypatch.setattr(media, "POINTER", lambda interface: ("POINTER", interface), raising=False)
    monkeypatch.setattr(media, "cast", lambda obj, pointer: ("cast", obj), raising=False)

    def use(device):
        monkeypatch.setattr(media, "AudioUtilities",
                            types.SimpleNamespace(GetSpeakers=lambda: device), raising=False)

    return use


def test_new_pycaw_audio_device_uses_its_endpoint_volume(fake_pycaw):
    # pycaw 20251023+: GetSpeakers() returns an AudioDevice wrapper with an
    # EndpointVolume property and NO Activate() ("'AudioDevice' object has
    # no attribute 'Activate'" on the owner's PC).
    endpoint = object()

    class AudioDevice:
        @property
        def EndpointVolume(self):
            return endpoint

    fake_pycaw(AudioDevice())
    assert media._volume_interface() is endpoint


def test_old_pycaw_raw_device_is_activated(fake_pycaw):
    activated = []

    class IMMDevice:
        def Activate(self, iid, context, params):
            activated.append((iid, context, params))
            return "interface"

    fake_pycaw(IMMDevice())
    assert media._volume_interface() == ("cast", "interface")
    assert activated == [("IID_IAudioEndpointVolume", 23, None)]


def test_a_com_error_inside_the_new_property_is_not_hidden(fake_pycaw):
    class AudioDevice:
        @property
        def EndpointVolume(self):
            raise OSError("no audio endpoint")

    fake_pycaw(AudioDevice())
    with pytest.raises(OSError):
        media._volume_interface()


# ------------------------------------------------------------
# FULL SCREEN IS NOT A BRIGHTNESS COMMAND
# ------------------------------------------------------------
# Bug: "full screen" was parsed as level "full" of subject "screen"
# and set the brightness to 100%.

@pytest.mark.parametrize("text", [
    "full screen",
    "fullscreen",
    "make it full screen",
    "make it fullscreen",
    "go full screen",
    "exit full screen",
])
def test_full_screen_never_touches_brightness(brightness, text):
    brightness.level = 42

    assert media.handle(text) is None
    assert brightness.level == 42, "brightness must be untouched"
    assert brightness.calls == []


def test_full_volume_is_still_a_real_command(volume):
    assert media.handle("full volume") == "Volume set to 100 percent."
