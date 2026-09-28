import threading
import time

from lyra.actions.schema import validate_plan
from lyra.computer import automation
from main import Session


class FakeMemory:
    items = []

    def add(self, _item):
        return True

    def remove(self, _item):
        return 0

    def clear(self):
        self.items = []

    def context_block(self):
        return ""


class PlannedBrain:
    def __init__(self, plan):
        self.plan = plan
        self.planned = []

    def plan_actions(self, request):
        self.planned.append(request)
        return self.plan

    def ask_stream(self, _prompt):
        yield "India is diverse and has many languages."


def test_multistep_task_is_planned_and_dispatched_safely(monkeypatch, capfd):
    calls = []
    monkeypatch.setattr(automation, "open_app", lambda app: calls.append(("open", app)))
    monkeypatch.setattr(automation, "type_text", lambda text: calls.append(("type", text)))
    plan = validate_plan({"intent": "computer_task", "actions": [
        {"type": "open_app", "app": "notepad"},
        {"type": "generate_text", "instruction": "Write about India"},
        {"type": "type_text", "source": "generated_text"},
    ]})
    brain = PlannedBrain(plan)
    session = Session(brain, FakeMemory())
    session.process("Open Notepad and write about India")
    assert brain.planned == ["Open Notepad and write about India"]
    assert calls[0] == ("open", "notepad")
    assert calls[1][0] == "type"
    assert "not yet independently verified" in capfd.readouterr().out


def test_async_task_can_be_cancelled_while_planning():
    entered = threading.Event()
    release = threading.Event()

    class SlowBrain(PlannedBrain):
        def plan_actions(self, request):
            entered.set()
            release.wait(2)
            return None

    session = Session(SlowBrain(None), FakeMemory())
    session.async_task_execution = True
    session.process("Open Notepad and write about India")
    assert entered.wait(1)
    assert session.task_active
    session.stop_active_task()
    release.set()
    session._task_thread.join(2)
    assert not session.task_active
    assert session.task_executor.stop_requested
