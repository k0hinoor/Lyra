"""
============================================================
 TESTS — lyra/skills/windows.py
============================================================
"""

import pytest

from lyra.skills import windows


# ------------------------------------------------------------
# WINDOW STATE
# ------------------------------------------------------------

def test_minimize_presses_win_down_twice(autogui):
    assert windows.handle("minimize window") == "Minimized."
    assert autogui.combos == [("hotkey", "win", "down"), ("hotkey", "win", "down")]


@pytest.mark.parametrize("text", ["minimize this window", "minimize the window", "minimize window"])
def test_minimize_accepts_fillers(autogui, text):
    assert windows.handle(text) == "Minimized."


def test_maximize_window(autogui):
    assert windows.handle("maximize window") == "Maximized."
    assert autogui.hotkeyed("win", "up")


def test_show_desktop(autogui):
    assert windows.handle("show desktop") == "Showing desktop."
    assert windows.handle("show the desktop") == "Showing desktop."
    assert autogui.hotkeyed("win", "d")


@pytest.mark.parametrize("text", ["switch window", "alt tab", "next window", "change window"])
def test_switch_window(autogui, text):
    assert windows.handle(text) == "Switching."
    assert autogui.hotkeyed("alt", "tab")


def test_task_view(autogui):
    assert windows.handle("task view") == "Opening task view."
    assert autogui.hotkeyed("win", "tab")


# ------------------------------------------------------------
# WINDOW LIFECYCLE
# ------------------------------------------------------------

def test_close_window(autogui):
    assert windows.handle("close this window") == "Closed window."
    assert autogui.hotkeyed("alt", "f4")


# ------------------------------------------------------------
# TABS
# ------------------------------------------------------------

@pytest.mark.parametrize("text, combo, reply", [
    ("new tab", ("ctrl", "t"), "New tab."),
    ("new window", ("ctrl", "n"), "New window."),
    ("close tab", ("ctrl", "w"), "Closed tab."),
    ("reopen tab", ("ctrl", "shift", "t"), "Reopened tab."),
])
def test_tab_commands(autogui, text, combo, reply):
    assert windows.handle(text) == reply
    assert autogui.hotkeyed(*combo)


def test_refresh_presses_f5(autogui):
    assert windows.handle("refresh") == "Refreshing."
    assert windows.handle("reload the page") == "Refreshing."
    assert autogui.pressed("f5")


def test_navigation(autogui):
    assert windows.handle("go back") == "Going back."
    assert windows.handle("go forward") == "Going forward."
    assert autogui.hotkeyed("alt", "left")
    assert autogui.hotkeyed("alt", "right")


# ------------------------------------------------------------
# SCROLL & ZOOM
# ------------------------------------------------------------

@pytest.mark.parametrize("text, amount", [
    ("scroll up", 5),
    ("scroll down", -5),
    ("scroll up 10", 10),
    ("scroll down by 3", -3),
])
def test_scroll(autogui, text, amount):
    assert windows.handle(text) == "Done."
    assert ("scroll", amount) in autogui.calls


def test_zoom(autogui):
    assert windows.handle("zoom in") == "Zooming in."
    assert windows.handle("zoom out") == "Zooming out."
    assert autogui.hotkeyed("ctrl", "+")
    assert autogui.hotkeyed("ctrl", "-")


def test_fullscreen(autogui):
    assert windows.handle("fullscreen") == "Toggled fullscreen."
    assert autogui.pressed("f11")


# ------------------------------------------------------------
# NOT MINE
# ------------------------------------------------------------

@pytest.mark.parametrize("text", ["open notepad", "what time is it", "close chrome", ""])
def test_other_commands_are_left_alone(autogui, text):
    assert windows.handle(text) is None


def test_no_pyautogui_means_no_window_control(monkeypatch):
    monkeypatch.setattr(windows, "_PYAUTOGUI_OK", False)
    assert windows.handle("minimize window") is None
