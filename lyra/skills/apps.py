"""
============================================================
 SKILL: APPS
============================================================
 Open / close any program, folder or Windows settings page.
============================================================
"""

import os
import re
import subprocess

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


def _clean_app_name(name):
    """Strip polite tails and dangling conjunctions from a spoken app name."""
    name = re.sub(r"\s+(please|now|for me)$", "", name.strip()).strip()
    name = _TRAILING_CONJUNCTION.sub("", name).strip()
    return name


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

    # Run-on speech ("open notepad and write about india") is a multi-step
    # task for the planner, not one app called "notepad and write...".
    if " and " in name or " then " in name:
        return None

    def _open_or_report(target, pretty):
        """Start the target; never claim success if nothing started."""
        try:
            _start(target)
        except OSError:
            return f"I couldn't find an app called {pretty}."
        return f"Opening {pretty}."

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

    # unknown — let Windows try to resolve it (installed apps, searches).
    # Launch first, report second: never say "Opening..." unless something
    # was actually started.
    raw_match = _OPEN_RE_RAW.match((raw or text).strip())

    if raw_match:
        display_name = _clean_app_name(raw_match.group(1)) or name
    else:
        display_name = name

    if " and " in display_name or " then " in display_name:
        return None

    # os.startfile raises FileNotFoundError for names Windows can't open
    return _open_or_report(display_name, display_name)


def name():
    return "apps"
