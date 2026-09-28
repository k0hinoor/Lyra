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
