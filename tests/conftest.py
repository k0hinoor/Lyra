"""
============================================================
 LYRA TEST SUITE — SHARED FIXTURES
============================================================
 Nothing here touches real hardware, the network, the
 clipboard or the file system outside pytest's tmp_path.

 Every skill module looks its dependencies up as module
 globals (pyautogui, pyperclip, psutil, sbc, requests...),
 so tests swap those globals for fakes with monkeypatch.
 That means the suite behaves identically on Linux CI and
 on the Windows machine Lyra actually runs on — and a
 passing test run can never move a real mouse or press a
 real key.

 Fake helper classes can also be imported directly:

     from conftest import FakePyAutoGUI      # rootdir is on sys.path
============================================================
"""

import time
from types import SimpleNamespace

import pytest


# ------------------------------------------------------------
# FAKE: pyautogui
# ------------------------------------------------------------

class FakePyAutoGUI:
    """Records every key/mouse call instead of performing it."""

    def __init__(self):
        self.PAUSE = 0
        self.FAILSAFE = True
        self.calls = []

    # ---- recording -------------------------------------------------

    def _record(self, *call):
        self.calls.append(call)
        return call

    # ---- pyautogui API ---------------------------------------------

    def hotkey(self, *keys, **kwargs):
        self._record("hotkey", *keys)

    def press(self, key, **kwargs):
        self._record("press", key)

    def scroll(self, amount):
        self._record("scroll", amount)

    def write(self, text, interval=None):
        self._record("write", text)

    def screenshot(self, path=None):
        self._record("screenshot", path)
        return self

    # ---- assertions helpers ----------------------------------------

    def clear(self):
        self.calls.clear()

    @property
    def combos(self):
        """Just the key combinations: [('hotkey', 'ctrl', 'c'), ...]."""
        return [call for call in self.calls if call[0] in ("hotkey", "press")]

    def pressed(self, *keys):
        return ("press",) + keys in self.calls

    def hotkeyed(self, *keys):
        return ("hotkey",) + keys in self.calls


# ------------------------------------------------------------
# FAKE: pyperclip
# ------------------------------------------------------------

class FakeClipboard:
    """An in-memory clipboard standing in for pyperclip."""

    def __init__(self, value=""):
        self.value = value
        self.copies = []

    def copy(self, text):
        self.value = text
        self.copies.append(text)

    def paste(self):
        return self.value


# ------------------------------------------------------------
# FAKE: screen_brightness_control
# ------------------------------------------------------------

class FakeBrightness:
    """Stands in for the `screen_brightness_control` module."""

    def __init__(self, level=50):
        self.level = level
        self.calls = []

    def get_brightness(self):
        return [self.level]

    def set_brightness(self, value):
        self.level = max(0, min(100, int(value)))
        self.calls.append(self.level)
        return self.level


# ------------------------------------------------------------
# FAKE: psutil
# ------------------------------------------------------------

class FakePsutil:
    """Only the handful of psutil calls the system skill makes."""

    POWER_TIME_UNLIMITED = -1
    POWER_TIME_UNKNOWN = -2

    def __init__(self):
        self.battery = None                 # None = desktop, no battery
        self.cpu = 12.4
        self.ram = 45.6
        self.disk_free_gb = 120
        self.disk_total_gb = 512
        self.boot = time.time() - 5400      # up 1h30m
        self.calls = []

    def sensors_battery(self):
        self.calls.append("sensors_battery")
        return self.battery

    def cpu_percent(self, interval=None):
        return self.cpu

    def virtual_memory(self):
        return SimpleNamespace(percent=self.ram)

    def disk_usage(self, root):
        scale = 1024 ** 3
        return SimpleNamespace(
            free=self.disk_free_gb * scale,
            total=self.disk_total_gb * scale,
        )

    def boot_time(self):
        return self.boot

    def battery_at(self, percent, plugged=True, secsleft=POWER_TIME_UNLIMITED):
        self.battery = SimpleNamespace(
            percent=percent,
            power_plugged=plugged,
            secsleft=secsleft,
        )
        return self.battery


# ------------------------------------------------------------
# FAKE: subprocess.run
# ------------------------------------------------------------

class FakeRun:
    """Stands in for subprocess.run — records commands, fakes return codes."""

    def __init__(self, returncode=0):
        self.returncode = returncode
        self.commands = []

    def __call__(self, command, **kwargs):
        self.commands.append(command)
        return self


# ------------------------------------------------------------
# FAKE: an HTTP response (for requests-based tests)
# ------------------------------------------------------------

class FakeResponse:
    """Minimal `requests.Response` stand-in, streaming or not."""

    def __init__(self, lines=(), payload=None, status_ok=True):
        self._lines = list(lines)
        self._payload = payload
        self._status_ok = status_ok

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def raise_for_status(self):
        if not self._status_ok:
            raise RuntimeError("HTTP 500")

    def iter_lines(self):
        for line in self._lines:
            yield line.encode("utf-8") if isinstance(line, str) else line

    def json(self):
        return self._payload


# ------------------------------------------------------------
# FIXTURES — isolation
# ------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_memory_file(tmp_path, monkeypatch):
    """Never let a test read or write the real memory.json."""

    from lyra import config

    monkeypatch.setattr(config, "MEMORY_FILE", tmp_path / "memory.json")
    return config.MEMORY_FILE


# ------------------------------------------------------------
# FIXTURES — fake dependencies
# ------------------------------------------------------------

@pytest.fixture
def pyauto():
    return FakePyAutoGUI()


@pytest.fixture
def autogui(monkeypatch, pyauto):
    """Patch pyautogui into every skill that uses it."""

    from lyra.skills import media, system, typing, windows

    for module in (media, system, typing, windows):
        monkeypatch.setattr(module, "pyautogui", pyauto, raising=False)
        monkeypatch.setattr(module, "_PYAUTOGUI_OK", True, raising=False)

    return pyauto


@pytest.fixture
def clipboard(monkeypatch, autogui):
    """
    Patch pyperclip into the typing skill.

    Also pulls in the pyautogui fake, because the typing skill bails
    out early when key control is unavailable.
    """

    from lyra.skills import typing

    fake = FakeClipboard()
    monkeypatch.setattr(typing, "pyperclip", fake, raising=False)
    monkeypatch.setattr(typing, "_PYPERCLIP_OK", True, raising=False)

    return fake


@pytest.fixture
def volume(monkeypatch):
    """Patch the Windows audio helpers used by the media skill."""

    from lyra.skills import media

    state = {"level": 30, "muted": False, "calls": []}

    monkeypatch.setattr(media, "_AUDIO_OK", True)
    monkeypatch.setattr(media, "_current_volume", lambda: state["level"])

    def _set_volume(percent):
        state["level"] = max(0, min(100, int(percent)))
        state["calls"].append(state["level"])
        return state["level"]

    monkeypatch.setattr(media, "_set_volume", _set_volume)

    class FakeEndpoint:

        def GetMute(self):
            return 1 if state["muted"] else 0

        def SetMute(self, value, _guid):
            state["muted"] = bool(value)
            state["calls"].append("mute" if value else "unmute")

    monkeypatch.setattr(media, "_volume_interface", lambda: FakeEndpoint())

    return state


@pytest.fixture
def brightness(monkeypatch):
    """Patch the brightness backend used by the media skill."""

    from lyra.skills import media

    fake = FakeBrightness(level=50)
    monkeypatch.setattr(media, "sbc", fake, raising=False)
    monkeypatch.setattr(media, "_BRIGHTNESS_OK", True, raising=False)

    return fake


@pytest.fixture
def psutil_stub(monkeypatch):
    """Patch psutil into the system skill with controllable values."""

    from lyra.skills import system

    fake = FakePsutil()
    monkeypatch.setattr(system, "psutil", fake, raising=False)
    monkeypatch.setattr(system, "_PSUTIL_OK", True, raising=False)

    return fake


@pytest.fixture
def opened(monkeypatch):
    """Record every URL the web skill tries to open in a browser."""

    from lyra.skills import web

    urls = []
    monkeypatch.setattr(web, "_open", urls.append)

    return urls


@pytest.fixture
def started(monkeypatch):
    """Record every app / folder / settings target the apps skill opens."""

    from lyra.skills import apps

    targets = []
    monkeypatch.setattr(apps, "_start", targets.append)

    return targets


@pytest.fixture
def fake_brain():
    """A Brain stand-in that records questions and yields canned replies."""

    class FakeBrain:

        def __init__(self, reply="Sure, I can help with that."):
            self.reply = reply
            self.asked = []

        def ask_stream(self, text):
            self.asked.append(text)
            return iter([self.reply])

    return FakeBrain()


@pytest.fixture
def session(fake_brain):
    """A main.Session wired to a fake brain, an empty memory and no voice."""

    import main
    from lyra.memory import Memory

    return main.Session(fake_brain, Memory(), voice=None)


@pytest.fixture
def pc(monkeypatch, autogui, clipboard, volume, brightness, opened, started, psutil_stub):
    """
    Every fake at once: keys, clipboard, audio, brightness, browser,
    app launcher, psutil and the shell.

    Use it for tests that push arbitrary text through the skill
    router, so nothing can escape onto a real desktop.
    """

    from lyra.skills import apps, system

    monkeypatch.setattr(system, "IS_WINDOWS", True)

    shell = FakeRun()
    monkeypatch.setattr(system.subprocess, "run", shell)
    monkeypatch.setattr(apps.subprocess, "run", shell)

    return SimpleNamespace(
        pyauto=autogui,
        clipboard=clipboard,
        volume=volume,
        brightness=brightness,
        urls=opened,
        started=started,
        psutil=psutil_stub,
        shell=shell,
    )
