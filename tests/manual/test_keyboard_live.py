"""
============================================================
 LYRA KEYBOARD TEST 01  (live hardware check)
============================================================
 This one is NOT part of the normal test run: it opens a real
 Notepad window and types into it with the real keyboard.

 Run it deliberately, on a Windows machine, when you want to
 prove the PC control path works end to end:

     pytest -m manual -s

 What it does:
   1. Opens Windows Notepad
   2. Waits for the Notepad window to appear
   3. Focuses it and VERIFIES it is really focused
   4. Types the fixed sentence:  Lyra is working.
   5. Stops.

 Emergency abort: slam the mouse into the TOP-LEFT corner
 of the screen (pyautogui failsafe), or Ctrl+C.
============================================================
"""

import subprocess
import time

import pytest

pytestmark = pytest.mark.manual


TYPE_TEXT = "Lyra is working."
WINDOW_HINT = "notepad"          # matched case-insensitively in the window title
WAIT_SECONDS = 15                # max time to wait for Notepad to appear
TYPE_INTERVAL = 0.03             # seconds between keystrokes (reliability)
COUNTDOWN = 3                    # seconds before typing starts


def find_window(gw, hint):
    """Return the first visible window whose title contains the hint."""

    for window in gw.getAllWindows():
        title = (window.title or "").lower()

        if hint in title:
            return window

    return None


def focus_window(window, gw, pyautogui):
    """
    Bring the window to the foreground and verify it.
    Returns True if the window is really focused.
    """

    try:
        if window.isMinimized:
            window.restore()
    except Exception:
        pass

    try:
        window.activate()
    except Exception:
        # Windows sometimes blocks programmatic focus.
        # Minimize + restore is the classic workaround.
        try:
            window.minimize()
            time.sleep(0.2)
            window.restore()
            time.sleep(0.3)
        except Exception:
            pass

    time.sleep(0.4)

    # verify — never type blind into the wrong window
    try:
        active = gw.getActiveWindow()

        if active is None:
            return False

        return WINDOW_HINT in (active.title or "").lower()

    except Exception:
        return False


def run_keyboard_test():
    """Returns an exit code: 0 = typed successfully, 1 = failed."""

    # --------------------------------------------------------
    # 0. DEPENDENCY CHECK
    # --------------------------------------------------------

    try:
        import pyautogui
    except ImportError:
        print("pyautogui is missing.  Run:  pip install pyautogui")
        return 1

    try:
        import pygetwindow as gw
    except ImportError:
        print("pygetwindow is missing.  Run:  pip install pygetwindow")
        return 1

    pyautogui.FAILSAFE = True       # mouse to top-left corner = instant abort

    print("=" * 44)
    print("  LYRA KEYBOARD TEST 01")
    print("=" * 44)
    print()

    # --------------------------------------------------------
    # 1. OPEN NOTEPAD
    # --------------------------------------------------------

    print("[1/5] Opening Notepad...")

    try:
        subprocess.Popen(
            ["notepad"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        subprocess.Popen("start notepad", shell=True)

    # --------------------------------------------------------
    # 2. WAIT FOR THE WINDOW
    # --------------------------------------------------------

    print(f"[2/5] Waiting for the window (max {WAIT_SECONDS}s)...")

    window = None
    deadline = time.time() + WAIT_SECONDS

    while time.time() < deadline:

        window = find_window(gw, WINDOW_HINT)

        if window is not None:
            break

        time.sleep(0.3)

    if window is None:
        print()
        print(f"   FAILED: no window with '{WINDOW_HINT}' in the title")
        print("   appeared within {0} seconds.".format(WAIT_SECONDS))
        print()
        print("   If Notepad IS open on your screen, tell me the")
        print("   exact text shown in its title bar.")
        return 1

    print(f'   Found: "{window.title}"')

    # --------------------------------------------------------
    # 3. FOCUS THE WINDOW
    # --------------------------------------------------------

    print("[3/5] Focusing the window...")

    if not focus_window(window, gw, pyautogui):
        print()
        print("   FAILED: Notepad is open but I could not get focus.")
        print("   (Windows blocks focus-stealing sometimes.)")
        print("   Nothing was typed. Click Notepad once, then rerun.")
        return 1

    print("   Focus verified.")

    # --------------------------------------------------------
    # 4. TYPE THE SENTENCE
    # --------------------------------------------------------

    print(f"[4/5] Typing in {COUNTDOWN}s — mouse to TOP-LEFT corner to abort...")

    for count in range(COUNTDOWN, 0, -1):
        print(f"   {count}...")
        time.sleep(1)

    pyautogui.write(TYPE_TEXT, interval=TYPE_INTERVAL)

    # --------------------------------------------------------
    # 5. DONE
    # --------------------------------------------------------

    print("[5/5] Done.")
    print()
    print(f'   Notepad should now show:  "{TYPE_TEXT}"')
    print()

    return 0


def test_keyboard_typing():
    """Live check: Notepad opens, takes focus, and gets the sentence typed in."""

    assert run_keyboard_test() == 0, (
        f"Notepad did not end up with '{TYPE_TEXT}' typed into it. "
        "See the output above for which step failed."
    )
