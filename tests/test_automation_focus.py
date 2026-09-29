"""
============================================================
 TESTS — lyra/computer/automation.py  (window focus)
============================================================
 Keystrokes go to whatever window is in front, so before a task types
 into the app it opened, focus_app_window() must bring THAT app to the
 front and verify it. pygetwindow is faked; nothing touches a desktop.
============================================================
"""

import sys
import types

import pytest

from lyra.computer import automation


class FakeWindow:

    def __init__(self, title, desktop, minimized=False, activate_error=False):
        self.title = title
        self.isMinimized = minimized
        self._desktop = desktop
        self._activate_error = activate_error

    def activate(self):
        self._desktop.active = self
        if self._activate_error:
            # pygetwindow's well-known quirk: raises although it worked.
            raise RuntimeError("Error code from Windows: 0 - The operation completed successfully.")

    def restore(self):
        self.isMinimized = False

    def minimize(self):
        self.isMinimized = True


class FakeDesktop:

    def __init__(self):
        self.windows = []
        self.active = None

    def add(self, title, **kwargs):
        window = FakeWindow(title, self, **kwargs)
        self.windows.append(window)
        return window

    # the pygetwindow module API used by automation
    def getAllWindows(self):
        return list(self.windows)

    def getActiveWindow(self):
        return self.active


@pytest.fixture
def desktop(monkeypatch):
    fake = FakeDesktop()
    module = types.SimpleNamespace(
        getAllWindows=fake.getAllWindows, getActiveWindow=fake.getActiveWindow
    )
    monkeypatch.setitem(sys.modules, "pygetwindow", module)
    monkeypatch.setattr(automation.time, "sleep", lambda _seconds: None)
    return fake


def test_the_opened_app_is_brought_to_the_front(desktop):
    terminal = desktop.add("Windows PowerShell")
    desktop.active = terminal
    notepad = desktop.add("Untitled - Notepad")
    assert automation.focus_app_window("notepad", timeout=0) is True
    assert desktop.active is notepad


def test_a_browser_tab_that_mentions_the_app_is_not_mistaken_for_it(desktop):
    desktop.add("notepad - Google Search - Google Chrome")
    notepad = desktop.add("*Untitled - Notepad")
    assert automation.focus_app_window("notepad", timeout=0) is True
    assert desktop.active is notepad


def test_activation_that_raises_but_worked_is_still_verified(desktop):
    notepad = desktop.add("Untitled - Notepad", activate_error=True)
    assert automation.focus_app_window("notepad", timeout=0) is True
    assert desktop.active is notepad


def test_a_minimized_window_is_restored_first(desktop):
    notepad = desktop.add("Untitled - Notepad", minimized=True)
    assert automation.focus_app_window("notepad", timeout=0) is True
    assert notepad.isMinimized is False


def test_no_window_means_no_focus(desktop):
    desktop.active = desktop.add("Windows PowerShell")
    assert automation.focus_app_window("notepad", timeout=0) is False


def test_focus_that_windows_refuses_is_reported_not_assumed(desktop, monkeypatch):
    terminal = desktop.add("Windows PowerShell")
    desktop.active = terminal
    notepad = desktop.add("Untitled - Notepad")
    monkeypatch.setattr(notepad, "activate", lambda: None)   # Windows ignores the request
    assert automation.focus_app_window("notepad", timeout=0) is False


def test_missing_window_library_is_a_clear_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "pygetwindow", None)
    with pytest.raises(RuntimeError, match="Window control unavailable"):
        automation.focus_app_window("notepad", timeout=0)
