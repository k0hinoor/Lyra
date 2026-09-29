"""
============================================================
 LYRA BROWSERS
============================================================
 Launch a named browser (brave, chrome, edge, firefox) with
 a URL as an argument list — never through a shell. The
 executable is found via the Windows App Paths registry key
 first, then standard install folders. Outside Windows a
 plain PATH lookup is used so development machines work too.
============================================================
"""

import logging
import os
import shutil
import subprocess
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

log = logging.getLogger(__name__)

SUPPORTED_BROWSERS = ("brave", "chrome", "edge", "firefox")

BROWSER_EXES = {
    "brave": "brave.exe",
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
    "firefox": "firefox.exe",
}

_PRETTY = {"brave": "Brave", "chrome": "Chrome", "edge": "Edge", "firefox": "Firefox"}


def pretty_name(browser):
    return _PRETTY.get(browser, browser.title())


def _env_dir(name, fallback=""):
    return os.environ.get(name, fallback)


def _standard_install_dirs(browser):
    """Usual install folders, checked in order after the registry."""

    program_files = _env_dir("ProgramFiles", r"C:\Program Files")
    program_files_x86 = _env_dir("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local_app_data = _env_dir("LOCALAPPDATA")

    dirs = {
        "brave": [
            Path(program_files) / "BraveSoftware" / "Brave-Browser" / "Application",
            Path(program_files_x86) / "BraveSoftware" / "Brave-Browser" / "Application",
        ],
        "chrome": [
            Path(program_files) / "Google" / "Chrome" / "Application",
            Path(program_files_x86) / "Google" / "Chrome" / "Application",
        ],
        "edge": [
            Path(program_files_x86) / "Microsoft" / "Edge" / "Application",
            Path(program_files) / "Microsoft" / "Edge" / "Application",
        ],
        "firefox": [
            Path(program_files) / "Mozilla Firefox",
            Path(program_files_x86) / "Mozilla Firefox",
        ],
    }
    candidates = dirs.get(browser, [])
    if local_app_data:
        if browser == "brave":
            candidates.append(
                Path(local_app_data) / "BraveSoftware" / "Brave-Browser" / "Application"
            )
        elif browser == "chrome":
            candidates.append(Path(local_app_data) / "Google" / "Chrome" / "Application")
    return candidates


def _find_in_app_paths(exe_name):
    """Windows App Paths registry lookup (HKLM then HKCU)."""

    try:
        import winreg
    except ImportError:
        return None

    sub_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths" + "\\" + exe_name

    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, sub_key) as key:
                value, _type = winreg.QueryValueEx(key, None)
                if value:
                    path = Path(str(value).strip().strip('"'))
                    if path.is_file():
                        return path
        except OSError:
            continue

    return None


def _find_browser_on_windows(browser, exe_name):
    """Registry App Paths first, then the standard install folders."""

    found = _find_in_app_paths(exe_name)
    if found is not None:
        return found

    for folder in _standard_install_dirs(browser):
        candidate = folder / exe_name
        if candidate.is_file():
            return candidate

    return None


def find_browser(browser):
    """Path of the browser executable, or None when not installed."""

    browser = (browser or "").strip().casefold()
    exe_name = BROWSER_EXES.get(browser)

    if exe_name is None:
        return None

    if os.name == "nt":
        return _find_browser_on_windows(browser, exe_name)

    # Development machines: a PATH lookup is the sensible equivalent.
    found = shutil.which(exe_name) or shutil.which(browser)
    return Path(found) if found else None


def launch_browser(browser, url=None):
    """Start the named browser, optionally at a URL. Argument list only."""

    exe = find_browser(browser)

    if exe is None:
        log.warning("Browser %r was not found on this PC", browser)
        return False

    command = [str(exe)]
    if url:
        command.append(url)

    try:
        subprocess.Popen(
            command,
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as error:
        log.warning("Could not start %s: %s", browser, error)
        return False

    return True


def is_safe_url(url):
    """Only http/https, with a host, no credentials, no surprises."""

    if not isinstance(url, str) or not url.strip() or len(url) > 2048:
        return False
    if any(char.isspace() or ord(char) < 32 for char in url):
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False              # blocks javascript:, file:, data:, ftp: ...
    if not parsed.netloc:
        return False
    if "@" in parsed.netloc or parsed.username or parsed.password:
        return False              # no embedded credentials
    return True


def open_url(url, browser=None):
    """Open a validated URL in the named browser, or the system default.

    Returns True when the URL was handed to a browser.
    """

    if not is_safe_url(url):
        log.warning("Refusing to open unsafe URL: %.120s", url)
        return False

    name = (browser or "").strip().casefold()

    if name in SUPPORTED_BROWSERS and launch_browser(name, url):
        return True

    try:
        webbrowser.open(url)
    except Exception:
        log.exception("Could not open URL in the default browser")
        return False
    return True
