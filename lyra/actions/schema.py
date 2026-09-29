"""Strict validation for model-proposed computer action plans.

Three layers, in the order the planner uses them:

* ``plan_json_schema()`` is sent to Ollama as a structured-output format, so
  the model is steered into the exact plan shape while it generates.
* ``coerce_plan()`` rewrites the JSON dialects small local models commonly
  produce anyway (``"open_app(app=notepad)"``, ``{"open_app": {...}}``,
  ``{"action": "open_app", ...}``) into that shape. It only restructures;
  it never adds power.
* ``validate_plan()`` is the safety gate. Every field, app, key, coordinate
  and action count is checked here before anything is dispatched.
"""

import ast
import re
from dataclasses import dataclass


class PlanValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ActionPlan:
    intent: str
    actions: tuple


# Required fields per action type.
_ALLOWED = {
    "open_app": {"type", "app"},
    "open_url": {"type", "url"},
    "generate_text": {"type", "instruction"},
    "type_text": {"type"},
    "press_key": {"type", "key"},
    "hotkey": {"type", "keys"},
    "move_mouse": {"type", "x", "y"},
    "click": {"type", "button", "clicks"},
    "scroll": {"type", "direction", "amount"},
    "drag_drop": {"type", "start_x", "start_y", "end_x", "end_y"},
}

# Optional fields: allowed but not required (the validator applies extra
# either/or rules, e.g. type_text needs exactly one of source/text).
_OPTIONAL_FIELDS = {
    "open_url": {"browser"},
    "type_text": {"source", "text"},
}

# Field order, used to map positional arguments ("move_mouse(10, 20)").
_FIELD_ORDER = {
    "open_app": ("app",),
    "open_url": ("url",),
    "generate_text": ("instruction",),
    "type_text": ("source",),
    "press_key": ("key",),
    "hotkey": ("keys",),
    "move_mouse": ("x", "y"),
    "click": ("button", "clicks"),
    "scroll": ("direction", "amount"),
    "drag_drop": ("start_x", "start_y", "end_x", "end_y"),
}

_BLOCKED_APPS = {"cmd", "command prompt", "powershell", "terminal"}

_MAX_URL_LENGTH = 2048
_MAX_TYPED_TEXT_LENGTH = 240


def _validate_open_url(url):
    """http/https only, with a host, no credentials — validated with urllib."""
    from urllib.parse import urlparse

    if not isinstance(url, str) or not url.strip() or len(url) > _MAX_URL_LENGTH:
        raise PlanValidationError("open_url needs a non-empty URL string")
    if any(char.isspace() or ord(char) < 32 for char in url):
        raise PlanValidationError("open_url URL must not contain whitespace")
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise PlanValidationError(f"open_url URL could not be parsed: {exc}")
    if parsed.scheme not in ("http", "https"):
        raise PlanValidationError(
            "open_url only accepts http:// or https:// URLs, got "
            + repr(parsed.scheme or "no scheme")
        )
    if not parsed.netloc:
        raise PlanValidationError("open_url URL is missing its host")
    if "@" in parsed.netloc or parsed.username or parsed.password:
        raise PlanValidationError("open_url URL must not embed credentials")
    return url.strip()


def validate_plan(value):
    from ..computer.automation import HOTKEY_KEYS, PRESSABLE_KEYS

    if not isinstance(value, dict) or value.get("intent") != "computer_task":
        raise PlanValidationError("Expected intent=computer_task")
    actions = value.get("actions")
    if not isinstance(actions, list) or not actions or len(actions) > 8:
        raise PlanValidationError("Plan must contain between 1 and 8 actions")
    checked = []
    has_generated_text = False
    from ..skills.apps import OPEN_APPS
    from .. import config
    action_safe_apps = set(OPEN_APPS) - _BLOCKED_APPS
    for index, action in enumerate(actions):
        if not isinstance(action, dict) or not isinstance(action.get("type"), str):
            raise PlanValidationError(f"Action {index + 1} must be an object with a type")
        action_type = action["type"]
        if action_type not in _ALLOWED:
            raise PlanValidationError(f"Unsupported action type: {action_type}")
        allowed_fields = _ALLOWED[action_type] | _OPTIONAL_FIELDS.get(action_type, set())
        unknown = set(action) - allowed_fields
        missing = _ALLOWED[action_type] - set(action)
        if unknown or missing:
            raise PlanValidationError(
                f"Invalid fields for {action_type}; missing={sorted(missing)}, "
                f"unknown={sorted(unknown)}"
            )
        normalized_action = dict(action)
        if action_type == "open_app":
            if not isinstance(action["app"], str):
                raise PlanValidationError(f"Action {index + 1} has an invalid app")
            normalized_action["app"] = action["app"].strip().casefold()
            if normalized_action["app"] not in action_safe_apps:
                raise PlanValidationError(
                    f"Application is not approved for automated launch: {action['app']}"
                )
        elif action_type == "open_url":
            normalized_action["url"] = _validate_open_url(action["url"])
            browser = action.get("browser")
            if browser is not None:
                canonical = config.normalize_browser_name(browser)
                if not canonical:
                    raise PlanValidationError(
                        f"open_url browser is not supported: {browser!r}"
                    )
                normalized_action["browser"] = canonical
        elif action_type == "type_text":
            has_source = "source" in action
            has_text = "text" in action
            if has_source == has_text:
                raise PlanValidationError(
                    f"Action {index + 1} type_text needs exactly one of source or text"
                )
            if has_text:
                literal = action["text"]
                if (
                    not isinstance(literal, str)
                    or not literal.strip()
                    or len(literal) > _MAX_TYPED_TEXT_LENGTH
                ):
                    raise PlanValidationError(
                        f"Action {index + 1} type_text text must be a short, "
                        "non-empty string"
                    )
                normalized_action["text"] = literal.strip()
        elif action_type == "press_key" and isinstance(action["key"], str):
            normalized_action["key"] = action["key"].strip().lower()
        elif action_type == "hotkey" and isinstance(action["keys"], list):
            normalized_action["keys"] = [
                key.strip().lower() if isinstance(key, str) else key for key in action["keys"]
            ]
        _validate_values(action_type, normalized_action, index, PRESSABLE_KEYS, HOTKEY_KEYS)
        if action_type == "generate_text":
            has_generated_text = True
        if (
            action_type == "type_text"
            and action.get("source") == "generated_text"
            and not has_generated_text
        ):
            raise PlanValidationError("type_text must follow a generate_text action")
        checked.append(normalized_action)
    return ActionPlan("computer_task", tuple(checked))


def _validate_values(kind, action, index, pressable_keys, hotkey_keys):
    label = f"Action {index + 1}"
    if kind in ("open_app", "generate_text"):
        key = "app" if kind == "open_app" else "instruction"
        value = action[key]
        if not isinstance(value, str) or not value.strip() or len(value) > 240:
            raise PlanValidationError(f"{label} has an invalid {key}")
    elif kind == "type_text":
        # The literal "text" form is validated in validate_plan(); the
        # source form may only ever type text generated in this plan.
        if "source" in action and action["source"] != "generated_text":
            raise PlanValidationError(f"{label} may only type text generated in this plan")
    elif kind == "press_key":
        if action["key"] not in pressable_keys:
            raise PlanValidationError(f"{label} has a key that is not allowed: {action['key']!r}")
    elif kind == "hotkey":
        keys = action["keys"]
        if not isinstance(keys, list) or not 2 <= len(keys) <= 4 or not all(
            isinstance(key, str) and key in hotkey_keys for key in keys
        ):
            raise PlanValidationError(f"{label} has an invalid or disallowed hotkey")
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


# ------------------------------------------------------------
# STRUCTURED OUTPUT SCHEMA  (sent to Ollama as "format")
# ------------------------------------------------------------

def plan_json_schema():
    """JSON Schema for the plan, built from the same tables the validator uses."""
    from ..computer.automation import HOTKEY_KEYS, PRESSABLE_KEYS

    string = {"type": "string"}
    integer = {"type": "integer"}
    fields = {
        "open_app": {"app": string},
        "open_url": {"url": string},
        "generate_text": {"instruction": string},
        "type_text": {"source": {"type": "string", "enum": ["generated_text"]}},
        "press_key": {"key": {"type": "string", "enum": sorted(PRESSABLE_KEYS)}},
        "hotkey": {"keys": {
            "type": "array",
            "items": {"type": "string", "enum": sorted(HOTKEY_KEYS)},
            "minItems": 2,
            "maxItems": 4,
        }},
        "move_mouse": {"x": integer, "y": integer},
        "click": {
            "button": {"type": "string", "enum": ["left", "right", "middle"]},
            "clicks": {"type": "integer", "enum": [1, 2]},
        },
        "scroll": {
            "direction": {"type": "string", "enum": ["up", "down", "left", "right"]},
            "amount": integer,
        },
        "drag_drop": {"start_x": integer, "start_y": integer, "end_x": integer, "end_y": integer},
    }
    optional = {
        "open_url": {
            "browser": {"type": "string", "enum": ["brave", "chrome", "edge", "firefox"]},
        },
        "type_text": {"text": string},
    }
    variants = [
        {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": [kind]},
                **properties,
                **optional.get(kind, {}),
            },
            "required": sorted(_ALLOWED[kind]),
            "additionalProperties": False,
        }
        for kind, properties in fields.items()
    ]
    return {
        "type": "object",
        "properties": {
            "intent": {"type": "string", "enum": ["computer_task"]},
            "actions": {
                "type": "array",
                "items": {"anyOf": variants},
                "minItems": 1,
                "maxItems": 8,
            },
        },
        "required": ["intent", "actions"],
        "additionalProperties": False,
    }


# ------------------------------------------------------------
# DIALECT COERCION  (restructure only; validate_plan decides)
# ------------------------------------------------------------

_TYPE_ALIASES = ("action", "name", "tool", "function", "command", "op", "operation", "step")
_KEY_SYNONYMS = {
    "return": "enter", "escape": "esc", "del": "delete", "spacebar": "space",
    "page up": "pageup", "page down": "pagedown", "page_up": "pageup", "page_down": "pagedown",
}
_ARGUMENT_KEYS = ("args", "arguments", "parameters", "params", "input", "inputs", "fields")
_INVALID = object()


def _canonical_kind(name):
    """'openApp', 'Open-App', 'open app' -> 'open_app'."""
    if not isinstance(name, str):
        return None
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name.strip())
    return re.sub(r"[\s\-]+", "_", name).lower()


def coerce_plan(value):
    """Rewrite common small-model plan dialects into the canonical shape.

    Nothing here grants permission: the result still has to pass
    ``validate_plan()``. Anything unrecognised is passed through unchanged
    so the validator can reject it with a precise message.
    """
    if isinstance(value, list):
        value = {"intent": "computer_task", "actions": value}
    if not isinstance(value, dict):
        return value
    value = dict(value)
    if "actions" not in value:
        for key in ("steps", "plan", "tasks"):
            if isinstance(value.get(key), list):
                value["actions"] = value.pop(key)
                break
    if isinstance(value.get("actions"), list):
        value.setdefault("intent", "computer_task")
        value["actions"] = [_coerce_action(item) for item in value["actions"]]
    return value


def _coerce_action(item):
    if isinstance(item, str):
        parsed = _parse_call(item)
        if parsed is None:
            return item
        item = parsed
    if not isinstance(item, dict):
        return item
    action = dict(item)

    # {"action": "open_app", "app": "notepad"} and similar type keys.
    if not isinstance(action.get("type"), str):
        for alias in _TYPE_ALIASES:
            if _canonical_kind(action.get(alias)) in _ALLOWED:
                action["type"] = action.pop(alias)
                break

    # {"url": "..."} / {"link": "..."} with no type key is a web action.
    if "type" not in action and any(key in action for key in ("url", "link", "href")):
        action["type"] = "open_url"

    # {"open_app": {"app": "notepad"}} or {"open_app": "notepad"}.
    if "type" not in action and len(action) == 1:
        (name, argument), = action.items()
        kind = _canonical_kind(name)
        if kind in _ALLOWED:
            if isinstance(argument, dict):
                action = {"type": kind, **argument}
            else:
                fields = _FIELD_ORDER[kind]
                values = argument if isinstance(argument, list) and len(fields) > 1 else [argument]
                if len(values) == len(fields):
                    action = {"type": kind, **dict(zip(fields, values))}

    if not isinstance(action.get("type"), str):
        return action
    kind = _canonical_kind(action["type"])
    if kind not in _ALLOWED:
        return action
    action["type"] = kind

    # {"type": "open_app", "args": {"app": "notepad"}}.
    for key in _ARGUMENT_KEYS:
        if isinstance(action.get(key), dict):
            for field, field_value in action.pop(key).items():
                action.setdefault(field, field_value)
            break

    if kind == "type_text":
        # Two shapes: type short user-given text literally, or type what a
        # generate_text step produced. Coercion only reshapes; the
        # validator still decides.
        literal = action.get("text")
        if isinstance(literal, str) and literal.strip():
            return {"type": "type_text", "text": literal.strip()}
        return {"type": "type_text", "source": "generated_text"}

    fields = _FIELD_ORDER[kind]
    extra = [field for field in action if field != "type" and field not in fields]
    if len(fields) == 1 and fields[0] not in action and len(extra) == 1:
        # {"type": "open_app", "application": "notepad"}: one field, other name.
        action[fields[0]] = action.pop(extra[0])

    if kind == "open_app" and isinstance(action.get("app"), str):
        action["app"] = re.sub(r"\.exe$", "", action["app"].strip(), flags=re.IGNORECASE)
    if kind == "open_url":
        # Rebuild around the URL and optional browser, dropping dialect keys.
        url = action.get("url") or action.get("link") or action.get("href")
        browser = action.get("browser") or action.get("in") or action.get("using")
        rebuilt = {"type": "open_url"}
        if isinstance(url, str) and url.strip():
            rebuilt["url"] = url.strip()
        if isinstance(browser, str) and browser.strip():
            rebuilt["browser"] = browser.strip()
        return rebuilt
    if kind == "press_key" and isinstance(action.get("key"), str):
        key = action["key"].strip().lower()
        action["key"] = _KEY_SYNONYMS.get(key, key)
    if kind == "hotkey" and isinstance(action.get("keys"), str):
        action["keys"] = [key for key in re.split(r"[+\s,]+", action["keys"]) if key]
    return action


def _parse_call(text):
    """'open_app(app="notepad")', 'open_app(notepad)', 'open_app: notepad', 'type_text'."""
    text = text.strip()
    if len(text) > 500:
        return None
    if _canonical_kind(text) in _ALLOWED:
        return {"type": _canonical_kind(text)}

    match = re.fullmatch(r"([A-Za-z][\w \-]*?)\s*\((.*)\)", text, re.DOTALL)
    if match is None:
        colon = re.fullmatch(r"([A-Za-z][\w \-]*?)\s*:\s*(.+)", text, re.DOTALL)
        kind = _canonical_kind(colon.group(1)) if colon else None
        if kind in _ALLOWED and len(_FIELD_ORDER[kind]) == 1:
            return {"type": kind, _FIELD_ORDER[kind][0]: colon.group(2).strip().strip("'\"")}
        return None

    kind = _canonical_kind(match.group(1))
    if kind not in _ALLOWED:
        return None
    inner = match.group(2).strip()
    fields = _FIELD_ORDER[kind]
    if not inner:
        return {"type": kind}

    try:
        call = ast.parse(f"f({inner})", mode="eval").body   # parsed, never evaluated
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        # generate_text(Write 20 words about India): one bare argument.
        if len(fields) == 1:
            value = re.sub(rf"^{fields[0]}\s*[=:]\s*", "", inner).strip().strip("'\"")
            return {"type": kind, fields[0]: value}
        return None
    if not isinstance(call, ast.Call) or len(call.args) > len(fields):
        return None

    action = {"type": kind}
    for field, node in zip(fields, call.args):
        action[field] = _literal(node)
    for keyword in call.keywords:
        if keyword.arg is None:
            return None
        action[keyword.arg] = _literal(keyword.value)
    if any(value is _INVALID for value in action.values()):
        return None
    return action


def _literal(node):
    """Plain constants and bare names only; anything else is refused."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, int)) \
            and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Name):          # app=notepad, source=generated_text
        return node.id
    if isinstance(node, (ast.List, ast.Tuple)):
        values = [_literal(element) for element in node.elts]
        return _INVALID if any(value is _INVALID for value in values) else values
    return _INVALID
