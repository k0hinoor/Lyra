"""
============================================================
 TESTS — lyra/brain.py
============================================================
"""

import json

import pytest

from lyra import brain as brain_module
from lyra import config
from lyra.memory import Memory

from conftest import FakeResponse


def ollama_lines(*chunks):
    """Build fake Ollama streaming lines out of raw token strings."""
    return [
        json.dumps({"message": {"content": chunk}, "done": False})
        for chunk in chunks
    ]


@pytest.fixture
def brain(monkeypatch):
    """A Brain whose warm-up call goes nowhere."""
    monkeypatch.setattr(brain_module.requests, "post", lambda *a, **k: FakeResponse())
    return brain_module.Brain(Memory())


# ------------------------------------------------------------
# PROMPT BUILDING
# ------------------------------------------------------------

def test_system_prompt_comes_first(brain):
    messages = brain._messages("hello")

    assert messages[0]["role"] == "system"
    assert config.USER_NAME in messages[0]["content"]
    assert messages[-1] == {"role": "user", "content": "hello"}


def test_memory_is_injected_into_the_system_prompt(brain):
    brain.memory.add("my exam is on Friday")

    system_prompt = brain._messages("hello")[0]["content"]

    assert "my exam is on Friday" in system_prompt


def test_history_is_sent_to_the_model(brain):
    brain.history = [
        {"role": "user", "content": "one"},
        {"role": "assistant", "content": "two"},
    ]

    messages = brain._messages("three")

    assert [m["content"] for m in messages[1:]] == ["one", "two", "three"]


def test_history_is_capped(brain):
    brain.history = [
        {"role": "user", "content": f"turn {i}"} for i in range(50)
    ]

    messages = brain._messages("now")

    assert len(messages) == config.HISTORY_MESSAGES + 2      # system + user
    assert messages[1]["content"] == f"turn {50 - config.HISTORY_MESSAGES}"


# ------------------------------------------------------------
# OPERATE, DON'T INSTRUCT
# ------------------------------------------------------------
# The bug this guards: asked to turn the volume up, Lyra read out
# a manual for Windows, macOS and phones instead of doing it.

def test_the_prompt_forbids_answering_with_instructions(brain):
    system_prompt = brain._messages("hello")[0]["content"].lower()

    assert "never reply with instructions" in system_prompt
    assert "you are not a manual" in system_prompt
    assert "here is how you do it" in system_prompt


def test_the_prompt_tells_the_brain_what_it_can_do(brain):
    system_prompt = brain._messages("hello")[0]["content"].lower()

    for capability in ("volume", "brightness", "clipboard", "windows"):
        assert capability in system_prompt


def test_the_prompt_stays_a_single_voice_friendly_block(brain):
    system_prompt = brain._messages("hello")[0]["content"]

    assert "no markdown" in system_prompt.lower()
    assert "spoken out loud" in system_prompt.lower()


# ------------------------------------------------------------
# STREAMING
# ------------------------------------------------------------

def test_stream_yields_sentences(monkeypatch, brain):
    chunks = [
        "The weather is nice today. ",
        "Do you want to go for a walk? ",
        "I think we should. ",
    ]
    monkeypatch.setattr(
        brain_module.requests,
        "post",
        lambda *a, **k: FakeResponse(lines=ollama_lines(*chunks)),
    )

    assert list(brain.ask_stream("how is the weather")) == [
        "The weather is nice today.",
        "Do you want to go for a walk?",
        "I think we should.",
    ]


def test_stream_starts_speaking_before_the_reply_is_complete(monkeypatch, brain):
    chunks = ["The weather is nice today. ", "Do you want to go for a walk? "]

    monkeypatch.setattr(
        brain_module.requests,
        "post",
        lambda *a, **k: FakeResponse(lines=ollama_lines(*chunks)),
    )

    stream = brain.ask_stream("how is the weather")

    first = next(stream)                       # no need to drain the reply first
    assert first == "The weather is nice today."
    assert next(stream) == "Do you want to go for a walk?"


def test_stream_keeps_the_tail(monkeypatch, brain):
    monkeypatch.setattr(
        brain_module.requests,
        "post",
        lambda *a, **k: FakeResponse(
            lines=ollama_lines("This is the first sentence. And a tail")
        ),
    )

    assert list(brain.ask_stream("hi")) == ["This is the first sentence.", "And a tail"]


def test_stream_ignores_empty_tokens(monkeypatch, brain):
    lines = ollama_lines("Some text here. ") + [
        json.dumps({"message": {"content": ""}, "done": False}),
        json.dumps({"message": {}, "done": True}),
    ]

    monkeypatch.setattr(
        brain_module.requests, "post", lambda *a, **k: FakeResponse(lines=lines)
    )

    assert list(brain.ask_stream("hi")) == ["Some text here."]


def test_stream_records_the_conversation(monkeypatch, brain):
    monkeypatch.setattr(
        brain_module.requests,
        "post",
        lambda *a, **k: FakeResponse(lines=ollama_lines("Here is a long enough answer. ")),
    )

    list(brain.ask_stream("what is up"))

    assert brain.history[-2] == {"role": "user", "content": "what is up"}
    assert brain.history[-1]["role"] == "assistant"
    assert "Here is a long enough answer." in brain.history[-1]["content"]


def test_stream_trims_old_history(monkeypatch, brain):
    brain.history = [
        {"role": "user", "content": f"turn {i}"} for i in range(40)
    ]
    monkeypatch.setattr(
        brain_module.requests,
        "post",
        lambda *a, **k: FakeResponse(lines=ollama_lines("Another long enough answer. ")),
    )

    list(brain.ask_stream("new question"))

    assert len(brain.history) == config.HISTORY_MESSAGES * 2
    assert brain.history[-2]["content"] == "new question"


def test_offline_brain_says_something_useful(monkeypatch, brain):
    def boom(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(brain_module.requests, "post", boom)

    assert list(brain.ask_stream("hi")) == [brain_module.CONNECTION_FALLBACK]


def test_a_broken_stream_still_speaks_the_fallback(monkeypatch, brain):
    monkeypatch.setattr(
        brain_module.requests,
        "post",
        lambda *a, **k: FakeResponse(lines=["not json at all"]),
    )

    assert list(brain.ask_stream("hi")) == [brain_module.CONNECTION_FALLBACK]


def test_the_request_asks_for_a_stream(monkeypatch, brain):
    payloads = []

    def fake_post(url, json=None, **kwargs):
        payloads.append((url, json, kwargs))
        return FakeResponse(lines=ollama_lines("Reply. "))

    monkeypatch.setattr(brain_module.requests, "post", fake_post)

    list(brain.ask_stream("hi"))

    url, payload, kwargs = payloads[-1]

    assert url == config.OLLAMA_URL
    assert payload["stream"] is True
    assert payload["model"] == config.OLLAMA_MODEL
    assert payload["keep_alive"] == config.OLLAMA_KEEP_ALIVE
    assert payload["options"]["num_predict"] == config.MAX_REPLY_TOKENS
    assert kwargs["stream"] is True


# ------------------------------------------------------------
# COMPUTER-TASK PLANNING
# ------------------------------------------------------------

from lyra.actions.schema import validate_plan  # noqa: E402


def test_the_example_shown_to_the_model_is_a_valid_plan():
    assert validate_plan(brain_module.PLAN_EXAMPLE).actions[0]["type"] == "open_app"


def test_the_planner_prompt_spells_out_the_action_objects():
    prompt = brain_module._planner_instruction("open notepad and write about india")
    assert '{"type": "open_app", "app": APP_NAME}' in prompt
    assert json.dumps(brain_module.PLAN_EXAMPLE) in prompt
    assert prompt.endswith("Task: open notepad and write about india")


def _plan_reply(content, status_code=200):
    return FakeResponse(payload={"message": {"content": content}}, status_code=status_code)


def test_plan_request_sends_the_schema_as_the_format(monkeypatch, brain):
    sent = []

    def post(url, json=None, **kwargs):
        sent.append(json)
        return _plan_reply(__import__("json").dumps(brain_module.PLAN_EXAMPLE))

    monkeypatch.setattr(brain_module.requests, "post", post)
    plan = brain.plan_actions("open notepad and write a poem")
    assert plan is not None and len(plan.actions) == 3
    assert isinstance(sent[0]["format"], dict)            # structured outputs
    assert sent[0]["format"]["required"] == ["intent", "actions"]


def test_old_ollama_without_schema_support_falls_back_to_json_mode(monkeypatch, brain):
    formats = []

    def post(url, json=None, **kwargs):
        formats.append(json["format"] if isinstance(json["format"], str) else "schema")
        if len(formats) == 1:
            return _plan_reply("", status_code=400)
        return _plan_reply(__import__("json").dumps(brain_module.PLAN_EXAMPLE))

    monkeypatch.setattr(brain_module.requests, "post", post)
    assert brain.plan_actions("open notepad and write a poem") is not None
    assert formats == ["schema", "json"]


def test_a_dialect_reply_is_recovered_into_a_plan(monkeypatch, brain):
    reply = {"intent": "computer_task", "actions": [
        "open_app(app=notepad)",
        'generate_text(instruction="Write 20 words about India")',
        "type_text(source=generated_text)",
    ]}
    monkeypatch.setattr(brain_module.requests, "post",
                        lambda *a, **k: _plan_reply(json.dumps(reply)))
    plan = brain.plan_actions("open notepad and write 20 words about india")
    assert [a["type"] for a in plan.actions] == ["open_app", "generate_text", "type_text"]


def test_a_rejected_plan_logs_what_the_model_said(monkeypatch, brain, caplog):
    reply = '{"intent": "computer_task", "actions": [{"type": "run_command", "command": "whoami"}]}'
    monkeypatch.setattr(brain_module.requests, "post", lambda *a, **k: _plan_reply(reply))
    with caplog.at_level("WARNING"):
        assert brain.plan_actions("do something odd") is None
    assert "run_command" in caplog.text        # the raw reply is in the log


# ------------------------------------------------------------
# WRITING TEXT FOR A TASK
# ------------------------------------------------------------

def test_write_text_uses_the_writer_prompt_and_leaves_history_alone(monkeypatch, brain):
    sent = []

    def post(url, json=None, **kwargs):
        sent.append(json)
        return FakeResponse(payload={"message": {"content": "India is vast and varied."}})

    monkeypatch.setattr(brain_module.requests, "post", post)
    assert brain.write_text("Write 5 words about India") == "India is vast and varied."
    assert sent[0]["messages"][0]["content"] == brain_module.WRITER_SYSTEM_PROMPT
    assert sent[0]["stream"] is False
    assert brain.history == []


@pytest.mark.parametrize("raw, cleaned", [
    ('"India is vast."', "India is vast."),
    ("```\nIndia is vast.\n```", "India is vast."),
    ("“India is vast.”", "India is vast."),
    ('"Hi," she said. "Bye."', '"Hi," she said. "Bye."'),     # inner quotes: left alone
    ("India's rivers are long.", "India's rivers are long."),
])
def test_written_text_loses_wrapping_but_keeps_its_own_quotes(raw, cleaned):
    assert brain_module._clean_written_text(raw) == cleaned


def test_write_text_raises_instead_of_returning_an_error_sentence(monkeypatch, brain):
    monkeypatch.setattr(brain_module.requests, "post",
                        lambda *a, **k: FakeResponse(payload={}, status_ok=False))
    with pytest.raises(Exception):
        brain.write_text("Write about India")
    monkeypatch.setattr(brain_module.requests, "post",
                        lambda *a, **k: FakeResponse(payload={"message": {"content": "  "}}))
    with pytest.raises(RuntimeError):
        brain.write_text("Write about India")


# ------------------------------------------------------------
# THE CHAT MODEL MUST NEVER CLAIM ACTIONS IT CANNOT DO
# ------------------------------------------------------------

def test_the_prompt_forbids_claiming_actions(brain):
    prompt = brain._messages("hello")[0]["content"].lower()

    assert "never claim to have done anything" in prompt
    assert "can't do that one" in prompt
    assert "not carried out" in prompt


def test_the_prompt_says_lyra_cannot_see_the_screen(brain):
    prompt = brain._messages("hello")[0]["content"].lower()

    assert "cannot see the screen" in prompt


def test_the_prompt_no_longer_says_the_chat_model_controls_the_pc(brain):
    prompt = brain._messages("hello")[0]["content"].lower()

    assert "you operate this computer" not in prompt
    assert "just say it is done" not in prompt


# ------------------------------------------------------------
# CURRENT DATE/TIME IN EVERY REQUEST
# ------------------------------------------------------------

import datetime as _datetime  # noqa: E402


def test_the_system_prompt_carries_the_current_datetime(brain):
    real_datetime = _datetime.datetime          # keep the class before patching

    class FixedDatetime:
        @staticmethod
        def now():
            return real_datetime(2026, 9, 29, 15, 45)

    line = brain_module.current_datetime_line(real_datetime(2026, 9, 29, 15, 45))
    assert line == "Current date and time: Tuesday 29 September 2026, 3:45 PM."

    import lyra.brain as module
    original = module.datetime.datetime
    module.datetime.datetime = FixedDatetime
    try:
        prompt = brain._messages("hello")[0]["content"]
    finally:
        module.datetime.datetime = original

    assert line in prompt


def test_the_datetime_is_refreshed_on_every_request(brain):
    real_datetime = _datetime.datetime          # keep the class before patching

    class MovingDatetime:
        counter = 0

        @staticmethod
        def now():
            MovingDatetime.counter += 1
            return real_datetime(2026, 9, 29, 10, MovingDatetime.counter)

    import lyra.brain as module
    original = module.datetime.datetime
    module.datetime.datetime = MovingDatetime
    try:
        first = brain._messages("hello")[0]["content"]
        second = brain._messages("hello")[0]["content"]
    finally:
        module.datetime.datetime = original

    assert "10:01 AM" in first
    assert "10:02 AM" in second


# ------------------------------------------------------------
# PLANNER KNOWS ABOUT open_url AND LITERAL type_text
# ------------------------------------------------------------

def test_the_planner_prompt_describes_open_url():
    prompt = brain_module._planner_instruction("open youtube in brave and search for lofi")
    assert '{"type": "open_url", "url": "https://...", "browser": BROWSER}' in prompt
    assert "http:// or https://" in prompt


def test_the_planner_prompt_describes_literal_type_text():
    prompt = brain_module._planner_instruction("open youtube and search for lofi")
    assert '{"type": "type_text", "text": SHORT_TEXT}' in prompt
