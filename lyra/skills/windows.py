"""
============================================================
 SKILL: WINDOWS & TABS
============================================================
 Window management, tabs, scrolling, zoom.
============================================================
"""

import re
import time

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
        return "Minimized."

    if re.match(r"^maximize(?: this| the| current)? window$", text):
        pyautogui.hotkey("win", "up")
        return "Maximized."

    if re.match(r"^show (?:the )?desktop$", text):
        pyautogui.hotkey("win", "d")
        return "Showing desktop."

    if text in ("switch window", "alt tab", "next window", "change window"):
        _hotkey("alt", "tab")
        return "Switching."

    if text == "task view":
        pyautogui.hotkey("win", "tab")
        return "Opening task view."

    # --------------------------------------------------------
    # WINDOW LIFECYCLE
    # --------------------------------------------------------

    if re.match(r"^close (?:this |the |that )?window$", text):
        pyautogui.hotkey("alt", "f4")
        return "Closed window."

    # --------------------------------------------------------
    # TABS
    # --------------------------------------------------------

    if text == "new tab":
        pyautogui.hotkey("ctrl", "t")
        return "New tab."

    if text == "new window":
        pyautogui.hotkey("ctrl", "n")
        return "New window."

    if re.match(r"^close (?:this |the )?tab$", text):
        pyautogui.hotkey("ctrl", "w")
        return "Closed tab."

    if re.match(r"^(?:reopen|restore|undo close) (?:the )?tab$", text):
        pyautogui.hotkey("ctrl", "shift", "t")
        return "Reopened tab."

    if re.match(r"^(?:refresh|reload)(?: (?:the )?(?:page|tab|window|screen))?$", text):
        pyautogui.press("f5")
        return "Refreshing."

    if re.match(r"^go back(?: page)?$", text):
        _hotkey("alt", "left")
        return "Going back."

    if re.match(r"^go forward(?: page)?$", text):
        _hotkey("alt", "right")
        return "Going forward."

    # --------------------------------------------------------
    # SCROLL & ZOOM
    # --------------------------------------------------------

    match = re.match(r"^scroll (up|down)(?: (?:by )?(\d{1,2}))?$", text)

    if match:
        amount = int(match.group(2) or 5)
        pyautogui.scroll(amount if match.group(1) == "up" else -amount)
        return "Done."

    if text == "zoom in":
        _hotkey("ctrl", "+")
        return "Zooming in."

    if text == "zoom out":
        _hotkey("ctrl", "-")
        return "Zooming out."

    if text == "fullscreen":
        pyautogui.press("f11")
        return "Toggled fullscreen."

    return None


def name():
    return "windows"
