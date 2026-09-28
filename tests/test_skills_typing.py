"""
============================================================
 TESTS — lyra/skills/typing.py
============================================================
"""

import pytest

from lyra.skills import typing


# ------------------------------------------------------------
# TYPE DICTATED TEXT
# ------------------------------------------------------------

def test_type_pastes_through_the_clipboard(autogui, clipboard):
    assert typing.handle("type hello world") == "Typed."
    assert clipboard.value == "hello world"
    assert autogui.hotkeyed("ctrl", "v")


def test_type_keeps_capitalisation_from_the_raw_text(autogui, clipboard):
    typing.handle("type Hello World", raw="type Hello World")
    assert clipboard.value == "Hello World"


def test_type_reports_missing_dependencies(monkeypatch, autogui):
    monkeypatch.setattr(typing, "_PYPERCLIP_OK", False)
    assert "pyautogui" in typing.handle("type hello")


# ------------------------------------------------------------
# PRESS KEYS
# ------------------------------------------------------------

@pytest.mark.parametrize("text, key", [
    ("press enter", "enter"),
    ("press escape", "esc"),
    ("press f5", "f5"),
    ("press space", "space"),
    ("press windows key", "win"),
])
def test_press_a_single_key(autogui, text, key):
    assert typing.handle(text) == "Done."
    assert autogui.pressed(key)


def test_press_strips_trailing_key_word(autogui):
    typing.handle("press enter key")
    assert autogui.pressed("enter")


def test_press_a_combination(autogui):
    assert typing.handle("press control alt") == "Done."
    assert autogui.hotkeyed("ctrl", "alt")


def test_press_rejects_single_letters(autogui):
    # only named keys are in the table — "ctrl c" is a shortcut, not a press
    assert typing.handle("press ctrl c") == "I don't know the c key."
    assert autogui.calls == []


def test_press_an_unknown_key_is_reported(autogui):
    assert typing.handle("press blarg") == "I don't know the blarg key."
    assert autogui.calls == []


def test_every_function_key_is_known(autogui):
    for i in range(1, 13):
        autogui.clear()
        assert typing.handle(f"press f{i}") == "Done."
        assert autogui.pressed(f"f{i}")


# ------------------------------------------------------------
# SHORTCUTS
# ------------------------------------------------------------

@pytest.mark.parametrize("text, combo", [
    ("copy", ("ctrl", "c")),
    ("paste", ("ctrl", "v")),
    ("select all", ("ctrl", "a")),
    ("undo", ("ctrl", "z")),
    ("save", ("ctrl", "s")),
])
def test_shortcuts(autogui, text, combo):
    assert typing.handle(text) == "Done."
    assert autogui.hotkeyed(*combo)


# ------------------------------------------------------------
# CLIPBOARD
# ------------------------------------------------------------

def test_copy_text_to_clipboard(autogui, clipboard):
    assert typing.handle("copy SRK to clipboard") == "Copied to clipboard."
    assert clipboard.value == "SRK"
    assert autogui.calls == []


def test_copy_the_current_selection(autogui, clipboard):
    assert typing.handle("copy this to clipboard") == "Copied."
    assert autogui.hotkeyed("ctrl", "c")


@pytest.mark.parametrize("text", [
    "read my clipboard",
    "read the clipboard",
    "show me the clipboard",
    "what's in my clipboard",
])
def test_read_clipboard(clipboard, text):
    clipboard.copy("secret")
    assert typing.handle(text) == "Clipboard says: secret"


def test_read_empty_clipboard(clipboard):
    assert typing.handle("read my clipboard") == "The clipboard is empty."


def test_clear_clipboard(clipboard):
    clipboard.copy("secret")
    assert typing.handle("clear the clipboard") == "Clipboard cleared."
    assert clipboard.value == ""


def test_clipboard_reports_missing_dependency(monkeypatch, autogui):
    monkeypatch.setattr(typing, "_PYPERCLIP_OK", False)
    assert "pyperclip" in typing.handle("copy SRK to clipboard")


# ------------------------------------------------------------
# NOT MINE
# ------------------------------------------------------------

@pytest.mark.parametrize("text", ["open notepad", "what time is it", ""])
def test_other_commands_are_left_alone(autogui, text):
    assert typing.handle(text) is None
