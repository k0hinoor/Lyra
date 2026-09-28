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
