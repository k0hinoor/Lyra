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
