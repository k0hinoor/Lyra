"""
============================================================
 SKILL: APPS
============================================================
 Open / close any program, folder or Windows settings page.
============================================================
"""

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
_OPEN_RE_RAW = re.compile(
    r"^(?:please )?(?:open|launch|start|run)\s+(?:the |my |up )?(.+?)$",
    re.IGNORECASE,
)
_CLOSE_RE = re.compile(
    r"^(?:please )?(?:close|kill|quit|exit|terminate)\s+(?:the |my )?(.+?)$"
)


def _start(target):
    subprocess.Popen(
        f'start "" "{target}"',
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
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

    name = re.sub(r"\s+(please|now|for me)$", "", match.group(1)).strip()

    # settings pages
    if name in OPEN_SETTINGS:
        _start(OPEN_SETTINGS[name])
        return f"Opening {_pretty(name)}."

    # folders
    if name in OPEN_FOLDERS:
        _start(OPEN_FOLDERS[name])
        return f"Opening {name}."

    # drive letters: "open c drive"
    drive = re.match(r"^([a-z]) drive$", name)

    if drive:
        _start(drive.group(1).upper() + ":\\")
        return f"Opening {drive.group(1).upper()} drive."

    # known apps
    if name in OPEN_APPS:
        _start(OPEN_APPS[name])
        return f"Opening {_pretty(name)}."

    # unknown — let Windows try to resolve it (installed apps, searches)
    raw_match = _OPEN_RE_RAW.match((raw or text).strip())

    if raw_match:
        raw_name = re.sub(
            r"\s+(please|now|for me)$", "",
            raw_match.group(1).strip()
        )
        _start(raw_name)

    return f"Opening {name}."


def name():
    return "apps"
