"""Minimal screen capture interface for later visual reasoning integrations."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ScreenFrame:
    image: object
    width: int
    height: int
    window_title: str | None = None


def screen_dimensions():
    import pyautogui
    size = pyautogui.size()
    return int(size.width), int(size.height)


def capture_screen(window_title=None):
    """Capture the desktop or, when pygetwindow exists, a titled window."""
    import pyautogui
    if not window_title:
        image = pyautogui.screenshot()
        return ScreenFrame(image, image.width, image.height)

    try:
        import pygetwindow
        matches = [w for w in pygetwindow.getAllWindows()
                   if window_title.casefold() in (w.title or "").casefold()]
        if not matches:
            raise LookupError(f"No visible window matches {window_title!r}")
        window = matches[0]
        if window.width <= 0 or window.height <= 0:
            raise RuntimeError("The requested window is minimized or has no visible area")
        image = pyautogui.screenshot(region=(window.left, window.top, window.width, window.height))
        return ScreenFrame(image, image.width, image.height, window.title)
    except ImportError as exc:
        raise RuntimeError("Window capture requires the optional pygetwindow package") from exc
