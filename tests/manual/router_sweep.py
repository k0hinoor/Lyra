"""
============================================================
 ROUTER SWEEP  (development helper, not a test)
============================================================
 Pushes a large corpus of real commands through the whole skill
 router with every hardware dependency faked, and prints what
 each one produced. Run it on two checkouts and diff the output
 to see exactly what the change did:

     python tests/manual/router_sweep.py > after.txt
     git stash && python tests/manual/router_sweep.py > before.txt
     git stash pop && diff before.txt after.txt
============================================================
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.conftest import (                                     # noqa: E402
    FakeBrightness, FakeClipboard, FakePyAutoGUI, FakePsutil, FakeRun,
)
from lyra.skills import apps, media, route, system, typing, web, windows  # noqa: E402
from lyra.utils import normalize                                  # noqa: E402

try:                                                             # absent before the fix
    from lyra.utils import strip_politeness
except ImportError:                                              # pragma: no cover
    def strip_politeness(text):
        return text

CORPUS = [
    # ---- volume / sound ------------------------------------------
    "volume", "volume up", "volume down 20", "set volume to 40", "mute", "unmute",
    "mute volume", "increase the volume", "please increase the volume",
    "can you turn up the volume", "could you please turn up the volume",
    "turn up my volume", "raise the volume a bit", "make it louder", "louder please",
    "boost the volume", "crank up the volume", "turn the music up", "turn it up",
    "raise it", "lower it", "turn the volume all the way up", "turn it up by 5",
    "the sound is too low", "it's too quiet", "i can't hear you", "volume is too low",
    "set the volume to sixty", "volume to 80", "increase the volume to 60",
    "full volume", "max volume", "half volume", "mute the sound", "silence the audio",
    "turn down the volume", "it's too loud", "make it quieter", "volume is too loud",
    "what's the volume", "how loud is it", "volume level", "turn off the sound",

    # ---- brightness -----------------------------------------------
    "brightness", "brightness up", "brightness down 20", "set brightness to 70",
    "make the screen brighter", "it's too dark", "dim the screen",
    "set the brightness to eighty", "how bright is the screen",

    # ---- playback -------------------------------------------------
    "play", "play music", "pause", "next track", "previous track",
    "stop the music", "skip to the next song", "resume",

    # ---- windows / typing (must be untouched) ---------------------
    "minimize window", "maximize window", "show desktop", "switch window", "task view",
    "new tab", "close tab", "reopen the tab", "refresh", "go back", "go forward",
    "scroll up", "scroll down 10", "zoom in", "zoom out", "fullscreen",
    "close the window", "new window", "scroll down the screen",

    "type hello world", "press enter", "press escape", "press f5", "copy", "cut",
    "paste", "select all", "undo", "redo", "save", "find", "print",
    "press the enter key", "press page up", "press the up arrow", "press ctrl c",
    "copy this to clipboard", "copy s r k to clipboard", "read my clipboard",
    "clear clipboard", "print screen",

    # ---- apps / web -----------------------------------------------
    "open notepad", "open calculator", "open spotify", "open chrome", "close chrome",
    "open sound settings", "open display settings", "open storage settings",
    "open battery settings", "open settings", "open my music folder",
    "open desktop", "open the pictures folder", "open settings for bluetooth",
    "search for best laptops", "google python tutorial", "wikipedia albert einstein",
    "open youtube", "play beliver on youtube", "search youtube for lofi beats",
    "open google dot com", "what's the weather", "what's the weather like in bhubaneswar",

    # ---- system ---------------------------------------------------
    "what time is it", "what's the date", "what day is it", "battery", "cpu usage",
    "ram usage", "how is my pc", "how much ram am i using", "disk space",
    "how much storage is left", "open storage settings", "what's my ip", "uptime",
    "wifi password", "take a screenshot", "lock my pc", "cancel shutdown",

    # ---- dangerous (confirmation) ---------------------------------
    "shutdown the pc", "restart", "put the pc to sleep", "empty the recycle bin",

    # ---- fun ------------------------------------------------------
    "tell me a joke", "flip a coin", "roll a dice", "pick a number between 1 and 100",

    # ---- memory-ish / brain ---------------------------------------
    "what do you remember", "remember that my exam is on friday", "forget that exam",

    # ---- must never be claimed by a knob -------------------------
    "the battery is too low", "the room is too noisy", "it's too late",
    "silence the notification", "why can't i hear the birds", "what volume should i use",
    "dark mode", "power off", "search for volume", "play music on spotify",
    "why is the sky blue", "tell me more about python", "how do i bake a cake",
]


def install_fakes():
    """Wire every hardware dependency to an in-memory fake."""

    pyauto = FakePyAutoGUI()
    clipboard = FakeClipboard()
    brightness = FakeBrightness(level=50)
    psutil = FakePsutil()
    shell = FakeRun()
    urls = []
    started = []
    state = {"level": 30, "muted": False}

    for module in (media, system, typing, windows):
        module.pyautogui = pyauto
        module._PYAUTOGUI_OK = True

    media.sbc = brightness
    media._BRIGHTNESS_OK = True
    media._AUDIO_OK = True
    media._current_volume = lambda: state["level"]
    media._set_volume = lambda p: state.__setitem__(
        "level", max(0, min(100, int(p)))
    ) or state["level"]
    media._is_muted = lambda: state["muted"]
    media._set_muted = lambda m: state.__setitem__("muted", m)

    typing.pyperclip = clipboard
    typing._PYPERCLIP_OK = True

    system.psutil = psutil
    system._PSUTIL_OK = True
    system.IS_WINDOWS = True
    system.subprocess.run = shell
    apps.subprocess.run = shell

    web._open = urls.append
    apps._start = started.append

    return state


def main():
    state = install_fakes()

    for raw in CORPUS:
        state["level"] = 30
        state["muted"] = False
        reply, confirmation = route(strip_politeness(normalize(raw)), raw=raw)
        answer = "CONFIRM" if confirmation else (reply or "BRAIN")
        print(f"{raw:<42} {state['level']:>3}%  {answer}")


if __name__ == "__main__":
    main()
