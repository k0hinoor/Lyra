"""Execute only validated LYRA actions; no shell/code evaluation surface."""

import logging
import re
import threading
from dataclasses import dataclass
from enum import Enum

from ..computer import automation
from .schema import ActionPlan

log = logging.getLogger(__name__)

_KEYBOARD_ACTIONS = frozenset({"type_text", "press_key", "hotkey"})


class Status(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    UNKNOWN = "UNKNOWN"
    STOPPED = "STOPPED"


@dataclass(frozen=True)
class ActionResult:
    action: dict
    status: Status
    detail: str = ""


@dataclass(frozen=True)
class TaskResult:
    status: Status
    results: tuple


class ActionExecutor:
    def __init__(self, observer=None):
        self._stop = threading.Event()
        self._observer = observer

    def request_stop(self):
        self._stop.set()

    def reset_stop(self):
        self._stop.clear()

    @property
    def stop_requested(self):
        return self._stop.is_set()

    def run(self, plan, generate_text=None):
        if not isinstance(plan, ActionPlan):
            raise TypeError("ActionExecutor accepts only validated ActionPlan objects")
        results = []
        generated_text = None
        opened_app = None
        for action in plan.actions:
            if self._stop.is_set():
                results.append(ActionResult(action, Status.STOPPED, "Task stopped safely"))
                return TaskResult(Status.STOPPED, tuple(results))
            try:
                kind = action["type"]
                if kind in _KEYBOARD_ACTIONS and opened_app is not None:
                    # Keystrokes go to whatever window is in front. After
                    # opening an app, type only once that app is verified
                    # to be in front (never into LYRA's own console).
                    if not automation.focus_app_window(opened_app):
                        raise RuntimeError(
                            f"I couldn't bring the {opened_app} window to the front, "
                            "so I didn't type anything"
                        )
                if kind == "open_app":
                    automation.open_app(action["app"])
                    opened_app = action["app"]
                elif kind == "generate_text":
                    if generate_text is None:
                        raise RuntimeError("Text generation callback is unavailable")
                    instruction = action["instruction"]
                    generated_text = generate_text(instruction)
                    if not isinstance(generated_text, str) or not generated_text.strip():
                        raise RuntimeError("Text generation returned no usable text")
                    exact = re.search(r"\bexactly\s+(\d+)\s+words\b", instruction, re.IGNORECASE)
                    if exact:
                        required = int(exact.group(1))
                        for _attempt in range(2):
                            words = re.findall(r"\b[\w'-]+\b", generated_text or "")
                            if len(words) == required:
                                break
                            generated_text = generate_text(
                                f"{instruction}. Output exactly {required} words, "
                                "with no heading or explanation."
                            )
                        if len(re.findall(r"\b[\w'-]+\b", generated_text or "")) != required:
                            raise RuntimeError(
                                f"Generated text did not meet the exact {required}-word constraint"
                            )
                elif kind == "type_text":
                    if generated_text is None:
                        raise RuntimeError("No generated text is available to type")
                    automation.type_text(generated_text)
                elif kind == "press_key":
                    automation.press_key(action["key"])
                elif kind == "hotkey":
                    automation.hotkey(action["keys"])
                elif kind == "move_mouse":
                    automation.move_mouse(action["x"], action["y"])
                elif kind == "click":
                    automation.click(action["button"], action["clicks"])
                elif kind == "scroll":
                    automation.scroll(action["direction"], action["amount"])
                elif kind == "drag_drop":
                    automation.drag_drop(
                        action["start_x"], action["start_y"], action["end_x"], action["end_y"]
                    )
                else:  # Extra defense if an invalid ActionPlan is constructed manually.
                    raise ValueError(f"Unsupported action type: {kind}")

                observed = self._observer(action) if self._observer else None
                status = Status.UNKNOWN if observed is None else (
                    Status.SUCCESS if observed else Status.FAILURE
                )
                detail = "Action issued; outcome not independently verified" if observed is None else (
                    "Observed success" if observed else "Observer reported failure"
                )
                results.append(ActionResult(action, status, detail))
                log.info("Task action %s returned %s", kind, status.value)
                if status == Status.FAILURE:
                    return TaskResult(Status.FAILURE, tuple(results))
            except Exception as exc:
                log.exception("Task action failed: %s", action.get("type"))
                results.append(ActionResult(action, Status.FAILURE, str(exc)))
                return TaskResult(Status.FAILURE, tuple(results))
        final = Status.SUCCESS if results and all(r.status == Status.SUCCESS for r in results) else Status.UNKNOWN
        return TaskResult(final, tuple(results))
