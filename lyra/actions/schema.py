"""Strict validation for model-proposed computer action plans."""

from dataclasses import dataclass


class PlanValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ActionPlan:
    intent: str
    actions: tuple


_ALLOWED = {
    "open_app": {"type", "app"},
    "generate_text": {"type", "instruction"},
    "type_text": {"type", "source"},
    "press_key": {"type", "key"},
    "hotkey": {"type", "keys"},
    "move_mouse": {"type", "x", "y"},
    "click": {"type", "button", "clicks"},
    "scroll": {"type", "direction", "amount"},
    "drag_drop": {"type", "start_x", "start_y", "end_x", "end_y"},
}


def validate_plan(value):
    if not isinstance(value, dict) or value.get("intent") != "computer_task":
        raise PlanValidationError("Expected intent=computer_task")
    actions = value.get("actions")
    if not isinstance(actions, list) or not actions or len(actions) > 8:
        raise PlanValidationError("Plan must contain between 1 and 8 actions")
    checked = []
    has_generated_text = False
    from ..skills.apps import OPEN_APPS
    action_safe_apps = set(OPEN_APPS) - {
        "cmd", "command prompt", "powershell", "terminal",
    }
    for index, action in enumerate(actions):
        if not isinstance(action, dict) or not isinstance(action.get("type"), str):
            raise PlanValidationError(f"Action {index + 1} must be an object with a type")
        action_type = action["type"]
        if action_type not in _ALLOWED:
            raise PlanValidationError(f"Unsupported action type: {action_type}")
        unknown = set(action) - _ALLOWED[action_type]
        missing = _ALLOWED[action_type] - set(action)
        if unknown or missing:
            raise PlanValidationError(
                f"Invalid fields for {action_type}; missing={sorted(missing)}, "
                f"unknown={sorted(unknown)}"
            )
        normalized_action = dict(action)
        if action_type == "open_app":
            normalized_action["app"] = action["app"].strip().casefold()
            if normalized_action["app"] not in action_safe_apps:
                raise PlanValidationError(
                    f"Application is not approved for automated launch: {action['app']}"
                )
        _validate_values(action_type, normalized_action, index)
        if action_type == "generate_text":
            has_generated_text = True
        if action_type == "type_text" and not has_generated_text:
            raise PlanValidationError("type_text must follow a generate_text action")
        checked.append(normalized_action)
    return ActionPlan("computer_task", tuple(checked))


def _validate_values(kind, action, index):
    label = f"Action {index + 1}"
    if kind in ("open_app", "generate_text"):
        key = "app" if kind == "open_app" else "instruction"
        value = action[key]
        if not isinstance(value, str) or not value.strip() or len(value) > 240:
            raise PlanValidationError(f"{label} has an invalid {key}")
    elif kind == "type_text":
        if action["source"] != "generated_text":
            raise PlanValidationError(f"{label} may only type text generated in this plan")
    elif kind == "press_key":
        if not isinstance(action["key"], str) or len(action["key"]) > 20:
            raise PlanValidationError(f"{label} has an invalid key")
    elif kind == "hotkey":
        keys = action["keys"]
        if not isinstance(keys, list) or not 2 <= len(keys) <= 4 or not all(
            isinstance(key, str) and len(key) <= 20 for key in keys
        ):
            raise PlanValidationError(f"{label} has an invalid hotkey")
    elif kind in ("move_mouse", "drag_drop"):
        fields = ("x", "y") if kind == "move_mouse" else (
            "start_x", "start_y", "end_x", "end_y"
        )
        for field in fields:
            value = action[field]
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 20000:
                raise PlanValidationError(f"{label} has invalid coordinate {field}")
    elif kind == "click":
        if action["button"] not in ("left", "right", "middle"):
            raise PlanValidationError(f"{label} has invalid mouse button")
        if isinstance(action["clicks"], bool) or action["clicks"] not in (1, 2):
            raise PlanValidationError(f"{label} click count must be 1 or 2")
    elif kind == "scroll":
        if action["direction"] not in ("up", "down", "left", "right"):
            raise PlanValidationError(f"{label} has invalid scroll direction")
        amount = action["amount"]
        if isinstance(amount, bool) or not isinstance(amount, int) or not 1 <= amount <= 20:
            raise PlanValidationError(f"{label} scroll amount must be between 1 and 20")
