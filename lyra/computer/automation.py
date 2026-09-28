"""Narrow, validated desktop-control adapter. No shell/code execution API."""

import logging
import os
import subprocess

log = logging.getLogger(__name__)


def _pyautogui():
    try:
        import pyautogui
        pyautogui.PAUSE = 0
        return pyautogui
    except Exception as exc:
        raise RuntimeError(f"Desktop automation unavailable: {exc}") from exc


def open_app(name):
    """Open only a catalogued application; never execute an LLM-provided command."""
    from ..skills.apps import OPEN_APPS

    app = name.strip().casefold()
    if app not in OPEN_APPS:
        raise ValueError(f"Application is not in LYRA's approved app catalog: {name}")
    target = OPEN_APPS[app]
    if os.name == "nt" and (target.startswith("ms-settings:") or target.endswith(":")):
        os.startfile(target)  # Windows URI activation, not command parsing
    else:
        subprocess.Popen([target], shell=False)


def type_text(text):
    if not isinstance(text, str) or len(text) > 5000:
        raise ValueError("Text is invalid or exceeds 5000 characters")
    try:
        import pyperclip
        pyperclip.copy(text)
    except Exception as exc:
        raise RuntimeError(f"Clipboard unavailable: {exc}") from exc
    _pyautogui().hotkey("ctrl", "v")


def press_key(key):
    gui = _pyautogui()
    allowed = {
        "enter", "esc", "tab", "space", "backspace", "delete", "up", "down",
        "left", "right", "home", "end", "pageup", "pagedown", "f5", "f11",
    }
    if key not in allowed:
        raise ValueError(f"Key is not allowed: {key}")
    gui.press(key)


def hotkey(keys):
    allowed = {"ctrl", "alt", "shift", "win", "c", "v", "a", "s", "z", "t", "w", "f", "p"}
    if any(key not in allowed for key in keys):
        raise ValueError("Hotkey contains an unsupported key")
    _pyautogui().hotkey(*keys)


def _validate_point(x, y):
    gui = _pyautogui()
    width, height = gui.size()
    if not (0 <= x < width and 0 <= y < height):
        raise ValueError(f"Point ({x}, {y}) is outside the screen ({width}x{height})")


def move_mouse(x, y):
    _validate_point(x, y)
    _pyautogui().moveTo(x, y)


def click(button="left", clicks=1):
    _pyautogui().click(button=button, clicks=clicks)


def scroll(direction, amount):
    gui = _pyautogui()
    delta = amount if direction in ("up", "right") else -amount
    if direction in ("left", "right"):
        gui.hscroll(delta)
    else:
        gui.scroll(delta)


def drag_drop(start_x, start_y, end_x, end_y):
    _validate_point(start_x, start_y)
    _validate_point(end_x, end_y)
    gui = _pyautogui()
    gui.moveTo(start_x, start_y)
    gui.dragTo(end_x, end_y, duration=0.35, button="left")
