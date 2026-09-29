from lyra.actions.executor import ActionExecutor, Status
from lyra.actions.schema import validate_plan


def test_executor_generates_then_types_without_shell_actions(monkeypatch):
    from lyra.computer import automation
    calls = []
    monkeypatch.setattr(automation, "open_app", lambda app: calls.append(("open", app)))
    monkeypatch.setattr(automation, "type_text", lambda text: calls.append(("type", text)))
    monkeypatch.setattr(
        automation, "focus_app_window", lambda app: calls.append(("focus", app)) or True
    )
    plan = validate_plan({"intent": "computer_task", "actions": [
        {"type": "open_app", "app": "notepad"},
        {"type": "generate_text", "instruction": "20 words about India"},
        {"type": "type_text", "source": "generated_text"},
    ]})
    result = ActionExecutor().run(plan, generate_text=lambda _prompt: "India is diverse.")
    assert result.status is Status.UNKNOWN  # action dispatch is not screen verification
    # The opened app is brought to the front before a single key is sent.
    assert calls == [("open", "notepad"), ("focus", "notepad"), ("type", "India is diverse.")]


def test_nothing_is_typed_when_the_opened_app_cannot_be_focused(monkeypatch):
    from lyra.computer import automation
    typed = []
    monkeypatch.setattr(automation, "open_app", lambda app: None)
    monkeypatch.setattr(automation, "type_text", typed.append)
    monkeypatch.setattr(automation, "focus_app_window", lambda app: False)
    plan = validate_plan({"intent": "computer_task", "actions": [
        {"type": "open_app", "app": "notepad"},
        {"type": "generate_text", "instruction": "20 words about India"},
        {"type": "type_text", "source": "generated_text"},
    ]})
    result = ActionExecutor().run(plan, generate_text=lambda _prompt: "India is diverse.")
    assert result.status is Status.FAILURE
    assert typed == []
    assert "front" in result.results[-1].detail


def test_keys_are_sent_without_a_focus_step_when_no_app_was_opened(monkeypatch):
    from lyra.computer import automation
    pressed = []

    def refuse_focus(app):
        raise AssertionError("no app was opened, so there is nothing to focus")

    monkeypatch.setattr(automation, "press_key", pressed.append)
    monkeypatch.setattr(automation, "focus_app_window", refuse_focus)
    plan = validate_plan({"intent": "computer_task", "actions": [
        {"type": "press_key", "key": "enter"},
    ]})
    result = ActionExecutor().run(plan)
    assert result.status is Status.UNKNOWN
    assert pressed == ["enter"]


def test_exact_word_count_is_checked_before_typing(monkeypatch):
    from lyra.computer import automation
    typed = []
    monkeypatch.setattr(automation, "type_text", typed.append)
    plan = validate_plan({"intent": "computer_task", "actions": [
        {"type": "generate_text", "instruction": "Write exactly 3 words about India"},
        {"type": "type_text", "source": "generated_text"},
    ]})
    generated = iter(["India is a diverse nation", "India is a vast and colorful nation"] )
    result = ActionExecutor().run(plan, generate_text=lambda _prompt: next(generated))
    assert result.status is Status.FAILURE
    assert typed == []


def test_executor_stops_before_dispatching_next_step(monkeypatch):
    from lyra.computer import automation
    calls = []
    executor = ActionExecutor(observer=lambda action: (executor.request_stop() or None))
    monkeypatch.setattr(automation, "press_key", lambda key: calls.append(key))
    plan = validate_plan({"intent": "computer_task", "actions": [
        {"type": "press_key", "key": "enter"},
        {"type": "press_key", "key": "esc"},
    ]})
    result = executor.run(plan)
    assert calls == ["enter"]
    assert result.status is Status.STOPPED
