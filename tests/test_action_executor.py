from lyra.actions.executor import ActionExecutor, Status
from lyra.actions.schema import validate_plan


def test_executor_generates_then_types_without_shell_actions(monkeypatch):
    from lyra.computer import automation
    calls = []
    monkeypatch.setattr(automation, "open_app", lambda app: calls.append(("open", app)))
    monkeypatch.setattr(automation, "type_text", lambda text: calls.append(("type", text)))
    plan = validate_plan({"intent": "computer_task", "actions": [
        {"type": "open_app", "app": "notepad"},
        {"type": "generate_text", "instruction": "20 words about India"},
        {"type": "type_text", "source": "generated_text"},
    ]})
    result = ActionExecutor().run(plan, generate_text=lambda _prompt: "India is diverse.")
    assert result.status is Status.UNKNOWN  # action dispatch is not screen verification
    assert calls == [("open", "notepad"), ("type", "India is diverse.")]


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
