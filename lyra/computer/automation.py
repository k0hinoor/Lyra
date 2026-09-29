"""Narrow, validated desktop-control adapter. No shell/code execution API."""

import logging
import os
import subprocess
import time

log = logging.getLogger(__name__)

# Single source of truth for keyboard actions: the planner prompt, the plan
# validator and the dispatch functions below all read these.
PRESSABLE_KEYS = frozenset({
    "enter", "esc", "tab", "space", "backspace", "delete", "up", "down",
    "left", "right", "home", "end", "pageup", "pagedown", "f5", "f11",
})
HOTKEY_KEYS = frozenset({"ctrl", "alt", "shift", "win", "c", "v", "a", "s", "z", "t", "w", "f", "p"})


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
    if key not in PRESSABLE_KEYS:
        raise ValueError(f"Key is not allowed: {key}")
    gui.press(key)


def hotkey(keys):
    if any(key not in HOTKEY_KEYS for key in keys):
        raise ValueError("Hotkey contains an unsupported key")
    _pyautogui().hotkey(*keys)


# ------------------------------------------------------------
# WINDOW FOCUS  (never type blind into the wrong window)
# ------------------------------------------------------------

def _title(window):
    return (getattr(window, "title", "") or "").strip().casefold()


def _find_app_window(gw, hint):
    """First window whose title ends with the app name ("Untitled - Notepad").

    Ending with the name, not merely containing it, keeps a browser tab
    called "notepad - Google Search" from being mistaken for Notepad.
    """
    for window in gw.getAllWindows():
        title = _title(window)
        if title and (title == hint or title.endswith(hint)):
            return window
    return None


def _bring_to_front(window, gw, hint):
    try:
        if window.isMinimized:
            window.restore()
    except Exception:
        pass
    try:
        window.activate()
    except Exception:
        # pygetwindow raises even on success on some Windows builds, and
        # Windows can refuse programmatic focus; minimize + restore is the
        # classic workaround. Either way the result is verified below.
        try:
            window.minimize()
            time.sleep(0.2)
            window.restore()
        except Exception:
            pass
    time.sleep(0.3)
    try:
        active = gw.getActiveWindow()
    except Exception:
        return False
    title = _title(active) if active is not None else ""
    return bool(title) and (title == hint or title.endswith(hint))


def focus_app_window(app, timeout=10.0):
    """Bring the window of an app LYRA just opened to the front.

    Returns True only when the foreground window is verified to be that
    app, so keyboard input can never land in another window.
    """
    try:
        import pygetwindow as gw
    except Exception as exc:
        raise RuntimeError(f"Window control unavailable: {exc}") from exc

    hint = app.strip().casefold()
    deadline = time.monotonic() + timeout
    while True:
        window = _find_app_window(gw, hint)
        if window is not None and _bring_to_front(window, gw, hint):
            return True
        if time.monotonic() >= deadline:
            log.warning("Could not verify a focused %r window within %.0fs", app, timeout)
            return False
        time.sleep(0.3)


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
