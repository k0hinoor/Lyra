"""
============================================================
 SKILL: WINDOWS & TABS
============================================================
 Window management, tabs, scrolling, zoom.
============================================================
"""

import re
import time

from ..messages import t

try:
    import pyautogui
    pyautogui.PAUSE = 0
    _PYAUTOGUI_OK = True
except Exception:
    _PYAUTOGUI_OK = False


def _hotkey(*combo, delay=0.0):
    pyautogui.hotkey(*combo, interval=0.05)

    if delay:
        time.sleep(delay)


def handle(text, raw=None):

    text = text.strip()

    if not text:
        return None

    if not _PYAUTOGUI_OK:
        return None

    # --------------------------------------------------------
    # WINDOW STATE
    # --------------------------------------------------------

    if re.match(r"^minimize(?: this| the| current)? window$", text):
        pyautogui.hotkey("win", "down")
        time.sleep(0.15)
        pyautogui.hotkey("win", "down")
        return t("windows.minimized")

    if re.match(r"^maximize(?: this| the| current)? window$", text):
        pyautogui.hotkey("win", "up")
        return t("windows.maximized")

    if re.match(r"^show (?:the )?desktop$", text):
        pyautogui.hotkey("win", "d")
        return t("windows.desktop")

    if text in ("switch window", "alt tab", "next window", "change window"):
        _hotkey("alt", "tab")
        return t("windows.switching")

    if text == "task view":
        pyautogui.hotkey("win", "tab")
        return t("windows.task_view")

    # --------------------------------------------------------
    # WINDOW LIFECYCLE
    # --------------------------------------------------------

    if re.match(r"^close (?:this |the |that )?window$", text):
        pyautogui.hotkey("alt", "f4")
        return t("windows.closed_window")

    # --------------------------------------------------------
    # TABS
    # --------------------------------------------------------

    if text == "new tab":
        pyautogui.hotkey("ctrl", "t")
        return t("windows.new_tab")

    if text == "new window":
        pyautogui.hotkey("ctrl", "n")
        return t("windows.new_window")

    if re.match(r"^close (?:this |the )?tab$", text):
        pyautogui.hotkey("ctrl", "w")
        return t("windows.closed_tab")

    if re.match(
        r"^(?:reopen|restore|undo close)(?: (?:the|this|that|my|last|closed))* tab$",
        text,
    ):
        pyautogui.hotkey("ctrl", "shift", "t")
        return t("windows.reopened_tab")

    if re.match(r"^(?:next|switch|go to)(?: (?:the|my|next))* tab$", text):
        _hotkey("ctrl", "tab")
        return t("windows.next_tab")

    if re.match(r"^(?:previous|last|back|go back)(?: (?:the|my|previous))* tab$", text):
        _hotkey("ctrl", "shift", "tab")
        return t("windows.previous_tab")

    if re.match(r"^(?:refresh|reload)(?: (?:the )?(?:page|tab|window|screen))?$", text):
        pyautogui.press("f5")
        return t("windows.refreshing")

    if re.match(r"^go back(?: page)?$", text):
        _hotkey("alt", "left")
        return t("windows.back")

    if re.match(r"^go forward(?: page)?$", text):
        _hotkey("alt", "right")
        return t("windows.forward")

    # --------------------------------------------------------
    # SCROLL & ZOOM
    # --------------------------------------------------------

    match = re.match(r"^scroll (up|down)(?: (?:by )?(\d{1,2}))?$", text)

    if match:
        amount = int(match.group(2) or 5)
        pyautogui.scroll(amount if match.group(1) == "up" else -amount)
        return t("session.done")

    if text == "zoom in":
        _hotkey("ctrl", "+")
        return t("windows.zoom_in")

    if text == "zoom out":
        _hotkey("ctrl", "-")
        return t("windows.zoom_out")

    # --------------------------------------------------------
    # FULL SCREEN  (F11 — never a brightness level, never an app)
    # --------------------------------------------------------

    if re.match(
        r"^(?:(?:enter|go|switch|come|turn)(?: in| to| on)? "
        r"|make (?:it |this |the window |the screen |the video )?"
        r"|exit |leave |close )?"
        r"full ?screen(?: mode)?$",
        text,
    ):
        pyautogui.press("f11")
        return t("windows.fullscreen")

    return None


def name():
    return "windows"
