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
