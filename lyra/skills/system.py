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
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes and not days:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")

    return ", ".join(parts) if parts else "less than a minute"


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

    if re.match(r"^(?:what(?:'s| is)? the time|what time is it|time)(?: now| please)?$", text):
        now = datetime.datetime.now()
        return "It's " + now.strftime("%I:%M %p").lstrip("0") + "."

    # --------------------------------------------------------
    # DATE / DAY
    # --------------------------------------------------------

    if re.match(
        r"^(?:what(?:'s| is)? (?:the )?date|what date is it|what day is it|"
        r"date|day)(?: today| is it| now)?$",
        text,
    ):
        now = datetime.datetime.now()
        return "Today is " + now.strftime("%A, %d %B %Y").lstrip("0") + "."

    # --------------------------------------------------------
    # BATTERY
    # --------------------------------------------------------

    if "battery" in text and re.search(r"\bbattery\b", text):

        if not _PSUTIL_OK:
            return "Battery status needs the psutil package."

        battery = psutil.sensors_battery()

        if battery is None:
            return "I couldn't find a battery — probably a desktop PC."

        percent = round(battery.percent)
        state = "charging" if battery.power_plugged else "on battery"
        reply = f"Battery is at {percent} percent and {state}."

        if battery.secsleft not in (
            psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN
        ) and battery.secsleft and battery.secsleft > 0:
            reply += f" About {_human_duration(battery.secsleft)} left."

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
            return "System stats need the psutil package."

        cpu = psutil.cpu_percent(interval=0.4)
        ram = psutil.virtual_memory().percent

        return f"CPU is at {round(cpu)} percent, memory at {round(ram)} percent."

    # --------------------------------------------------------
    # DISK SPACE
    # --------------------------------------------------------

    if re.search(r"\b(disk space|storage)\b", text):

        if not _PSUTIL_OK:
            return "Disk stats need the psutil package."

        for root in ("C:/", "/"):
            try:
                usage = psutil.disk_usage(root)
                free_gb = round(usage.free / (1024 ** 3))
                total_gb = round(usage.total / (1024 ** 3))
                return f"The main drive has {free_gb} gigabytes free, out of {total_gb}."
            except Exception:
                continue

        return "I couldn't read the disk usage."

    # --------------------------------------------------------
    # IP ADDRESS
    # --------------------------------------------------------

    if re.search(r"\b(ip address|my ip|ip)\b$", text) or text in ("ip", "my ip"):
        return f"Your local IP address is {_local_ip().replace('.', ' ')}."

    # --------------------------------------------------------
    # WI-FI PASSWORD
    # --------------------------------------------------------

    if re.search(r"\bwifi password\b|\bwi fi password\b|\bwi fi\b.*password", text):

        ssid, password = _wifi_password()

        if ssid is None:
            return "I couldn't read the Wi-Fi details. Is Wi-Fi connected?"

        if password is None:
            return f"The network is {ssid}, but the password isn't stored on this PC."

        return f"The password for {ssid} is: {password}."

    # --------------------------------------------------------
    # UPTIME
    # --------------------------------------------------------

    if re.match(r"^(?:how long have (?:you|we) been (?:on|up)|uptime|system uptime)$", text):

        if not _PSUTIL_OK:
            return "Uptime needs the psutil package."

        uptime = time.time() - psutil.boot_time()
        return f"The system has been up for {_human_duration(uptime)}."

    # --------------------------------------------------------
    # SCREENSHOT
    # --------------------------------------------------------

    if re.match(r"^(?:take )?(?:a )?screen ?shot(?: for me)?(?: of the screen)?(?: now)?$", text):

        if not _PYAUTOGUI_OK:
            return "Screenshots need the pyautogui package."

        try:
            config.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = config.SCREENSHOT_DIR / f"Lyra_{stamp}.png"

            pyautogui.screenshot(str(path))

            return "Screenshot saved to the Pictures folder."
        except Exception as e:
            print(f"Screenshot error: {e}")
            return "I couldn't take the screenshot."

    # --------------------------------------------------------
    # LOCK
    # --------------------------------------------------------

    if re.match(r"^lock(?: my| the)? (?:pc|computer|screen|windows|system)$", text):

        if not IS_WINDOWS:
            return "Locking only works on Windows."

        def _lock():
            ctypes.windll.user32.LockWorkStation()

        _lock()
        return "Locked. See you soon."

    # --------------------------------------------------------
    # CANCEL SHUTDOWN
    # --------------------------------------------------------

    if re.match(r"^cancel (?:the )?(?:shutdown|restart|turn off)$", text):

        if not IS_WINDOWS:
            return "That only works on Windows."

        result = subprocess.run(["shutdown", "/a"], capture_output=True)

        if result.returncode == 0:
            return "Shutdown cancelled."
        return "There was no shutdown to cancel."

    # --------------------------------------------------------
    # SHUTDOWN  (needs confirmation)
    # --------------------------------------------------------

    if re.match(
        r"^(?:shut ?down|turn off|power off)"
        r"(?: (?:the|my)? ?(?:pc|computer|system|windows|machine))?(?: now| please)?$",
        text,
    ):

        if not IS_WINDOWS:
            return "That only works on Windows."

        return Confirmation(
            prompt=(
                f"This will shut down the PC in {config.SHUTDOWN_DELAY} seconds. "
                "Say confirm to continue, or cancel."
            ),
            action=_do_shutdown,
            say_on_confirm=(
                f"Shutting down in {config.SHUTDOWN_DELAY} seconds. Goodbye."
            ),
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
            return "That only works on Windows."

        return Confirmation(
            prompt=(
                f"This will restart the PC in {config.SHUTDOWN_DELAY} seconds. "
                "Say confirm to continue, or cancel."
            ),
            action=_do_restart,
            say_on_confirm=f"Restarting in {config.SHUTDOWN_DELAY} seconds.",
        )

    # --------------------------------------------------------
    # PC SLEEP  (needs confirmation)
    # --------------------------------------------------------

    if re.match(
        r"^(?:put )?(?:the |my )?(?:pc|computer|system|windows|machine)?"
        r" ?to sleep(?: now)?$", text,
    ) or text == "sleep pc" or text == "sleep the pc":

        if not IS_WINDOWS:
            return "That only works on Windows."

        return Confirmation(
            prompt="Put the PC to sleep? Say confirm, or cancel.",
            action=_do_sleep,
            say_on_confirm="Sleeping. Goodnight.",
        )

    # --------------------------------------------------------
    # EMPTY RECYCLE BIN  (needs confirmation)
    # --------------------------------------------------------

    if re.match(r"^(?:empty|clear|clean) (?:the )?recycle bin$", text):

        return Confirmation(
            prompt="This will permanently empty the recycle bin. Say confirm, or cancel.",
            action=_do_empty_recycle_bin,
            say_on_confirm="Recycle bin emptied.",
        )

    return None


def name():
    return "system"
