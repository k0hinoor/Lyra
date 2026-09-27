"""
============================================================
 SKILL: MEDIA
============================================================
 Volume, mute, brightness and media playback keys.
============================================================
"""

import re

try:
    import pyautogui
    pyautogui.PAUSE = 0
    _PYAUTOGUI_OK = True
except Exception:
    _PYAUTOGUI_OK = False

try:
    import screen_brightness_control as sbc
    _BRIGHTNESS_OK = True
except Exception:
    _BRIGHTNESS_OK = False

_AUDIO_OK = False

try:
    from ctypes import POINTER, cast

    from comtypes import CLSCTX_ALL

    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    _AUDIO_OK = True
except Exception:
    pass


# ------------------------------------------------------------
# VOLUME INTERFACE
# ------------------------------------------------------------

def _volume_interface():

    from comtypes import CoInitialize

    try:
        CoInitialize()
    except Exception:
        pass

    device = AudioUtilities.GetSpeakers()
    interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)

    return cast(interface, POINTER(IAudioEndpointVolume))


def _current_volume():
    volume = _volume_interface()
    return round(volume.GetMasterVolumeLevelScalar() * 100)


def _set_volume(percent):
    percent = max(0, min(100, int(percent)))
    volume = _volume_interface()
    volume.SetMasterVolumeLevelScalar(percent / 100.0, None)
    return percent


# ------------------------------------------------------------
# MEDIA KEYS
# ------------------------------------------------------------

def _press_media(key):
    pyautogui.press(key)


# ------------------------------------------------------------
# HANDLE
# ------------------------------------------------------------

def handle(text, raw=None):

    text = text.strip()

    if not text:
        return None

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    if text == "volume":
        if not _AUDIO_OK:
            return "Volume control needs the pycaw package."
        return f"Volume is at {_current_volume()} percent."

    match = re.match(r"^set volume to (\d{1,3})(?: percent)?$", text)

    if match:
        if not _AUDIO_OK:
            return "Volume control needs the pycaw package."
        level = _set_volume(match.group(1))
        return f"Volume set to {level} percent."

    match = re.match(
        r"^(?:turn |the |turn the )?volume (up|down|louder|quieter)"
        r"(?: (?:by )?(\d{1,3}))?$",
        text,
    )

    if match:
        step = int(match.group(2) or 10)
        going_up = match.group(1) in ("up", "louder")
    else:
        match = re.match(
            r"^(increase|raise|decrease|reduce|lower) (?:the )?volume"
            r"(?: (?:by )?(\d{1,3}))?$",
            text,
        )

        if match:
            step = int(match.group(2) or 10)
            going_up = match.group(1) in ("increase", "raise")

    if match:
        if not _AUDIO_OK:
            return "Volume control needs the pycaw package."

        current = _current_volume()
        level = _set_volume(current + step if going_up else current - step)

        return f"Volume set to {level} percent."

    match = re.match(r"^(?:volume )?(mute|unmute)$", text)

    if match:
        if not _AUDIO_OK:
            return "Volume control needs the pycaw package."

        volume = _volume_interface()
        muting = match.group(1) == "mute"
        volume.SetMute(1 if muting else 0, None)

        return "Muted." if muting else "Unmuted."

    if text in ("volume mute", "mute volume"):
        if not _AUDIO_OK:
            return "Volume control needs the pycaw package."
        _volume_interface().SetMute(1, None)
        return "Muted."

    # --------------------------------------------------------
    # BRIGHTNESS
    # --------------------------------------------------------

    if text == "brightness":
        if not _BRIGHTNESS_OK:
            return "Brightness control needs the screen-brightness-control package."
        try:
            return f"Brightness is at {sbc.get_brightness()[0]} percent."
        except Exception:
            return "I couldn't read the brightness."

    match = re.match(r"^set brightness to (\d{1,3})(?: percent)?$", text)

    if match:
        if not _BRIGHTNESS_OK:
            return "Brightness control needs the screen-brightness-control package."
        try:
            level = max(0, min(100, int(match.group(1))))
            sbc.set_brightness(level)
            return f"Brightness set to {level} percent."
        except Exception:
            return "I couldn't change the brightness."

    match = re.match(r"^brightness (?:up|down)(?: (?:by )?(\d{1,3}))?$", text)

    if match:
        if not _BRIGHTNESS_OK:
            return "Brightness control needs the screen-brightness-control package."
        try:
            step = int(match.group(1) or 10)
            current = sbc.get_brightness()[0]
            level = current + step if "up" in text else current - step
            level = max(0, min(100, level))
            sbc.set_brightness(level)
            return f"Brightness set to {level} percent."
        except Exception:
            return "I couldn't change the brightness."

    # --------------------------------------------------------
    # PLAYBACK KEYS
    # --------------------------------------------------------

    if not _PYAUTOGUI_OK:
        return None

    if re.match(r"^(?:play|resume)(?: (?:some |the )?(?:music|song|songs|video|media|track))?$", text):
        _press_media("playpause")
        return "Playing."

    if re.match(r"^pause(?: (?:the |some )?(?:music|song|songs|video|media|track))?$", text):
        _press_media("playpause")
        return "Paused."

    if re.match(r"^(?:next|skip)(?: (?:track|song|video|media))?$", text) or text == "next song please":
        _press_media("nexttrack")
        return "Next track."

    if re.match(r"^(?:previous|last)(?: (?:track|song|video|media))?$", text):
        _press_media("prevtrack")
        return "Previous track."

    return None


def name():
    return "media"
