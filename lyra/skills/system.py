"""
============================================================
 SKILL: SYSTEM
============================================================
 Time, date, battery, CPU/RAM, disk, IP, Wi-Fi password,
 screenshots, lock, sleep, restart, shutdown, recycle bin,
 uptime. Dangerous actions ask for confirmation.
============================================================
"""

import ctypes
import datetime
import re
import socket
import subprocess
import time

from .. import config
from ..messages import hindi_date, hindi_time, is_hindi, t
from .base import Confirmation

try:
    import psutil
    _PSUTIL_OK = True
except Exception:
    _PSUTIL_OK = False

try:
    import pyautogui
    pyautogui.PAUSE = 0
    _PYAUTOGUI_OK = True
except Exception:
    _PYAUTOGUI_OK = False

IS_WINDOWS = __import__("sys").platform.startswith("win")

# "open storage settings" and "open battery settings" contain words this
# skill knows ("storage", "battery"), but they are not questions — they are
# requests for a Windows Settings page, which the apps skill owns. Without
# this guard the user gets a disk-space report instead of the page.
_OPENS_SOMETHING = re.compile(r"^(?:open|launch|start|run|visit|go to)\b")
_WANTS_SETTINGS = re.compile(r"\bsettings\b")


# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------

def _local_ip():
    """Local network IP without sending any traffic."""

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "127.0.0.1"
    finally:
        sock.close()

    return ip


def _wifi_password():

    try:
        # current network
        interfaces = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True,
        ).stdout

        ssid_match = re.search(r"^\s*SSID\s*:\s*(.+)$", interfaces, re.MULTILINE)

        if not ssid_match:
            return None, None

        ssid = ssid_match.group(1).strip()

        # password for it
        profile = subprocess.run(
            ["netsh", "wlan", "show", "profile", f"name={ssid}", "key=clear"],
            capture_output=True, text=True,
        ).stdout

        key_match = re.search(r"^\s*Key Content\s*:\s*(.+)$", profile, re.MULTILINE)

        if not key_match:
            return ssid, None

        return ssid, key_match.group(1).strip()

    except Exception:
        return None, None


def _human_duration(seconds):

    seconds = int(seconds)
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    parts = []

    if days:
        parts.append(t("duration.day" if days == 1 else "duration.days", n=days))
    if hours:
        parts.append(t("duration.hour" if hours == 1 else "duration.hours", n=hours))
    if minutes and not days:
        parts.append(t("duration.minute" if minutes == 1 else "duration.minutes", n=minutes))

    return ", ".join(parts) if parts else t("duration.under_minute")


def _do_shutdown():
    subprocess.run(["shutdown", "/s", "/t", str(config.SHUTDOWN_DELAY)])


def _do_restart():
    subprocess.run(["shutdown", "/r", "/t", str(config.SHUTDOWN_DELAY)])


def _do_sleep():
    subprocess.run(
        ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
        capture_output=True,
    )


def _do_empty_recycle_bin():
    subprocess.run(
        ["powershell", "-Command",
         "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
        capture_output=True,
    )


# ------------------------------------------------------------
# HANDLE
# ------------------------------------------------------------

def handle(text, raw=None):

    text = text.strip()

    if not text:
        return None

    # Opening apps / folders / settings pages belongs to the apps and web
    # skills, however many words below happen to match this one.
    if _OPENS_SOMETHING.match(text) or _WANTS_SETTINGS.search(text):
        return None

    # --------------------------------------------------------
    # TIME
    # --------------------------------------------------------
    # Conversational fillers ("so", "and", "well") are peeled off by
    # strip_politeness() before this runs.

    if re.match(
        r"^(?:what(?:'s| is)? (?:the )?time"
        r"|what time is it"
        r"|(?:please )?tell me the time"
        r"|(?:the |what is the |whats the )?current time"
        r"|(?:the |give me the )?time"
        r"|(?:do you have|have) (?:the )?time"
        r")(?: right now| now| please| today)?$",
        text,
    ):
        now = datetime.datetime.now()
        if is_hindi():
            return t("system.time", time=hindi_time(now))
        return t("system.time", time=now.strftime("%I:%M %p").lstrip("0"))

    # --------------------------------------------------------
    # DATE / DAY
    # --------------------------------------------------------

    if re.match(
        r"^(?:what(?:'s| is)? (?:the )?date|what date is it|what day is it|"
        r"date|day)(?: today| is it| now)?$",
        text,
    ):
        now = datetime.datetime.now()
        if is_hindi():
            return t("system.date", date=hindi_date(now))
        return t("system.date", date=now.strftime("%A, %d %B %Y").lstrip("0"))

    # --------------------------------------------------------
    # BATTERY
    # --------------------------------------------------------

    if "battery" in text and re.search(r"\bbattery\b", text):

        if not _PSUTIL_OK:
            return t("system.no_psutil_battery")

        battery = psutil.sensors_battery()

        if battery is None:
            return t("system.no_battery")

        percent = round(battery.percent)
        state = t("system.charging") if battery.power_plugged else t("system.on_battery")
        reply = t("system.battery", percent=percent, state=state)

        if battery.secsleft not in (
            psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN
        ) and battery.secsleft and battery.secsleft > 0:
            reply += t("system.battery_left", duration=_human_duration(battery.secsleft))

        return reply

    # --------------------------------------------------------
    # CPU / RAM / SYSTEM STATUS
    # --------------------------------------------------------

    if re.match(
        r"^(?:how is my (?:pc|computer|system)|system status|pc status|"
        r"cpu (?:usage)?|ram (?:usage)?|memory usage|performance|"
        r"cpu and ram(?: usage)?|system usage|"
        r"how much (?:ram|memory|cpu)(?: usage)?"
        r"(?: am i using| do i have| is in use| is being used)?)$",
        text,
    ):
        if not _PSUTIL_OK:
            return t("system.no_psutil_stats")

        cpu = psutil.cpu_percent(interval=0.4)
        ram = psutil.virtual_memory().percent

        return t("system.stats", cpu=round(cpu), ram=round(ram))

    # --------------------------------------------------------
    # DISK SPACE
    # --------------------------------------------------------

    if re.search(r"\b(disk space|storage)\b", text):

        if not _PSUTIL_OK:
            return t("system.no_psutil_disk")

        for root in ("C:/", "/"):
            try:
                usage = psutil.disk_usage(root)
                free_gb = round(usage.free / (1024 ** 3))
                total_gb = round(usage.total / (1024 ** 3))
                return t("system.disk", free=free_gb, total=total_gb)
            except Exception:
                continue

        return t("system.disk_failed")

    # --------------------------------------------------------
    # IP ADDRESS
    # --------------------------------------------------------

    if re.search(r"\b(ip address|my ip|ip)\b$", text) or text in ("ip", "my ip"):
        return t("system.ip", ip=_local_ip().replace('.', ' '))

    # --------------------------------------------------------
    # WI-FI PASSWORD
    # --------------------------------------------------------

    if re.search(r"\bwifi password\b|\bwi fi password\b|\bwi fi\b.*password", text):

        ssid, password = _wifi_password()

        if ssid is None:
            return t("system.wifi_failed")

        if password is None:
            return t("system.wifi_no_password", ssid=ssid)

        return t("system.wifi_password", ssid=ssid, password=password)

    # --------------------------------------------------------
    # UPTIME
    # --------------------------------------------------------

    if re.match(r"^(?:how long have (?:you|we) been (?:on|up)|uptime|system uptime)$", text):

        if not _PSUTIL_OK:
            return t("system.no_psutil_uptime")

        uptime = time.time() - psutil.boot_time()
        return t("system.uptime", duration=_human_duration(uptime))

    # --------------------------------------------------------
    # SCREENSHOT
    # --------------------------------------------------------

    if re.match(r"^(?:take )?(?:a )?screen ?shot(?: for me)?(?: of the screen)?(?: now)?$", text):

        if not _PYAUTOGUI_OK:
            return t("system.no_pyautogui_screenshot")

        try:
            config.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = config.SCREENSHOT_DIR / f"Lyra_{stamp}.png"

            pyautogui.screenshot(str(path))

            return t("system.screenshot_saved")
        except Exception as e:
            print(f"Screenshot error: {e}")
            return t("system.screenshot_failed")

    # --------------------------------------------------------
    # LOCK
    # --------------------------------------------------------

    if re.match(r"^lock(?: my| the)? (?:pc|computer|screen|windows|system)$", text):

        if not IS_WINDOWS:
            return t("system.lock_windows_only")

        def _lock():
            ctypes.windll.user32.LockWorkStation()

        _lock()
        return t("system.locked")

    # --------------------------------------------------------
    # CANCEL SHUTDOWN
    # --------------------------------------------------------

    if re.match(r"^cancel (?:the )?(?:shutdown|restart|turn off)$", text):

        if not IS_WINDOWS:
            return t("system.windows_only")

        result = subprocess.run(["shutdown", "/a"], capture_output=True)

        if result.returncode == 0:
            return t("system.shutdown_cancelled")
        return t("system.no_shutdown")

    # --------------------------------------------------------
    # SHUTDOWN  (needs confirmation)
    # --------------------------------------------------------

    if re.match(
        r"^(?:shut ?down|turn off|power off)"
        r"(?: (?:the|my)? ?(?:pc|computer|system|windows|machine))?(?: now| please)?$",
        text,
    ):

        if not IS_WINDOWS:
            return t("system.windows_only")

        return Confirmation(
            prompt=t("system.shutdown_prompt", seconds=config.SHUTDOWN_DELAY),
            action=_do_shutdown,
            say_on_confirm=t("system.shutdown_confirm", seconds=config.SHUTDOWN_DELAY),
        )

    # --------------------------------------------------------
    # RESTART  (needs confirmation)
    # --------------------------------------------------------

    if re.match(
        r"^(?:restart|reboot|reset)"
        r"(?: (?:the|my)? ?(?:pc|computer|system|windows|machine))?(?: now| please)?$",
        text,
    ):

        if not IS_WINDOWS:
            return t("system.windows_only")

        return Confirmation(
            prompt=t("system.restart_prompt", seconds=config.SHUTDOWN_DELAY),
            action=_do_restart,
            say_on_confirm=t("system.restart_confirm", seconds=config.SHUTDOWN_DELAY),
        )

    # --------------------------------------------------------
    # PC SLEEP  (needs confirmation)
    # --------------------------------------------------------
    # "put my PC to sleep", "sleep mode", "put my windows in sleep
    # mode" — and the common Whisper mishearing "put my windows AND
    # sleep mode". A bare "sleep" is NOT a PC-sleep request (it is the
    # assistant's own go-to-sleep phrase), so every form here either
    # ends in "mode" or spells "to sleep".

    if (
        re.match(
            r"^(?:put |switch |enable |turn on |set )?"
            r"(?:the |my )?"
            r"(?:pc|computer|system|windows|machine|laptop)?"
            r" ?(?:to |in |into |on |and )?"
            r"sleep ?mode(?:s)?"
            r"(?: now| please)?$",
            text,
        )
        or re.match(
            r"^(?:put )?(?:the |my )?(?:pc|computer|system|windows|machine|laptop)?"
            r" ?to sleep(?: now| please)?$",
            text,
        )
        or re.match(
            r"^(?:put |switch |set )?(?:the |my )?"
            r"(?:pc|computer|system|windows|machine|laptop)?"
            r" (?:in|into|and) sleep(?: mode)?(?: now| please)?$",
            text,
        )
        or text in ("sleep pc", "sleep the pc", "sleep my pc")
    ):

        if not IS_WINDOWS:
            return t("system.windows_only")

        return Confirmation(
            prompt=t("system.sleep_prompt"),
            action=_do_sleep,
            say_on_confirm=t("system.sleep_confirm"),
        )

    # --------------------------------------------------------
    # EMPTY RECYCLE BIN  (needs confirmation)
    # --------------------------------------------------------

    if re.match(r"^(?:empty|clear|clean) (?:the )?recycle bin$", text):

        return Confirmation(
            prompt=t("system.recycle_prompt"),
            action=_do_empty_recycle_bin,
            say_on_confirm=t("system.recycle_confirm"),
        )

    return None


def name():
    return "system"
