"""
============================================================
 TESTS — main.py  (Session: routing, memory, confirmations)
============================================================
"""

import pytest

import main
from lyra.skills.base import Confirmation


pytestmark = pytest.mark.usefixtures("pc")


# ------------------------------------------------------------
# TERMINATE
# ------------------------------------------------------------

def test_terminate_ends_the_session(session, capfd):
    assert session.process("terminate execution") is True
    assert "Goodbye" in capfd.readouterr().out


def test_normal_commands_keep_the_session_alive(session):
    assert session.process("tell me a joke") is False


# ------------------------------------------------------------
# SKILLS BEFORE BRAIN
# ------------------------------------------------------------

def test_skills_answer_without_asking_the_brain(session, fake_brain):
    session.process("what time is it")
    assert fake_brain.asked == []


def test_unknown_questions_go_to_the_brain(session, fake_brain):
    session.process("why is the sky blue")
    assert fake_brain.asked == ["why is the sky blue"]


def test_pc_commands_go_to_the_skills(session, fake_brain, pc):
    session.process("open notepad")

    assert pc.started == ["notepad"]
    assert fake_brain.asked == []


def test_blank_input_does_nothing(session, fake_brain):
    assert session.process("") is False
    assert fake_brain.asked == []


# ------------------------------------------------------------
# POLITE COMMANDS STILL REACH THE SKILL
# ------------------------------------------------------------

@pytest.mark.parametrize("said", [
    "can you please turn up the volume",
    "could you make it louder please",
    "hey increase the volume a bit",
    "i want you to turn the volume down",
    "turn the volume up now please",
])
def test_polite_pc_commands_are_executed_not_asked_about(session, fake_brain, pc, said):
    pc.volume["level"] = 40

    session.process(said)

    assert fake_brain.asked == [], "the brain must not answer with a how-to guide"
    assert pc.volume["calls"], "the volume must actually have been changed"


def test_a_complaint_is_fixed_instead_of_explained(session, fake_brain, pc, capfd):
    pc.volume["level"] = 20

    session.process("it's too quiet")

    assert fake_brain.asked == []
    assert pc.volume["level"] == 30
    assert "right-click" not in capfd.readouterr().out.lower()


# ------------------------------------------------------------
# MEMORY
# ------------------------------------------------------------

def test_remember(session):
    session.process("remember that my exam is on Friday")
    assert session.memory.items == ["my exam is on Friday"]


def test_remember_twice_says_it_already_knows(session, capfd):
    session.process("remember that my exam is on Friday")
    capfd.readouterr()

    session.process("remember that my exam is on Friday")
    assert "already knew" in capfd.readouterr().out
    assert len(session.memory.items) == 1


def test_what_do_you_remember(session):
    session.process("remember that my exam is on Friday")

    reply, _confirmation = session._handle_memory("what do you remember", "what do you remember")
    assert reply == "Here's what I remember: 1. my exam is on Friday"


def test_what_do_you_remember_when_empty(session):
    reply, _confirmation = session._handle_memory("what do you remember", "what do you remember")
    assert reply == "I don't remember anything yet."


def test_forget_that(session):
    session.process("remember that my exam is on Friday")
    session.process("forget that exam")
    assert session.memory.items == []


def test_forget_something_unknown(session, capfd):
    session.process("forget that homework")
    assert "wasn't in my memory" in capfd.readouterr().out


# ------------------------------------------------------------
# CONFIRMATIONS
# ------------------------------------------------------------

@pytest.fixture
def pending(session):
    calls = []
    session.pending_confirmation = Confirmation(
        prompt="Are you sure?",
        action=lambda: calls.append("ran"),
        say_on_confirm="Doing it.",
    )
    return calls


@pytest.mark.parametrize("word", ["confirm", "yes", "go ahead", "haan"])
def test_confirming_runs_the_action(session, pending, word, capfd):
    assert session.process(word) is False
    assert pending == ["ran"]
    assert session.pending_confirmation is None
    assert "Doing it." in capfd.readouterr().out


@pytest.mark.parametrize("word", ["cancel", "no", "stop", "nahi"])
def test_cancelling_does_not_run_the_action(session, pending, word, capfd):
    session.process(word)

    assert pending == []
    assert session.pending_confirmation is None
    assert "Cancelled." in capfd.readouterr().out


def test_cancel_wins_over_confirm(session, pending):
    session.process("yes but actually no")
    assert pending == []


def test_unrelated_reply_drops_the_pending_action(session, pending, fake_brain):
    session.process("why is the sky blue")

    assert pending == []
    assert session.pending_confirmation is None
    assert fake_brain.asked == ["why is the sky blue"]


def test_a_failing_action_does_not_crash_the_session(session, capfd):
    def boom():
        raise RuntimeError("nope")

    session.pending_confirmation = Confirmation("Sure?", boom, say_on_confirm="Doing it.")

    assert session.process("confirm") is False
    assert "Action error" in capfd.readouterr().out


def test_forget_everything_needs_confirmation(session):
    session.process("remember that my exam is on Friday")

    session.process("forget everything")

    assert isinstance(session.pending_confirmation, Confirmation)
    assert session.memory.items, "memory survives until the user confirms"

    session.process("confirm")
    assert session.memory.items == []


# ------------------------------------------------------------
# OUTPUT
# ------------------------------------------------------------

def test_say_prints_the_reply(session, capfd):
    session.say("hello there")
    assert "Lyra: hello there" in capfd.readouterr().out


def test_say_stream_prints_every_sentence(session, capfd):
    session.say_stream(iter(["One.", "Two."]))

    out = capfd.readouterr().out
    assert "One." in out
    assert "Two." in out


def test_say_stream_skips_blanks(session, capfd):
    session.say_stream(iter(["One.", "   ", None]))
    assert capfd.readouterr().out.count("Lyra:") == 1


def test_session_is_wired_to_a_voice_when_given_one(session, fake_brain):
    spoken = []

    class Voice:

        def speak(self, text):
            spoken.append(text)

    voiced = main.Session(fake_brain, session.memory, voice=Voice())
    voiced.process("tell me a joke")

    assert spoken


# ------------------------------------------------------------
# A WAKE PHRASE IS AN ADDRESS, NOT A COMMAND
# ------------------------------------------------------------
# Typing "hey lyra" in text mode (or saying it again while Lyra is already
# awake) used to reach the skills, and the volume skill read it as "mute".

@pytest.mark.parametrize("text", ["hey lyra", "Hey Lyra!", "lyra", "ok lyra", "hey laura"])
def test_a_bare_wake_phrase_gets_an_acknowledgement(session, fake_brain, pc, text, capfd):
    assert session.process(text) is False
    assert "Yes?" in capfd.readouterr().out
    assert fake_brain.asked == []
    assert pc.volume["calls"] == []


def test_a_command_after_the_wake_phrase_is_carried_out(session, fake_brain, capfd):
    session.process("Hey Lyra, what time is it?")
    assert "It's" in capfd.readouterr().out
    assert fake_brain.asked == []


def test_a_question_after_the_wake_phrase_reaches_the_brain_without_it(session, fake_brain):
    session.process("hey lyra why is the sky blue")
    assert fake_brain.asked == ["why is the sky blue"]


def test_goodbye_with_the_name_still_ends_the_session(session):
    assert session.process("lyra goodbye") is True


@pytest.mark.parametrize("text", ["you", "okay", "hmm", "hello", "so"])
def test_filler_heard_while_awake_never_mutes(session, pc, text):
    session.process(text)
    assert pc.volume["calls"] == []
    assert pc.volume["muted"] is False


def test_stop_after_the_wake_phrase_still_stops_an_active_task(session, capfd):
    session.task_active = True
    session.process("hey lyra stop")
    assert session.task_executor.stop_requested
    assert "Stopping" in capfd.readouterr().out


# ------------------------------------------------------------
# VOICE-TEST BUGS END-TO-END  (through the real Session)
# ------------------------------------------------------------

@pytest.mark.parametrize("said", [
    "so what is the time right now",
    "so what time is it",
    "tell me the time",
    "current time",
])
def test_time_phrasings_never_reach_the_brain(session, fake_brain, pc, said, capfd):
    assert session.process(said) is False
    assert "It's" in capfd.readouterr().out
    assert fake_brain.asked == [], "the chat model must not answer with a guess"


def test_full_screen_toggles_f11_not_brightness(session, fake_brain, pc, capfd):
    pc.brightness.level = 42

    session.process("full screen")

    assert pc.pyauto.pressed("f11")
    assert pc.brightness.level == 42
    assert fake_brain.asked == []


def test_make_it_full_screen_toggles_f11(session, fake_brain, pc):
    session.process("make it full screen")
    assert pc.pyauto.pressed("f11")
    assert pc.brightness.calls == []


def test_exit_full_screen_is_not_closing_an_app(session, fake_brain, pc, capfd):
    session.process("exit full screen")

    assert pc.pyauto.pressed("f11")
    assert "Closed" not in capfd.readouterr().out
    assert pc.shell.commands == []


def test_sleep_mode_asks_then_sleeps(session, fake_brain, pc, capfd):
    assert session.process("sleep mode") is False
    assert "confirm" in capfd.readouterr().out.lower()
    assert pc.shell.commands == []

    session.process("confirm")
    assert pc.shell.commands and pc.shell.commands[0][0] == "rundll32.exe"


def test_misheard_terminate_still_exits(session, capfd):
    assert session.process("and the terminal execution") is True
    assert "Goodbye" in capfd.readouterr().out


def test_open_brave_and_open_youtube_is_not_a_planner_task(session, fake_brain, pc):
    session.process("open brave and open youtube")

    assert pc.started == [], "the app launcher must not fire"
    assert fake_brain.asked == [], "chat must not answer"
    assert "planner" not in str(getattr(fake_brain, "planned", []))


def test_unknown_app_failure_is_spoken_not_raised(session, fake_brain, monkeypatch, capfd):
    from lyra.skills import apps

    def fail(target):
        raise FileNotFoundError(target)

    monkeypatch.setattr(apps, "_start", fail)

    assert session.process("open breathe and", raw="open, breathe and") is False
    assert "couldn't find an app called" in capfd.readouterr().out


# ------------------------------------------------------------
# EVERY REPLY IS PRINTED AND TRANSCRIBED
# ------------------------------------------------------------

def test_say_records_the_exchange_in_the_transcript(session, isolated_log_dir):
    session.last_heard = "what time is it"
    session.say("It's 3:45 PM.", handler="skill:system")

    (path,) = list(isolated_log_dir.glob("conversation-*.txt"))
    content = path.read_text(encoding="utf-8")

    assert "Heard: what time is it" in content
    assert "Handled by: skill:system" in content
    assert "Lyra: It's 3:45 PM." in content


def test_say_stream_prints_and_transcribes_the_full_reply(session, isolated_log_dir, capfd):
    session.last_heard = "tell me about rain"
    session.say_stream(iter(["Rain is condensed water. ", "It falls from clouds."]),
                       handler="chat model")

    out = capfd.readouterr().out
    assert "Lyra: Rain is condensed water." in out
    assert "Lyra: It falls from clouds." in out

    (path,) = list(isolated_log_dir.glob("conversation-*.txt"))
    content = path.read_text(encoding="utf-8")
    assert "Handled by: chat model" in content
    assert "Rain is condensed water. It falls from clouds." in content


def test_the_transcript_records_what_handled_each_exchange(session, fake_brain, pc,
                                                             isolated_log_dir):
    session.process("open notepad")
    session.process("why is the sky blue")

    (path,) = list(isolated_log_dir.glob("conversation-*.txt"))
    content = path.read_text(encoding="utf-8")

    assert "skill:apps" in content
    assert "chat model" in content


def test_a_chat_reply_is_printed_even_with_a_voice(session, fake_brain, capfd):
    spoken = []

    class Voice:
        ok = True

        def speak(self, text):
            spoken.append(text)

        def speak_stream(self, sentences):
            for sentence in sentences:
                spoken.append(sentence)

    voiced = main.Session(fake_brain, session.memory, voice=Voice())
    voiced.process("why is the sky blue")

    assert "Lyra:" in capfd.readouterr().out, "voice replies must also be printed"
    assert spoken, "and still spoken"


def test_planned_tasks_are_transcribed_as_planner(monkeypatch, capfd, isolated_log_dir):
    from lyra.actions.schema import validate_plan
    from lyra.computer import automation

    monkeypatch.setattr(automation, "open_app", lambda app: None)
    monkeypatch.setattr(automation, "focus_app_window", lambda app: True)

    plan = validate_plan({"intent": "computer_task", "actions": [
        {"type": "open_app", "app": "notepad"},
    ]})

    class PlannerBrain:
        def plan_actions(self, request):
            return plan

        def ask_stream(self, text):
            raise AssertionError("planner tasks must not reach chat")

        def write_text(self, instruction):
            return "text"

    session = main.Session(PlannerBrain(), session_memory())
    session.process("Open Notepad and write about India")

    (path,) = list(isolated_log_dir.glob("conversation-*.txt"))
    assert "Handled by: planner" in path.read_text(encoding="utf-8")


def session_memory():
    from lyra.memory import Memory
    return Memory()


# ------------------------------------------------------------
# --voice-test
# ------------------------------------------------------------

def test_voice_test_speaks_a_sample_and_reports_failure_when_silent(monkeypatch, capfd):
    from lyra import voice as voice_module

    class NoVoice:
        def __init__(self):
            self.ok = False

    # main.run_voice_test imports Voice inside; patch the source module.
    monkeypatch.setattr(voice_module, "Voice", NoVoice)

    rc = main.run_voice_test()
    out = capfd.readouterr().out
    assert rc == 1
    assert "not available" in out


def test_voice_test_speaks_with_the_current_voice_and_speed(monkeypatch, capfd):
    from lyra import config
    from lyra import voice as voice_module

    spoken = []

    class GoodVoice:
        def __init__(self):
            self.ok = True

        def speak(self, text):
            spoken.append(text)

    monkeypatch.setattr(voice_module, "Voice", GoodVoice)

    rc = main.run_voice_test()
    out = capfd.readouterr().out
    assert rc == 0
    assert str(config.VOICE_MODEL) in out
    assert spoken == [main.VOICE_TEST_SENTENCE]
