"""
============================================================
 TESTS — lyra/skills/system.py
============================================================
"""

import datetime
import re
import time
from types import SimpleNamespace

import pytest

from lyra import config
from lyra.skills import system
from lyra.skills.base import Confirmation

from conftest import FakeRun


# ------------------------------------------------------------
# TIME & DATE
# ------------------------------------------------------------

@pytest.mark.parametrize("text", ["what time is it", "what's the time", "time"])
def test_time(text):
    reply = system.handle(text)

    assert reply.startswith("It's ")
    assert reply.endswith(".")


def test_time_matches_the_clock():
    # matched loosely so it can't flake when the minute ticks over
    assert re.fullmatch(r"It's \d{1,2}:\d{2} (AM|PM)\.", system.handle("what time is it"))


@pytest.mark.parametrize("text", ["what's the date", "what date is it", "what day is it"])
def test_date(text):
    today = datetime.datetime.now().strftime("%A, %d %B %Y").lstrip("0")
    assert system.handle(text) == f"Today is {today}."


# ------------------------------------------------------------
# BATTERY
# ------------------------------------------------------------

def test_battery_charging(psutil_stub):
    psutil_stub.battery_at(80, plugged=True)
    assert system.handle("battery") == "Battery is at 80 percent and charging."


def test_battery_on_battery(psutil_stub):
    psutil_stub.battery_at(50, plugged=False)
    assert system.handle("battery") == "Battery is at 50 percent and on battery."


def test_battery_reports_time_left(psutil_stub):
    psutil_stub.battery_at(50, plugged=False, secsleft=5400)
    assert system.handle("battery") == (
        "Battery is at 50 percent and on battery. About 1 hour, 30 minutes left."
    )


def test_battery_without_a_battery(psutil_stub):
    psutil_stub.battery = None
    assert system.handle("battery") == "I couldn't find a battery — probably a desktop PC."


def test_battery_without_psutil(monkeypatch):
    monkeypatch.setattr(system, "_PSUTIL_OK", False)
    assert "psutil" in system.handle("battery")


# ------------------------------------------------------------
# SYSTEM STATUS
# ------------------------------------------------------------

@pytest.mark.parametrize("text", ["how is my pc", "cpu usage", "ram usage", "system status"])
def test_system_status(psutil_stub, text):
    psutil_stub.cpu = 12.4
    psutil_stub.ram = 45.6
    assert system.handle(text) == "CPU is at 12 percent, memory at 46 percent."


def test_system_status_without_psutil(monkeypatch):
    monkeypatch.setattr(system, "_PSUTIL_OK", False)
    assert "psutil" in system.handle("how is my pc")


@pytest.mark.parametrize("text", ["disk space", "how much storage do I have"])
def test_disk_space(psutil_stub, text):
    psutil_stub.disk_free_gb = 120
    psutil_stub.disk_total_gb = 512
    assert system.handle(text) == "The main drive has 120 gigabytes free, out of 512."


# ------------------------------------------------------------
# IP & WI-FI
# ------------------------------------------------------------

def test_local_ip_is_spoken_digit_by_digit(monkeypatch):
    monkeypatch.setattr(system, "_local_ip", lambda: "192.168.1.5")
    assert system.handle("what's my ip") == "Your local IP address is 192 168 1 5."


def test_wifi_password(monkeypatch):
    monkeypatch.setattr(system, "_wifi_password", lambda: ("HomeNet", "secret123"))
    assert system.handle("wifi password") == "The password for HomeNet is: secret123."


def test_wifi_without_a_stored_password(monkeypatch):
    monkeypatch.setattr(system, "_wifi_password", lambda: ("HomeNet", None))
    assert system.handle("what's my wifi password") == (
        "The network is HomeNet, but the password isn't stored on this PC."
    )


def test_wifi_when_not_connected(monkeypatch):
    monkeypatch.setattr(system, "_wifi_password", lambda: (None, None))
    assert system.handle("wifi password") == "I couldn't read the Wi-Fi details. Is Wi-Fi connected?"


# ------------------------------------------------------------
# UPTIME
# ------------------------------------------------------------

def test_uptime(psutil_stub):
    psutil_stub.boot = time.time() - 5400
    assert system.handle("uptime") == "The system has been up for 1 hour, 30 minutes."


@pytest.mark.parametrize("seconds, text", [
    (30, "less than a minute"),
    (600, "10 minutes"),
    (5400, "1 hour, 30 minutes"),
    (90000, "1 day, 1 hour"),
])
def test_human_duration(seconds, text):
    assert system._human_duration(seconds) == text


# ------------------------------------------------------------
# SCREENSHOT
# ------------------------------------------------------------

def test_screenshot(monkeypatch, autogui, tmp_path):
    monkeypatch.setattr(config, "SCREENSHOT_DIR", tmp_path / "shots")

    assert system.handle("take a screenshot") == "Screenshot saved to the Pictures folder."

    call = autogui.calls[-1]
    assert call[0] == "screenshot"
    assert call[1].startswith(str(tmp_path / "shots"))
    assert (tmp_path / "shots").is_dir()


def test_screenshot_without_pyautogui(monkeypatch):
    monkeypatch.setattr(system, "_PYAUTOGUI_OK", False)
    assert "pyautogui" in system.handle("take a screenshot")


# ------------------------------------------------------------
# LOCK
# ------------------------------------------------------------

def test_lock_calls_the_windows_api(monkeypatch):
    monkeypatch.setattr(system, "IS_WINDOWS", True)

    locked = []
    fake_ctypes = SimpleNamespace(
        windll=SimpleNamespace(user32=SimpleNamespace(LockWorkStation=lambda: locked.append(True)))
    )
    monkeypatch.setattr(system, "ctypes", fake_ctypes)

    assert system.handle("lock my pc") == "Locked. See you soon."
    assert locked == [True]


def test_lock_off_windows_is_refused(monkeypatch):
    monkeypatch.setattr(system, "IS_WINDOWS", False)
    assert system.handle("lock my pc") == "Locking only works on Windows."


# ------------------------------------------------------------
# DANGEROUS ACTIONS — CONFIRMATION
# ------------------------------------------------------------

@pytest.fixture
def shell(monkeypatch):
    def install(returncode=0):
        fake = FakeRun(returncode)
        monkeypatch.setattr(system.subprocess, "run", fake)
        return fake

    return install


@pytest.fixture(autouse=True)
def on_windows(monkeypatch):
    """Power commands are Windows-only; force that branch on every platform."""
    monkeypatch.setattr(system, "IS_WINDOWS", True)


@pytest.mark.parametrize("text, flag", [
    ("shutdown the pc", "/s"),
    ("turn off the computer", "/s"),
    ("restart", "/r"),
    ("reboot the pc", "/r"),
])
def test_power_commands_ask_for_confirmation(shell, text, flag):
    fake = shell()

    result = system.handle(text)

    assert isinstance(result, Confirmation)
    assert "confirm" in result.prompt.lower()
    assert fake.commands == [], "nothing may run before the user confirms"

    result.action()
    assert fake.commands == [["shutdown", flag, "/t", str(config.SHUTDOWN_DELAY)]]


def test_sleep_asks_for_confirmation(shell):
    fake = shell()
    result = system.handle("put the pc to sleep")

    assert isinstance(result, Confirmation)
    assert fake.commands == []

    result.action()
    assert fake.commands[0][0] == "rundll32.exe"


def test_empty_recycle_bin_asks_for_confirmation(shell):
    fake = shell()
    result = system.handle("empty the recycle bin")

    assert isinstance(result, Confirmation)
    assert "permanently" in result.prompt
    assert fake.commands == []

    result.action()
    assert fake.commands[0][0] == "powershell"


def test_confirmation_has_a_message_to_speak(shell):
    result = system.handle("shutdown the pc")
    assert result.say_on_confirm


def test_cancel_shutdown(shell):
    fake = shell()
    assert system.handle("cancel the shutdown") == "Shutdown cancelled."
    assert fake.commands == [["shutdown", "/a"]]


def test_cancel_shutdown_when_none_is_pending(shell):
    fake = shell(returncode=1)
    assert system.handle("cancel the shutdown") == "There was no shutdown to cancel."


def test_power_commands_off_windows_are_refused(monkeypatch, shell):
    monkeypatch.setattr(system, "IS_WINDOWS", False)
    assert system.handle("shutdown the pc") == "That only works on Windows."


# ------------------------------------------------------------
# NOT MINE
# ------------------------------------------------------------

@pytest.mark.parametrize("text", ["open notepad", "tell me a joke", "close chrome", ""])
def test_other_commands_are_left_alone(text):
    assert system.handle(text) is None
