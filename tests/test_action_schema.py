import pytest

from lyra.actions.schema import PlanValidationError, validate_plan


def test_valid_compound_text_task_plan():
    plan = validate_plan({
        "intent": "computer_task",
        "actions": [
            {"type": "open_app", "app": "Notepad"},
            {"type": "generate_text", "instruction": "Write exactly 20 words about India."},
            {"type": "type_text", "source": "generated_text"},
        ],
    })
    assert plan.actions[0]["app"] == "notepad"
    assert len(plan.actions) == 3


@pytest.mark.parametrize("actions", [
    [{"type": "run_command", "command": "whoami"}],
    [{"type": "open_app", "app": "powershell"}],
    [{"type": "type_text", "source": "generated_text"}],
    [{"type": "move_mouse", "x": -1, "y": 10}],
    [{"type": "click", "button": "left", "clicks": 3}],
])
def test_unsafe_or_malformed_actions_are_rejected(actions):
    with pytest.raises(PlanValidationError):
        validate_plan({"intent": "computer_task", "actions": actions})


def test_plan_length_is_bounded():
    actions = [{"type": "press_key", "key": "enter"}] * 9
    with pytest.raises(PlanValidationError):
        validate_plan({"intent": "computer_task", "actions": actions})


# ------------------------------------------------------------
# KEYS ARE CHECKED BEFORE ANYTHING RUNS
# ------------------------------------------------------------

@pytest.mark.parametrize("action", [
    {"type": "press_key", "key": "f4"},
    {"type": "hotkey", "keys": ["ctrl", "alt", "delete"]},
    {"type": "hotkey", "keys": ["alt", "f4"]},
])
def test_disallowed_keys_are_rejected_at_validation(action):
    with pytest.raises(PlanValidationError):
        validate_plan({"intent": "computer_task", "actions": [action]})


def test_key_names_are_normalised_to_lowercase():
    plan = validate_plan({"intent": "computer_task", "actions": [
        {"type": "press_key", "key": "Enter"},
        {"type": "hotkey", "keys": ["Ctrl", "S"]},
    ]})
    assert plan.actions[0]["key"] == "enter"
    assert plan.actions[1]["keys"] == ["ctrl", "s"]


# ------------------------------------------------------------
# SMALL-MODEL DIALECTS ARE RESTRUCTURED, NEVER TRUSTED
# ------------------------------------------------------------

from lyra.actions.schema import (  # noqa: E402
    _ALLOWED,
    _OPTIONAL_FIELDS,
    coerce_plan,
    plan_json_schema,
)

CANONICAL = [
    {"type": "open_app", "app": "notepad"},
    {"type": "generate_text", "instruction": "Write 20 words about India"},
    {"type": "type_text", "source": "generated_text"},
]


@pytest.mark.parametrize("reply", [
    # The shape the validator wants.
    {"intent": "computer_task", "actions": CANONICAL},
    # Function-call strings, echoing the old prompt's "open_app(app)" notation.
    {"intent": "computer_task", "actions": [
        "open_app(app=notepad)",
        'generate_text(instruction="Write 20 words about India")',
        "type_text(source=generated_text)",
    ]},
    {"intent": "computer_task", "actions": [
        "open_app('notepad')",
        "generate_text(Write 20 words about India)",
        "type_text",
    ]},
    # Action name as the key.
    {"intent": "computer_task", "actions": [
        {"open_app": {"app": "notepad"}},
        {"generate_text": "Write 20 words about India"},
        {"type_text": {"source": "generated_text"}},
    ]},
    # "action"/"name" instead of "type", nested arguments, other field names.
    {"intent": "computer_task", "actions": [
        {"action": "open_app", "app": "Notepad.exe"},
        {"name": "generate_text", "arguments": {"prompt": "Write 20 words about India"}},
        {"action": "type_text", "source": "generated_text"},
    ]},
    # camelCase names, "steps" instead of "actions", intent left out.
    {"steps": [
        {"type": "openApp", "application": "notepad"},
        {"type": "generateText", "instruction": "Write 20 words about India"},
        {"type": "typeText"},
    ]},
    # A bare list.
    [
        {"type": "open_app", "app": "notepad"},
        {"type": "generate_text", "instruction": "Write 20 words about India"},
        {"type": "type_text", "source": "generated_text"},
    ],
])
def test_common_model_dialects_become_the_canonical_plan(reply):
    plan = validate_plan(coerce_plan(reply))
    assert list(plan.actions) == CANONICAL


def test_the_failure_seen_on_the_owners_pc_now_validates():
    # "Action 1 must be an object with a type" came from actions that were
    # not objects with a "type" key; the plan itself was well-formed.
    reply = {"intent": "computer_task", "actions": [
        {"open_app": "notepad"},
        {"generate_text": {"instruction": "Write 20 words about India"}},
        {"type_text": "generated_text"},
    ]}
    with pytest.raises(PlanValidationError, match="must be an object with a type"):
        validate_plan(reply)
    assert list(validate_plan(coerce_plan(reply)).actions) == CANONICAL


@pytest.mark.parametrize("reply", [
    {"intent": "computer_task", "actions": ["open_app(app='powershell')"]},
    {"intent": "computer_task", "actions": [{"open_app": "cmd"}]},
    {"intent": "computer_task", "actions": [{"run_command": {"command": "del *"}}]},
    {"intent": "computer_task", "actions": ["shell('rm -rf /')"]},
    {"intent": "computer_task", "actions": ["open_app(app=__import__('os').system('calc'))"]},
    {"intent": "computer_task", "actions": ["press_key(key='f4')"]},
    {"intent": "computer_task", "actions": [{"type_text": "anything"}]},  # no generate_text first
    {"intent": "chat", "actions": [{"type": "open_app", "app": "notepad"}]},
    {"intent": "computer_task", "actions": ["x" * 600]},
])
def test_coercion_never_lets_an_unsafe_plan_through(reply):
    with pytest.raises(PlanValidationError):
        validate_plan(coerce_plan(reply))


def test_coercion_parses_call_strings_without_evaluating_them(monkeypatch):
    import os
    ran = []
    monkeypatch.setattr(os, "system", lambda command: ran.append(command) or 0)
    coerced = coerce_plan({"actions": ["open_app(app=__import__('os').system('calc'))"]})
    assert ran == []
    assert coerced["actions"] == ["open_app(app=__import__('os').system('calc'))"]  # left as-is


def test_schema_fields_match_the_validator_exactly():
    variants = plan_json_schema()["properties"]["actions"]["items"]["anyOf"]
    by_kind = {v["properties"]["type"]["enum"][0]: v for v in variants}
    assert set(by_kind) == set(_ALLOWED)
    for kind, variant in by_kind.items():
        optional = _OPTIONAL_FIELDS.get(kind, set())
        assert set(variant["properties"]) == _ALLOWED[kind] | optional
        assert set(variant["required"]) == _ALLOWED[kind]
        assert variant["additionalProperties"] is False


# ------------------------------------------------------------
# OPEN_URL  (safe web actions for the planner)
# ------------------------------------------------------------

def test_open_url_with_https_is_valid():
    plan = validate_plan({"intent": "computer_task", "actions": [
        {"type": "open_url", "url": "https://www.youtube.com"},
    ]})
    assert plan.actions[0]["url"] == "https://www.youtube.com"


def test_open_url_accepts_an_optional_browser_and_normalises_it():
    plan = validate_plan({"intent": "computer_task", "actions": [
        {"type": "open_url", "url": "https://youtube.com", "browser": "Google Chrome"},
    ]})
    assert plan.actions[0]["browser"] == "chrome"


@pytest.mark.parametrize("url", [
    "javascript:alert(1)",
    "file:///C:/Windows/system.ini",
    "data:text/html,<script>",
    "ftp://example.com/file",
    "https://user:pass@example.com",
    "https://",
    "not a url",
    "https://example.com/has space",
    "",
])
def test_open_url_rejects_unsafe_urls(url):
    with pytest.raises(PlanValidationError):
        validate_plan({"intent": "computer_task", "actions": [
            {"type": "open_url", "url": url},
        ]})


def test_open_url_rejects_an_unknown_browser():
    with pytest.raises(PlanValidationError):
        validate_plan({"intent": "computer_task", "actions": [
            {"type": "open_url", "url": "https://example.com", "browser": "netscape"},
        ]})


def test_open_url_dialects_are_coerced():
    reply = {"actions": [
        {"link": "https://www.youtube.com", "in": "brave"},
        "open_url(https://www.google.com)",
    ]}
    plan = validate_plan(coerce_plan(reply))
    assert plan.actions[0] == {"type": "open_url", "url": "https://www.youtube.com",
                               "browser": "brave"}
    assert plan.actions[1] == {"type": "open_url", "url": "https://www.google.com"}


# ------------------------------------------------------------
# TYPE_TEXT WITH LITERAL TEXT
# ------------------------------------------------------------

def test_type_text_accepts_short_literal_text_without_generate_text():
    plan = validate_plan({"intent": "computer_task", "actions": [
        {"type": "open_url", "url": "https://www.youtube.com"},
        {"type": "type_text", "text": "lofi"},
    ]})
    assert plan.actions[1]["text"] == "lofi"


def test_type_text_needs_exactly_one_of_source_or_text():
    with pytest.raises(PlanValidationError):
        validate_plan({"intent": "computer_task", "actions": [
            {"type": "type_text"},
        ]})
    with pytest.raises(PlanValidationError):
        validate_plan({"intent": "computer_task", "actions": [
            {"type": "type_text", "source": "generated_text", "text": "lofi"},
        ]})


def test_type_text_literal_is_bounded():
    with pytest.raises(PlanValidationError):
        validate_plan({"intent": "computer_task", "actions": [
            {"type": "type_text", "text": "x" * 500},
        ]})


def test_type_text_literal_survives_coercion():
    plan = validate_plan(coerce_plan({"actions": [
        {"action": "type_text", "text": "lofi beats"},
    ]}))
    assert plan.actions[0] == {"type": "type_text", "text": "lofi beats"}
