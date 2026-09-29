"""
============================================================
 TESTS — lyra/skills/apps.py
============================================================
"""

import pytest

from lyra.skills import apps

from conftest import FakeRun


# ------------------------------------------------------------
# OPEN — KNOWN APPS
# ------------------------------------------------------------

@pytest.mark.parametrize("text, target, reply", [
    ("open notepad", "notepad", "Opening Notepad."),
    ("open calculator", "calc", "Opening Calculator."),
    ("open vs code", "code", "Opening Vs Code."),
    ("launch chrome", "chrome", "Opening Chrome."),
    ("start spotify", "spotify", "Opening Spotify."),
    ("open task manager", "taskmgr", "Opening Task Manager."),
])
def test_open_known_app(started, text, target, reply):
    assert apps.handle(text) == reply
    assert started == [target]


def test_open_settings_page_uses_a_pretty_name(started):
    assert apps.handle("open bluetooth settings") == "Opening Bluetooth Settings."
    assert started == ["ms-settings:bluetooth"]


def test_open_strips_politeness(started):
    apps.handle("open notepad please")
    assert started == ["notepad"]


# ------------------------------------------------------------
# OPEN — FOLDERS, DRIVES, SETTINGS
# ------------------------------------------------------------

@pytest.mark.parametrize("text, target, reply", [
    ("open downloads", "shell:Downloads", "Opening downloads."),
    ("open documents", "shell:Personal", "Opening documents."),
    ("open recycle bin", "shell:RecycleBinFolder", "Opening recycle bin."),
])
def test_open_folder(started, text, target, reply):
    assert apps.handle(text) == reply
    assert started == [target]


def test_open_drive_letter(started):
    assert apps.handle("open c drive") == "Opening C drive."
    assert started == ["C:\\"]


@pytest.mark.parametrize("text, target", [
    ("open settings", "ms-settings:"),
    ("open wifi settings", "ms-settings:network-wifi"),
    ("open display settings", "ms-settings:display"),
])
def test_open_settings_page(started, text, target):
    assert apps.handle(text).startswith("Opening ")
    assert started == [target]


# ------------------------------------------------------------
# OPEN — UNKNOWN APPS FALL THROUGH TO WINDOWS
# ------------------------------------------------------------

def test_unknown_app_is_passed_to_windows_verbatim(started):
    assert apps.handle("open Some Random App") == "Opening Some Random App."
    assert started == ["Some Random App"]


# ------------------------------------------------------------
# CLOSE
# ------------------------------------------------------------

@pytest.fixture
def taskkill(monkeypatch):
    """Install a fake subprocess.run and return a factory for it."""

    def install(returncode=0):
        fake = FakeRun(returncode)
        monkeypatch.setattr(apps.subprocess, "run", fake)
        return fake

    return install


def test_close_known_app(taskkill):
    fake = taskkill()

    assert apps.handle("close chrome") == "Closed Chrome."
    assert fake.commands == [["taskkill", "/F", "/IM", "chrome.exe"]]


def test_close_tries_every_known_executable(taskkill):
    fake = taskkill(returncode=1)

    assert apps.handle("close calculator") == "I couldn't find calculator running."
    assert fake.commands == [
        ["taskkill", "/F", "/IM", "CalculatorApp.exe"],
        ["taskkill", "/F", "/IM", "Calculator.exe"],
    ]


def test_close_unknown_app_guesses_the_executable_name(taskkill):
    fake = taskkill(returncode=1)

    assert apps.handle("close myapp") == "I couldn't find myapp running."
    assert fake.commands == [["taskkill", "/F", "/IM", "myapp.exe"]]


@pytest.mark.parametrize("text", ["quit notepad", "kill chrome", "exit spotify"])
def test_close_synonyms(taskkill, text):
    fake = taskkill()
    assert apps.handle(text).startswith("Closed ")
    assert fake.commands[0][0] == "taskkill"


# ------------------------------------------------------------
# NOT MINE
# ------------------------------------------------------------

def test_window_commands_are_left_to_the_windows_skill(taskkill):
    fake = taskkill()

    assert apps.handle("close this window") is None
    assert apps.handle("close the tab") is None
    assert fake.commands == []


@pytest.mark.parametrize("text", ["what time is it", "tell me a joke", ""])
def test_other_commands_are_left_alone(started, text):
    assert apps.handle(text) is None
    assert started == []


# ------------------------------------------------------------
# DATA SANITY
# ------------------------------------------------------------

def test_command_tables_are_well_formed():
    for table in (apps.OPEN_APPS, apps.OPEN_SETTINGS, apps.OPEN_FOLDERS):
        for key, value in table.items():
            assert key == key.strip().lower(), key
            assert value, key

    for key, exes in apps.CLOSE_EXES.items():
        assert key == key.strip().lower(), key
        assert exes, key
        assert all(exe.lower().endswith(".exe") for exe in exes), key


# ------------------------------------------------------------
# TRAILING "and" / "then"  (run-on speech)
# ------------------------------------------------------------

@pytest.mark.parametrize("text, target", [
    ("open brave and", "brave"),
    ("open notepad and then", "notepad"),
    ("open brave and then", "brave"),
])
def test_trailing_conjunctions_are_stripped(started, text, target):
    reply = apps.handle(text)
    assert reply == f"Opening {target.title()}."
    assert started == [target]


# ------------------------------------------------------------
# NEVER REPORT SUCCESS WITHOUT STARTING SOMETHING
# ------------------------------------------------------------

def test_a_comma_in_the_raw_utterance_still_launches(started):
    # Whisper transcript kept the comma: "open, breathe and". The
    # normalized text is clean, but the raw fallback used to fail on
    # the comma, so nothing started while Lyra said "Opening...".
    reply = apps.handle("open breathe and", raw="open, breathe and")
    assert started == ["breathe"], "the app must actually be started"
    assert reply == "Opening breathe."


def test_an_unknown_app_failure_is_reported_not_claimed(monkeypatch):
    def fail(target):
        raise FileNotFoundError(f"not found: {target}")

    monkeypatch.setattr(apps, "_start", fail)

    # unknown name, comma in the raw transcript
    assert apps.handle("open zzzapp and", raw="open, zzzapp and") == (
        "I couldn't find an app called zzzapp."
    )
    # a catalogued app whose launch still fails (e.g. not installed)
    assert apps.handle("open brave") == "I couldn't find an app called Brave."


def test_unknown_app_oserror_is_caught(monkeypatch):
    monkeypatch.setattr(apps, "_start", lambda target: (_ for _ in ()).throw(OSError("nope")))
    assert apps.handle("open zzznope") == "I couldn't find an app called zzznope."


# ------------------------------------------------------------
# RUN-ON MULTI-STEP IS FOR THE PLANNER, NOT ONE GIANT APP NAME
# ------------------------------------------------------------

def test_multistep_open_is_not_treated_as_one_app(started):
    assert apps.handle("open notepad and write about india") is None
    assert started == []


# ------------------------------------------------------------
# FULL SCREEN IS NOT AN APP
# ------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "exit full screen",
    "close full screen",
    "exit fullscreen",
    "close full screen mode",
])
def test_fullscreen_is_not_closed_like_an_app(taskkill, text):
    fake = taskkill()
    assert apps.handle(text) is None
    assert fake.commands == []
