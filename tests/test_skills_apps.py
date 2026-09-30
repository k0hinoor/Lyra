"""
============================================================
 TESTS — lyra/skills/apps.py
============================================================
"""

import pytest

from lyra.skills import apps
from lyra.utils import normalize

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
# START MENU DISCOVERY — ANY INSTALLED APP, BY ITS REAL NAME
# ------------------------------------------------------------
# Windows has no entry for half the software people own. The Start
# Menu shortcut does: "open davinci resolve" must find
# "DaVinci Resolve.lnk" without a hand-written table entry.

@pytest.fixture
def start_menu(tmp_path, monkeypatch):
    """A fake Start Menu: a user tree and the machine-wide one."""
    user = tmp_path / "user"
    common = tmp_path / "common"

    programs = user / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    common_programs = common / "Microsoft" / "Windows" / "Start Menu" / "Programs"

    (programs / "DaVinci Resolve").mkdir(parents=True)
    common_programs.mkdir(parents=True)

    (programs / "DaVinci Resolve" / "DaVinci Resolve.lnk").write_bytes(b"")
    (programs / "Uninstall DaVinci Resolve.lnk").write_bytes(b"")
    (programs / "Notepad.lnk").write_bytes(b"")
    (common_programs / "OBS Studio (64bit).lnk").write_bytes(b"")

    monkeypatch.setenv("APPDATA", str(user))
    monkeypatch.setenv("PROGRAMDATA", str(common))

    return programs


def test_start_menu_roots_are_collected_from_both_env_vars(start_menu):
    roots = apps._start_menu_roots()

    assert len(roots) == 2
    assert all(root.is_dir() for root in roots)
    assert any(root.name == "Programs" for root in roots)


def test_missing_start_menu_folders_are_dropped(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "nowhere"))
    monkeypatch.setenv("PROGRAMDATA", str(tmp_path / "also-nowhere"))

    assert apps._start_menu_roots() == []


def test_pretty_name_drops_punctuation_and_case():
    assert apps._pretty_name("OBS Studio (64bit)") == "obs studio 64bit"
    assert apps._pretty_name("  DaVinci Resolve!  ") == "davinci resolve"


def test_an_exact_shortcut_name_is_found(start_menu):
    found = apps._find_start_menu_app("davinci resolve")

    assert found is not None
    assert found.name == "DaVinci Resolve.lnk"


def test_an_uninstaller_is_never_returned(start_menu):
    found = apps._find_start_menu_app("uninstall davinci resolve")

    assert found is not None
    assert found.name != "Uninstall DaVinci Resolve.lnk"


def test_a_shortcut_listed_only_by_its_maintenance_twins_is_skipped(
        tmp_path, monkeypatch):
    programs = tmp_path / "user" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    programs.mkdir(parents=True)
    for stem in ("Uninstall Sketch", "Sketch Setup", "Sketch Update", "Repair Sketch"):
        (programs / f"{stem}.lnk").write_bytes(b"")

    monkeypatch.setenv("APPDATA", str(tmp_path / "user"))
    monkeypatch.setenv("PROGRAMDATA", str(tmp_path / "common"))

    assert apps._find_start_menu_app("uninstall sketch") is None


def test_a_machine_wide_shortcut_is_found_too(start_menu):
    found = apps._find_start_menu_app("obs studio")

    assert found is not None
    assert found.name == "OBS Studio (64bit).lnk"


def test_a_word_of_the_name_matches_a_longer_shortcut(start_menu):
    found = apps._find_start_menu_app("obs")

    assert found is not None
    assert found.name == "OBS Studio (64bit).lnk"


def test_an_unknown_name_matches_nothing(start_menu):
    assert apps._find_start_menu_app("skype") is None


# ------------------------------------------------------------
# OPENING AN APP THAT IS NOT IN ANY TABLE
# ------------------------------------------------------------

def test_open_by_name_uses_the_start_menu_shortcut(start_menu, started):
    shortcut = start_menu / "DaVinci Resolve" / "DaVinci Resolve.lnk"

    assert apps.handle("open davinci resolve") == "Opening DaVinci Resolve."
    assert started == [str(shortcut)]


def test_open_by_name_launches_the_shortcut_path_verbatim(start_menu, started):
    apps.open_by_name("davinci resolve")

    (target,) = started
    assert target.endswith("DaVinci Resolve.lnk")
    assert "Uninstall" not in target


def test_an_app_in_no_table_and_no_start_menu_is_reported_as_missing(
        start_menu, monkeypatch):
    def fail(target):
        raise FileNotFoundError(target)

    monkeypatch.setattr(apps, "_start", fail)

    assert apps.open_by_name("some app nobody has") == (
        "I couldn't find an app called some app nobody has."
    )


@pytest.mark.parametrize("name", ["", "   ", "brave and chrome", "brave then chrome"])
def test_open_by_name_ignores_nothing_openable(started, name):
    assert apps.open_by_name(name) is None
    assert started == []


def test_open_by_name_still_prefers_the_known_tables(start_menu, started):
    assert apps.open_by_name("notepad") == "Opening Notepad."
    assert started == ["notepad"]


# ------------------------------------------------------------
# RUN-ON SPEECH: "OPEN NOTEPAD AND TELL ME WHAT IS GOING ON"
# ------------------------------------------------------------
# A conversational tail belongs to the chat, so the app still opens.
# A second step ("and write about india") belongs to the planner.

@pytest.mark.parametrize("said", [
    "open notepad and tell me what is going on",
    "open notepad and then tell me what is going on",
    "open notepad and explain that",
    "open notepad and read me the news",
    "open notepad and show me the time",
    "open notepad and why is the sky blue",
    "open notepad and can you check the time",
    "open notepad and give me the weather",
])
def test_a_conversational_tail_still_opens_the_app(started, said):
    reply = apps.handle(normalize(said))

    assert reply == "Opening Notepad."
    assert started == ["notepad"]


@pytest.mark.parametrize("said", [
    "open notepad and write about india",
    "open brave and search youtube for lofi",
    "open notepad then write a poem",
])
def test_a_second_step_is_left_to_the_multi_step_handlers(started, said):
    assert apps.handle(normalize(said)) is None
    assert started == []


def test_a_conversational_tail_uses_the_words_the_user_really_said(started):
    apps.handle(normalize("open, davinci resolve and tell me about it"),
                raw="open, davinci resolve and tell me about it")

    assert started == ["davinci resolve"]



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
