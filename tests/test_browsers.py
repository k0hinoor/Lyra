"""
============================================================
 TESTS — lyra/browsers.py
============================================================
 Named-browser lookup and launch. Windows registry access is
 faked; nothing starts a real browser.
============================================================
"""

import sys
import types

import pytest

from lyra import browsers


# ------------------------------------------------------------
# URL SAFETY
# ------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "https://www.youtube.com",
    "http://example.com/path?q=1",
    "https://mail.google.com",
])
def test_safe_urls_are_accepted(url):
    assert browsers.is_safe_url(url)


@pytest.mark.parametrize("url", [
    "javascript:alert(1)",
    "JavaScript:alert(1)",
    "file:///C:/Windows/system.ini",
    "data:text/html,<script>x</script>",
    "ftp://example.com/file",
    "https://user:pass@example.com",      # embedded credentials
    "https://user@example.com",
    "https://",                            # no host
    "not a url",
    "",
    "https://example.com/a b",             # whitespace
    "https://example.com/\x00",            # control char
    12345,
    None,
])
def test_unsafe_urls_are_rejected(url):
    assert not browsers.is_safe_url(url)


# ------------------------------------------------------------
# LOOKUP
# ------------------------------------------------------------

class FakeWinreg:
    """Just enough of winreg for the App Paths lookup."""

    HKEY_LOCAL_MACHINE = "HKLM"
    HKEY_CURRENT_USER = "HKCU"

    def __init__(self, entries=None):
        self.entries = entries or {}

    class _Key:
        def __init__(self, value):
            self._value = value

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def OpenKey(self, hive, sub_key):
        if (hive, sub_key) in self.entries:
            return self._Key(self.entries[(hive, sub_key)])
        raise OSError("key not found")

    def QueryValueEx(self, key, name):
        return key._value, 1


def test_app_paths_registry_wins(monkeypatch, tmp_path):
    exe = tmp_path / "brave.exe"
    exe.write_bytes(b"MZ")

    fake = FakeWinreg({
        (FakeWinreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\brave.exe"): str(exe),
    })
    monkeypatch.setitem(sys.modules, "winreg", fake)

    assert browsers._find_in_app_paths("brave.exe") == exe


def test_registry_miss_falls_back_to_standard_folders(monkeypatch, tmp_path):
    chrome_dir = tmp_path / "Google" / "Chrome" / "Application"
    chrome_dir.mkdir(parents=True)
    exe = chrome_dir / "chrome.exe"
    exe.write_bytes(b"MZ")

    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    assert browsers._find_browser_on_windows("chrome", "chrome.exe") == exe


def test_windows_lookup_returns_none_when_nothing_is_installed(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "winreg", FakeWinreg())
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    assert browsers._find_browser_on_windows("brave", "brave.exe") is None


def test_an_unknown_browser_has_no_path():
    assert browsers.find_browser("netscape") is None
    assert browsers.find_browser("") is None


# ------------------------------------------------------------
# LAUNCH — argument list, never a shell
# ------------------------------------------------------------

def test_launch_uses_an_argument_list(monkeypatch, tmp_path):
    exe = tmp_path / "brave.exe"
    exe.write_bytes(b"MZ")

    monkeypatch.setattr(browsers, "find_browser", lambda name: exe)

    spawned = []
    monkeypatch.setattr(
        browsers.subprocess, "Popen",
        lambda command, **kwargs: spawned.append((command, kwargs)),
    )

    assert browsers.launch_browser("brave", "https://www.youtube.com")

    (command, kwargs), = spawned
    assert command == [str(exe), "https://www.youtube.com"]
    assert kwargs.get("shell") is False


def test_launch_without_a_url_opens_the_home_page(monkeypatch, tmp_path):
    monkeypatch.setattr(browsers, "find_browser", lambda name: tmp_path / "brave.exe")
    spawned = []
    monkeypatch.setattr(
        browsers.subprocess, "Popen",
        lambda command, **kwargs: spawned.append(command),
    )

    assert browsers.launch_browser("brave")
    assert spawned == [[str(tmp_path / "brave.exe")]]


def test_launch_of_a_missing_browser_returns_false(monkeypatch):
    monkeypatch.setattr(browsers, "find_browser", lambda name: None)
    assert browsers.launch_browser("brave", "https://x.com") is False


# ------------------------------------------------------------
# OPEN_URL
# ------------------------------------------------------------

def test_open_url_uses_the_named_browser(monkeypatch):
    launched = []
    monkeypatch.setattr(
        browsers, "launch_browser",
        lambda name, url=None: launched.append((name, url)) is True,
    )

    assert browsers.open_url("https://www.youtube.com", "brave")
    assert launched == [("brave", "https://www.youtube.com")]


def test_open_url_falls_back_to_the_default_browser(monkeypatch):
    monkeypatch.setattr(browsers, "launch_browser", lambda name, url=None: False)
    opened = []
    monkeypatch.setattr(browsers.webbrowser, "open", opened.append)

    assert browsers.open_url("https://www.youtube.com", "brave")
    assert opened == ["https://www.youtube.com"]


def test_open_url_refuses_unsafe_urls(monkeypatch):
    launched = []
    opened = []
    monkeypatch.setattr(
        browsers, "launch_browser",
        lambda name, url=None: launched.append(url) is True,
    )
    monkeypatch.setattr(browsers.webbrowser, "open", opened.append)

    for url in ("javascript:alert(1)", "file:///c:/x", "data:text/html,x",
                "https://user:pass@x.com"):
        assert browsers.open_url(url) is False

    assert launched == []
    assert opened == []
