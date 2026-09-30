"""
============================================================
 SKILL: APPS
============================================================
 Open / close any program, folder or Windows settings page.

 Opening an app by name, in order:
   built-in tables -> Start Menu shortcut -> whatever Windows can resolve.
 Every launch is reported from what actually started, so LYRA never claims
 to have opened something it did not.
============================================================
"""

import os
import re
import subprocess
from pathlib import Path

OPEN_APPS = {
    "notepad": "notepad",
    "calculator": "calc",
    "calc": "calc",
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "firefox": "firefox",
    "brave": "brave",
    "opera": "opera",
    "file explorer": "explorer",
    "explorer": "explorer",
    "this pc": "explorer",
    "my computer": "explorer",
    "control panel": "control",
    "task manager": "taskmgr",
    "cmd": "cmd",
    "command prompt": "cmd",
    "powershell": "powershell",
    "terminal": "wt",
    "paint": "mspaint",
    "wordpad": "write",
    "snipping tool": "snippingtool",
    "camera": "microsoft.windows.camera:",
    "vs code": "code",
    "visual studio code": "code",
    "vscode": "code",
    "spotify": "spotify",
    "whatsapp": "whatsapp",
    "telegram": "telegram",
    "discord": "discord",
    "steam": "steam",
    "vlc": "vlc",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "outlook": "outlook",
}

OPEN_SETTINGS = {
    "settings": "ms-settings:",
    "pc settings": "ms-settings:",
    "windows settings": "ms-settings:",
    "bluetooth settings": "ms-settings:bluetooth",
    "wifi settings": "ms-settings:network-wifi",
    "network settings": "ms-settings:network",
    "display settings": "ms-settings:display",
    "sound settings": "ms-settings:sound",
    "battery settings": "ms-settings:batterysaver",
    "storage settings": "ms-settings:storagesense",
    "update settings": "ms-settings:windowsupdate",
    "privacy settings": "ms-settings:privacy",
}

OPEN_FOLDERS = {
    "downloads": "shell:Downloads",
    "documents": "shell:Personal",
    "pictures": "shell:My Pictures",
    "music": "shell:My Music",
    "videos": "shell:My Video",
    "desktop": "shell:Desktop",
    "recycle bin": "shell:RecycleBinFolder",
}

CLOSE_EXES = {
    "chrome": ["chrome.exe"],
    "google chrome": ["chrome.exe"],
    "edge": ["msedge.exe"],
    "firefox": ["firefox.exe"],
    "notepad": ["notepad.exe"],
    "calculator": ["CalculatorApp.exe", "Calculator.exe"],
    "spotify": ["Spotify.exe"],
    "vs code": ["Code.exe"],
    "vscode": ["Code.exe"],
    "visual studio code": ["Code.exe"],
    "vlc": ["vlc.exe"],
    "steam": ["steam.exe"],
    "discord": ["Discord.exe"],
    "telegram": ["Telegram.exe"],
    "whatsapp": ["WhatsApp.exe"],
    "word": ["WINWORD.EXE"],
    "excel": ["EXCEL.EXE"],
    "powerpoint": ["POWERPNT.EXE"],
    "outlook": ["OUTLOOK.EXE"],
    "task manager": ["Taskmgr.exe"],
    "cmd": ["cmd.exe"],
    "command prompt": ["cmd.exe"],
    "powershell": ["powershell.exe", "pwsh.exe"],
    "paint": ["mspaint.exe"],
    "calculator app": ["CalculatorApp.exe", "Calculator.exe"],
}

_OPEN_RE = re.compile(
    r"^(?:please )?(?:open|launch|start|run)\s+(?:the |my |up )?(.+?)$"
)
# The raw (un-normalized) utterance may carry punctuation Whisper kept,
# e.g. "open, brave and" — tolerate it between the verb and the name so
# the launch attempt always uses the words the user really said.
_OPEN_RE_RAW = re.compile(
    r"^(?:please\s+)?(?:open|launch|start|run)[\s,]+(?:the |my |up )?(.+?)$",
    re.IGNORECASE,
)
_CLOSE_RE = re.compile(
    r"^(?:please )?(?:close|kill|quit|exit|terminate)\s+(?:the |my )?(.+?)$"
)

# Trailing conjunctions from run-on speech: "open brave and" -> "brave".
_TRAILING_CONJUNCTION = re.compile(r"(?:\s+(?:and|then))+$")

# "full screen" is a window state toggled with F11 (windows skill),
# never an app to close or open.
_FULLSCREEN_NAMES = {"full screen", "fullscreen", "full screen mode", "fullscreen mode"}

# Start Menu programs live here, per user and machine-wide.
_START_MENU_SUBPATH = ("Microsoft", "Windows", "Start Menu", "Programs")

# A Start Menu shortcut carries the real display name ("DaVinci Resolve.lnk"),
# which is the only way to open an app Windows has no App Paths key for.
# These words mark maintenance entries that must never be launched by accident.
_SHORTCUT_BLACKLIST = ("uninstall", "remove ", "repair", "setup", "update")

# Run-on speech: "open notepad and tell me what is going on" is one app plus
# a chat question, while "open notepad and write about india" is a multi-step
# task the planner owns. Only a conversational tail may be split off.
_CONVERSATIONAL_TAILS = (
    "tell me", "say ", "ask ", "explain", "answer", "read me", "remind me",
    "let me", "show me", "what ", "why ", "how ", "when ", "where ", "who ",
    "can you", "could you", "would you", "will you", "do you", "does ",
    "check ", "find out", "describe", "talk ", "give me", "is it", "are ",
)

# "and then" is one step boundary, not two.
_RUN_ON_SPLIT = re.compile(r"\s+(?:and\s+then|and|then)\s+")


def _clean_app_name(name):
    """Strip polite tails and dangling conjunctions from a spoken app name."""
    name = re.sub(r"\s+(please|now|for me)$", "", name.strip()).strip()
    name = _TRAILING_CONJUNCTION.sub("", name).strip()
    return name


def _split_run_on(name):
    """Split run-on speech into (app name, tail); the tail is "" when clean."""
    match = _RUN_ON_SPLIT.search(name)
    if not match:
        return name, ""
    return name[:match.start()].strip(), name[match.end():].strip()


def _is_conversational_tail(tail):
    """True for "tell me what is going on" — chat, not a second PC step."""
    tail = tail.strip().lower()
    return any(tail.startswith(marker) for marker in _CONVERSATIONAL_TAILS)


def _start_menu_roots():
    """The Start Menu program folders that exist on this machine."""
    roots = []
    for env in ("APPDATA", "PROGRAMDATA"):
        value = os.environ.get(env)
        if not value:
            continue
        root = Path(value).joinpath(*_START_MENU_SUBPATH)
        if root.is_dir() and root not in roots:
            roots.append(root)
    return roots


def _pretty_name(name):
    """A comparable form of a name: lowercase letters, digits and spaces."""
    return re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()


def _find_start_menu_app(name):
    """
    Find the Start Menu shortcut for a spoken app name.

    Uninstallers, repairs, setups and updaters are skipped: "open davinci
    resolve" must never launch "Uninstall DaVinci Resolve.lnk". Returns the
    shortcut Path, or None when nothing close enough exists.
    """

    wanted = _pretty_name(name)
    if not wanted:
        return None

    wanted_words = wanted.split()
    best = None
    best_score = 0

    for root in _start_menu_roots():
        try:
            shortcuts = list(root.rglob("*.lnk"))
        except OSError:
            continue

        for shortcut in shortcuts:
            stem = shortcut.stem
            if any(word in stem.lower() for word in _SHORTCUT_BLACKLIST):
                continue

            clean = _pretty_name(stem)
            if clean == wanted:
                score = 3
            elif wanted_words and set(wanted_words) <= set(clean.split()):
                score = 2
            elif wanted in clean or clean in wanted:
                score = 1
            else:
                score = 0

            if score == 0:
                continue
            if best is None or score > best_score or (
                score == best_score and len(stem) < len(best.stem)
            ):
                best = shortcut
                best_score = score

    return best


def _open_or_report(target, pretty):
    """Start the target; never claim success if nothing started."""
    try:
        _start(target)
    except OSError:
        return f"I couldn't find an app called {pretty}."
    return f"Opening {pretty}."


def open_by_name(name):
    """
    Open an app, folder, drive or settings page by spoken name.

    Returns the reply to speak, or None when the name is not a single
    openable thing. Exposed so a name repair ("no, I meant Notepad") can
    re-use exactly the same lookup chain.
    """

    name = _clean_app_name(name)

    if not name:
        return None

    if " and " in name or " then " in name:
        return None

    # settings pages
    if name in OPEN_SETTINGS:
        return _open_or_report(OPEN_SETTINGS[name], _pretty(name))

    # folders
    if name in OPEN_FOLDERS:
        return _open_or_report(OPEN_FOLDERS[name], name)

    # drive letters: "open c drive"
    drive = re.match(r"^([a-z]) drive$", name)

    if drive:
        return _open_or_report(
            drive.group(1).upper() + ":\\", f"{drive.group(1).upper()} drive"
        )

    # known apps
    if name in OPEN_APPS:
        return _open_or_report(OPEN_APPS[name], _pretty(name))

    # anything else Windows has actually installed: its Start Menu shortcut
    shortcut = _find_start_menu_app(name)

    if shortcut is not None:
        return _open_or_report(str(shortcut), shortcut.stem)

    # last resort — let Windows resolve the name itself (search results, App
    # Paths entries, document types). Launch first, report second: never say
    # "Opening..." unless something was actually started.
    return _open_or_report(name, name)


def _start(target):
    """Delegate one target to Windows shell activation without shell parsing."""
    if os.name == "nt":
        os.startfile(target)
    else:
        # This is a single executable/target argument, never a shell command.
        subprocess.Popen(
            [target], shell=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )


def _pretty(name):
    return name.replace("ms ", "").title()


def handle(text, raw=None):

    text = text.strip()
    if not text:
        return None

    # --------------------------------------------------------
    # CLOSE APP
    # --------------------------------------------------------

    match = _CLOSE_RE.match(text)

    if match:
        name = re.sub(r"\s+(please|now)$", "", match.group(1)).strip()

        if name in ("this window", "the window", "this", "that window", "tab", "this tab", "the tab"):
            return None                      # window control skill handles these

        if name in _FULLSCREEN_NAMES:
            return None                      # F11 toggle — windows skill owns it

        exes = CLOSE_EXES.get(name)

        if not exes:
            exes = [name.replace(" ", "") + ".exe"]

        for exe in exes:
            result = subprocess.run(
                ["taskkill", "/F", "/IM", exe],
                capture_output=True,
            )

            if result.returncode == 0:
                return f"Closed {_pretty(name)}."

        return f"I couldn't find {name} running."

    # --------------------------------------------------------
    # OPEN APP / FOLDER / SETTINGS
    # --------------------------------------------------------

    match = _OPEN_RE.match(text)

    if not match:
        return None

    name = _clean_app_name(match.group(1))

    if not name:
        return None

    # Run-on speech. "open notepad and tell me what is going on" opens
    # Notepad and answers the question in chat. "open notepad and write
    # about india" is a multi-step task for the planner, not an app called
    # "notepad and write about india".
    head, tail = _split_run_on(name)

    if tail:
        if not _is_conversational_tail(tail):
            return None
        name = head
        if not name:
            return None

    # The raw (un-normalized) utterance may carry punctuation Whisper kept,
    # e.g. "open, brave and" — use the words the user really said whenever
    # they still name a single app.
    raw_match = _OPEN_RE_RAW.match((raw or text).strip())

    if raw_match:
        raw_name = _clean_app_name(raw_match.group(1))
        if raw_name and " and " not in raw_name and " then " not in raw_name:
            name = raw_name

    return open_by_name(name)


def name():
    return "apps"
