"""
============================================================
 SKILL: TYPING & KEYBOARD
============================================================
 Type dictated text, press keys, hotkeys, clipboard.
============================================================
"""

import re

try:
    import pyautogui
    pyautogui.PAUSE = 0
    _PYAUTOGUI_OK = True
except Exception:
    _PYAUTOGUI_OK = False

try:
    import pyperclip
    _PYPERCLIP_OK = True
except Exception:
    _PYPERCLIP_OK = False

KEYS = {
    "enter": "enter", "return": "enter",
    "escape": "esc", "esc": "esc",
    "tab": "tab", "space": "space", "spacebar": "space", "space bar": "space",
    "backspace": "backspace", "delete": "delete", "del": "delete",
    "up": "up", "up arrow": "up", "down": "down", "down arrow": "down",
    "left": "left", "left arrow": "left", "right": "right", "right arrow": "right",
    "home": "home", "end": "end",
    "page up": "pageup", "page down": "pagedown",
    "insert": "insert", "print screen": "printscreen",
    "windows key": "win", "windows": "win", "win": "win",
    "comma": ",", "period": ".", "full stop": ".",
    "shift": "shift", "ctrl": "ctrl", "control": "ctrl", "alt": "alt",
}

for i in range(1, 13):
    KEYS[f"f{i}"] = f"f{i}"

# Multi-word names in KEYS ("page up", "up arrow", "print screen") need
# longest-first matching, so remember how many words the longest name has.
_LONGEST_KEY_NAME = max(len(name.split()) for name in KEYS)

_LEADING_ARTICLE = re.compile(r"^(?:the|a)\s+")
_TRAILING_KEY_NOUN = re.compile(r"\s+(?:key|button)$")


def _parse_keys(phrase):
    """
    "the page up key" -> (["pageup"], None)
    "control alt"     -> (["ctrl", "alt"], None)
    "ctrl c"          -> (None, "c")      single letters are shortcuts, not keys

    Multi-word names in KEYS ("page up", "up arrow", "print screen") are
    only reachable with longest-first matching — splitting the phrase on
    spaces turned them into nonsense combinations. Nothing is pressed
    until the whole phrase is understood.
    """

    words = phrase.split()
    keys = []
    index = 0

    while index < len(words):

        for span in range(min(_LONGEST_KEY_NAME, len(words) - index), 0, -1):

            key = KEYS.get(" ".join(words[index:index + span]))

            if key is not None:
                keys.append(key)
                index += span
                break

        else:
            return None, words[index]

    return keys, None


SHORTCUTS = {
    "copy": ("ctrl", "c"),
    "cut": ("ctrl", "x"),
    "paste": ("ctrl", "v"),
    "select all": ("ctrl", "a"),
    "undo": ("ctrl", "z"),
    "redo": ("ctrl", "y"),
    "save": ("ctrl", "s"),
    "find": ("ctrl", "f"),
    "print": ("ctrl", "p"),
    "new tab": ("ctrl", "t"),      # also handled by windows skill
    "screenshot selection": ("shift", "win", "s"),
}


def _do_hotkey(combo):
    pyautogui.hotkey(*combo)


# ------------------------------------------------------------
# HANDLE
# ------------------------------------------------------------

def handle(text, raw=None):

    text = text.strip()
    source = (raw or text).strip()

    if not text:
        return None

    # --------------------------------------------------------
    # TYPE DICTATED TEXT  (uses raw text to keep case/punctuation)
    # --------------------------------------------------------

    match = re.match(r"^type\s+(.+)$", source, re.IGNORECASE)

    if match:
        content = match.group(1).strip()

        if not _PYPERCLIP_OK or not _PYAUTOGUI_OK:
            return "Typing needs the pyautogui and pyperclip packages."

        # clipboard-paste = instant and supports every character
        pyperclip.copy(content)
        pyautogui.hotkey("ctrl", "v")

        return "Typed."

    # --------------------------------------------------------
    # PRESS KEY(S)
    # --------------------------------------------------------

    match = re.match(r"^press\s+(.+)$", text)

    if match:
        if not _PYAUTOGUI_OK:
            return "Key control needs the pyautogui package."

        phrase = match.group(1).strip()
        phrase = _LEADING_ARTICLE.sub("", phrase)
        phrase = _TRAILING_KEY_NOUN.sub("", phrase)

        if phrase in ("", "key", "button"):
            return None                 # "press the key" names no key at all

        combo, unknown = _parse_keys(phrase)

        if unknown is not None:
            return f"I don't know the {unknown} key."

        if not combo:
            return None

        if len(combo) == 1:
            pyautogui.press(combo[0])
        else:
            pyautogui.hotkey(*combo)

        return "Done."

    # --------------------------------------------------------
    # SHORTCUTS  (copy / paste / save ...)
    # --------------------------------------------------------

    if not _PYAUTOGUI_OK:
        return None

    if text in SHORTCUTS:
        _do_hotkey(SHORTCUTS[text])
        return "Done."

    # --------------------------------------------------------
    # CLIPBOARD
    # --------------------------------------------------------

    match = re.match(r"^(?:copy|put)\s+(.+?)\s+to (?:the )?clipboard$", text)

    if match:
        content = match.group(1).strip()

        if content in ("this", "it", "that", "selection"):
            if not _PYAUTOGUI_OK:
                return "Key control needs the pyautogui package."
            _do_hotkey(("ctrl", "c"))
            return "Copied."

        if not _PYPERCLIP_OK:
            return "Clipboard needs the pyperclip package."

        pyperclip.copy(content)
        return "Copied to clipboard."

    if re.match(r"^(?:read|show)(?: me)? (?:the |my )?clipboard$", text) \
            or re.match(r"^what(?:'s| is) in (?:the |my )?clipboard$", text):
        if not _PYPERCLIP_OK:
            return "Clipboard needs the pyperclip package."

        content = (pyperclip.paste() or "").strip()

        if not content:
            return "The clipboard is empty."

        return "Clipboard says: " + content[:250]

    if re.match(r"^clear (?:the |my )?clipboard$", text):
        if not _PYPERCLIP_OK:
            return "Clipboard needs the pyperclip package."

        pyperclip.copy("")
        return "Clipboard cleared."

    return None


def name():
    return "typing"
