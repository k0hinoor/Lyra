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


# ------------------------------------------------------------
# OPEN_URL AND LITERAL TYPE_TEXT DISPATCH
# ------------------------------------------------------------

def test_open_url_is_dispatched_through_the_browsers_module(monkeypatch):
    from lyra import browsers
    opened = []

    def fake_open(url, browser=None):
        opened.append((url, browser))
        return True

    monkeypatch.setattr(browsers, "open_url", fake_open)
    plan = validate_plan({"intent": "computer_task", "actions": [
        {"type": "open_url", "url": "https://www.youtube.com", "browser": "brave"},
    ]})
    result = ActionExecutor().run(plan)
    assert result.status is Status.UNKNOWN          # issued, not screen-verified
    assert opened == [("https://www.youtube.com", "brave")]


def test_open_url_failure_fails_the_task(monkeypatch):
    from lyra import browsers
    monkeypatch.setattr(browsers, "open_url", lambda url, browser=None: False)
    plan = validate_plan({"intent": "computer_task", "actions": [
        {"type": "open_url", "url": "https://www.youtube.com"},
    ]})
    result = ActionExecutor().run(plan)
    assert result.status is Status.FAILURE


def test_literal_type_text_types_the_given_text(monkeypatch):
    from lyra.computer import automation
    typed = []
    monkeypatch.setattr(automation, "type_text", typed.append)
    plan = validate_plan({"intent": "computer_task", "actions": [
        {"type": "open_url", "url": "https://www.youtube.com"},
        {"type": "type_text", "text": "lofi"},
    ]})
    result = ActionExecutor().run(plan, generate_text=lambda _i: "never used")
    assert result.status is Status.UNKNOWN
    assert typed == ["lofi"]


def test_generated_type_text_still_uses_the_writer(monkeypatch):
    from lyra.computer import automation
    typed = []
    monkeypatch.setattr(automation, "open_app", lambda app: None)
    monkeypatch.setattr(automation, "focus_app_window", lambda app: True)
    monkeypatch.setattr(automation, "type_text", typed.append)
    plan = validate_plan({"intent": "computer_task", "actions": [
        {"type": "open_app", "app": "notepad"},
        {"type": "generate_text", "instruction": "Write about India"},
        {"type": "type_text", "source": "generated_text"},
    ]})
    result = ActionExecutor().run(plan, generate_text=lambda _i: "India is diverse.")
    assert result.status is Status.UNKNOWN
    assert typed == ["India is diverse."]
