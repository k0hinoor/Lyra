"""
============================================================
 LYRA
============================================================
 A local-first AI voice assistant.
 Brain: Ollama (phi4-mini) | Ears: faster-whisper |
 Voice: Piper | Hands: full Windows control skills.

 Run:
   python main.py               wake-word mode ("Hey Lyra ...")
   python main.py --always      always-listening mode
   python main.py --text        type instead of talk (testing)
   python main.py --devices     list audio output devices
============================================================
"""

import argparse
import logging
import re
import threading
import time

from lyra import config
from lyra.memory import Memory
from lyra.skills import route, Confirmation
from lyra.utils import (
    correct_name,
    is_sleep,
    is_terminate,
    is_thanks,
    normalize,
    strip_politeness,
    strip_wake_word,
)


# ============================================================
# SESSION
# ============================================================

log = logging.getLogger(__name__)


def _looks_like_multistep_computer_task(text):
    """Avoid an extra planner LLM request for normal chat/simple skills."""
    text = normalize(text)
    has_connector = bool(re.search(r"\b(?:and then|then|and)\b", text))
    verbs = re.findall(
        r"\b(?:open|launch|start|write|type|press|click|double click|right click|"
        r"move|scroll|drag|drop)\b", text
    )
    return has_connector and len(verbs) >= 2


class Session:
    """
    One conversation session. Handles routing, pending
    dangerous-action confirmations, and speaking/printing.
    """

    def __init__(self, brain, memory, voice=None):
        self.brain = brain
        self.memory = memory
        self.voice = voice
        self.pending_confirmation = None
        from lyra.actions.executor import ActionExecutor
        self.task_executor = ActionExecutor()
        self.task_active = False
        self.async_task_execution = False
        self._task_thread = None

    def stop_active_task(self):
        """Cancellation hook used by UI/voice integrations and emergency controls."""
        self.task_executor.request_stop()

    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    def say(self, text):

        print("\nLyra:", text, "\n")

        if self.voice is not None:
            self.voice.speak(text)

    def say_stream(self, sentences):

        if self.voice is not None:
            self.voice.speak_stream(sentences)
        else:
            for sentence in sentences:
                if sentence and sentence.strip():
                    print("Lyra:", sentence)

    # --------------------------------------------------------
    # CONFIRMATION HANDLING
    # --------------------------------------------------------

    def _check_confirmation(self, text):
        """Returns True if the input was consumed by a pending confirmation."""

        if self.pending_confirmation is None:
            return False

        confirmed = any(word in text for word in config.CONFIRM_WORDS)
        cancelled = any(word in text for word in config.CANCEL_WORDS)

        if confirmed and not cancelled:

            confirmation = self.pending_confirmation
            self.pending_confirmation = None

            say_on_confirm = confirmation.say_on_confirm or "Done."

            print("\nLyra:", say_on_confirm, "\n")

            try:
                confirmation.action()
            except Exception as error:
                log.exception("Confirmed action failed")
                print(f"Action error: {error}")

            if self.voice is not None:
                self.voice.speak(say_on_confirm)

            return True

        if cancelled:

            self.pending_confirmation = None
            self.say("Cancelled.")

            return True

        # something else said — drop the pending action silently
        self.pending_confirmation = None

        return False

    # --------------------------------------------------------
    # MEMORY COMMANDS
    # --------------------------------------------------------

    def _handle_memory(self, text, raw):
        """
        Returns (reply, confirmation) — (None, None) if the input
        is not a memory command.
        """

        # remember that ...
        match = re.match(r"^(?:remember|note) that (.+)$", raw, re.IGNORECASE)

        if match:
            item = match.group(1).strip()

            if self.memory.add(item):
                return "I'll remember that.", None
            return "I already knew that.", None

        # what do you remember
        if re.match(
            r"^what (?:do you|all do you|all you) remember(?: so far| now)?$",
            text,
        ) or text in ("show memory", "list memory", "show my memory"):

            if not self.memory.items:
                return "I don't remember anything yet.", None

            listed = ". ".join(
                f"{i + 1}. {item}" for i, item in enumerate(self.memory.items[-10:])
            )
            return "Here's what I remember: " + listed, None

        # forget that ...
        match = re.match(r"^(?:forget|delete) (?:that|about) (.+)$", text)

        if match:
            removed = self.memory.remove(match.group(1))

            if removed:
                return "Forgotten.", None
            return "That wasn't in my memory.", None

        # forget everything (dangerous — confirm)
        if text in ("forget everything", "clear your memory", "clear memory", "wipe memory"):

            return None, Confirmation(
                prompt=(
                    "This deletes everything I remember. "
                    "Say confirm to wipe it, or cancel."
                ),
                action=self.memory.clear,
                say_on_confirm="Memory wiped clean.",
            )

        return None, None

    def _execute_planned_task(self, raw):
        try:
            plan = self.brain.plan_actions(raw)
            if self.task_executor.stop_requested:
                self.say("The task was stopped before any action was run.")
                return
            if plan is None:
                self.say("I couldn't create a valid, safe action plan for that task.")
                return
            # write_text, not the chat stream: the chat voice adds spoken
            # preambles, keeps the text in conversation history, and on an
            # Ollama error yields a fallback sentence that would then be
            # typed into the document. write_text raises instead.
            result = self.task_executor.run(plan, generate_text=self.brain.write_text)
            if result.status.value == "FAILURE":
                failed = next((item for item in result.results if item.status.value == "FAILURE"), None)
                detail = failed.detail if failed else "An action failed."
                self.say("The task stopped because an action failed: " + detail[:180])
            elif result.status.value == "STOPPED":
                self.say("The task was stopped.")
            else:
                self.say("I issued the planned actions. Their on-screen results are not yet independently verified.")
        except Exception:
            log.exception("Unexpected task execution error")
            self.say("The task stopped because of an internal action error. See the LYRA log.")
        finally:
            self.task_active = False

    def _start_planned_task(self, raw):
        if self.task_active:
            self.say("I am already working on a computer task. Say stop to cancel it.")
            return
        self.task_executor.reset_stop()
        self.task_active = True
        if self.async_task_execution:
            self._task_thread = threading.Thread(
                target=self._execute_planned_task, args=(raw,), daemon=True,
                name="lyra-computer-task",
            )
            self.say("Planning and carrying out the task. Say stop to cancel it.")
            self._task_thread.start()
        else:
            self._execute_planned_task(raw)

    # --------------------------------------------------------
    # PROCESS ONE COMMAND
    # --------------------------------------------------------

    def process(self, text, raw=None):
        """Process one already-wake-stripped command. Returns True to exit."""

        normalized = strip_politeness(normalize(text))
        raw = raw if raw is not None else text

        if not normalized:
            return False

        # terminate
        if is_terminate(normalized):
            self.stop_active_task()
            self.say("Going offline. Goodbye.")
            return True

        # A wake phrase at the start is an address, not part of the command:
        # "hey lyra" typed in text mode, or said again during the follow-up
        # window, used to reach the skills (and the volume skill read it as
        # "mute"). Checked after terminate so "lyra goodbye" still exits.
        woke, remainder = strip_wake_word(normalize(text))
        if woke:
            if not remainder:
                self.say("Yes?")
                return False
            return self.process(remainder, raw=remainder)

        if normalized in {"stop", "stop task", "cancel task", "abort task"} and self.task_active:
            self.stop_active_task()
            self.say("Stopping the active task safely.")
            return False

        if self.task_active:
            self.say("I am still working. Say stop to cancel the active task.")
            return False

        # pending shutdown/restart confirmations
        if self._check_confirmation(normalized):
            return False

        if normalized in {"stop", "stop task", "cancel task", "abort task"}:
            self.say("There is no active computer task.")
            return False

        # memory commands (need the Memory instance, not in the skill router)
        reply, confirmation = self._handle_memory(normalized, raw)

        if reply is None and confirmation is None and _looks_like_multistep_computer_task(raw):
            self._start_planned_task(raw)
            return False

        if reply is None and confirmation is None:
            # skills (PC control)
            reply, confirmation = route(normalized, raw)

        if confirmation is not None:
            self.pending_confirmation = confirmation
            self.say(confirmation.prompt)
            return False

        if reply is not None:
            self.say(reply)
            return False

        # brain (LLM) — streamed sentence by sentence
        self.say_stream(self.brain.ask_stream(raw.strip()))

        return False


# ============================================================
# TEXT MODE
# ============================================================

def run_text_mode(session):

    print()
    print("Text mode — type commands. 'exit' to quit.")
    print()

    while True:

        try:
            line = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not line:
            continue

        normalized = normalize(line)

        if normalized in ("exit", "quit", "bye"):
            break

        if session.process(line, raw=line):
            break

    print()
    print("Lyra offline.")


# ============================================================
# VOICE MODE
# ============================================================

def run_voice_mode(session, always_listening):

    import speech_recognition as sr

    from lyra.ear import Ear
    from lyra.voice import Voice
    from lyra.wake import WakeWordDetector

    ear = Ear()
    wake_detector = WakeWordDetector()

    voice = Voice()
    session.voice = voice
    session.async_task_execution = True

    recognizer = sr.Recognizer()
    recognizer.pause_threshold = config.PAUSE_THRESHOLD
    recognizer.non_speaking_duration = config.NON_SPEAKING_DURATION
    recognizer.phrase_threshold = 0.2

    print()

    with sr.Microphone() as source:

        print("Calibrating microphone...")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        print("Microphone ready.")

        print()
        print("====================================")
        print("          LYRA IS ONLINE")
        print("====================================")
        print()

        if always_listening:
            print("Mode: ALWAYS LISTENING")
        else:
            print(f"Mode: WAKE WORD — say 'Hey {config.WAKE_WORD.capitalize()}'")

        print(f"Kill command: 'terminate execution'")
        print("Emergency stop: Ctrl+C")
        print()

        voice.speak("Online.")

        if not always_listening:
            print("Waiting for the wake word...")
        print()

        awake_until = 0.0

        while True:

            try:

                # Do not capture the assistant's own playback as user speech.
                if voice.is_speaking:
                    time.sleep(0.1)
                    continue

                # ------------------------------------------------
                # LISTEN
                # ------------------------------------------------

                state = "awake" if session.task_active or time.time() < awake_until else "asleep"

                try:
                    phrase_limit = (
                        config.WAKE_WINDOW_SECONDS
                        if state == "asleep" and not always_listening
                        else config.PHRASE_TIME_LIMIT
                    )
                    audio = recognizer.listen(
                        source,
                        timeout=config.LISTEN_TIMEOUT,
                        phrase_time_limit=phrase_limit,
                    )
                except sr.WaitTimeoutError:
                    if state == "awake" and time.time() >= awake_until:
                        print("(went back to sleep)")
                    continue

                # ------------------------------------------------
                # WAKE GATE / COMMAND TRANSCRIPTION
                # ------------------------------------------------

                lightweight_wake_hit = False
                wake_gate_matched = False
                wake_gate_remainder = ""
                if not always_listening and state == "asleep":
                    matched, _wake_remainder, wake_transcript = wake_detector.detect(
                        audio, fallback_transcriber=ear.transcribe_audio
                    )
                    # Keep the global spoken termination phrase available in
                    # lightweight mode; it is checked before the normal wake gate.
                    if is_terminate(normalize(wake_transcript)):
                        session.stop_active_task()
                        session.say("Going offline. Goodbye.")
                        break
                    if not matched:
                        continue
                    wake_gate_matched = True
                    wake_gate_remainder = _wake_remainder
                    lightweight_wake_hit = wake_detector.lightweight
                    # Run command-quality Whisper only on the short clip after
                    # the inexpensive wake recognizer has accepted a wake phrase.
                    heard = ear.transcribe_audio(audio) if lightweight_wake_hit else wake_transcript
                else:
                    heard = ear.transcribe_audio(audio)

                if not heard:
                    continue

                print(f"You: {correct_name(heard)}")

                normalized = normalize(heard)

                # terminate works in every mode, no wake word needed
                if is_terminate(normalized):
                    session.stop_active_task()
                    session.say("Going offline. Goodbye.")
                    break

                # ------------------------------------------------
                # ROUTE: ALWAYS MODE vs WAKE MODE
                # ------------------------------------------------

                if always_listening:

                    if is_sleep(normalized) or is_thanks(normalized):
                        session.say("Okay.")
                        continue

                    exit_now = session.process(heard, raw=heard)

                else:

                    awake = time.time() < awake_until

                    if awake:

                        if is_sleep(normalized) or is_thanks(normalized):
                            if config.SPEAK_BEEP:
                                voice.beep()
                            awake_until = 0.0
                            session.say("Okay, going back to sleep.")
                            continue

                        exit_now = session.process(heard, raw=heard)

                    else:

                        matched, remainder = strip_wake_word(normalized)
                        if not matched and wake_gate_matched:
                            # Vosk has already verified the wake shape. If the
                            # higher-accuracy recognizer drops the wake phrase,
                            # retain Vosk's remainder rather than losing wake.
                            matched, remainder = True, wake_gate_remainder

                        if not matched:
                            continue        # background chatter — ignore

                        if not remainder:
                            # just the wake word — wake up
                            if config.SPEAK_BEEP:
                                voice.beep()
                            awake_until = time.time() + config.FOLLOW_UP_SECONDS
                            print(f"(awake for {config.FOLLOW_UP_SECONDS}s — "
                                  "keep talking, or say 'go to sleep')")
                            continue

                        exit_now = session.process(remainder, raw=remainder)

                if exit_now:
                    break

                # stay awake a while after every successful exchange
                if not always_listening:
                    awake_until = time.time() + config.FOLLOW_UP_SECONDS

            # ====================================================
            # CTRL+C
            # ====================================================

            except KeyboardInterrupt:
                session.stop_active_task()
                voice.stop()
                print()
                print("Lyra stopped by user.")
                break

            # ====================================================
            # OTHER ERRORS
            # ====================================================

            except Exception:
                log.exception("Unexpected voice-loop error")
                continue

    voice.stop()
    print()
    print("Lyra offline.")


# ============================================================
# AUDIO DEVICE LISTING
# ============================================================

def list_devices():

    try:
        import sounddevice as sd
    except Exception as e:
        print(f"sounddevice not available: {e}")
        return

    print()
    print(sd.query_devices())
    print()
    print("Set your output device in lyra/config.py -> OUTPUT_DEVICE = <index>")
    print("(None = Windows default)")


# ============================================================
# STARTUP
# ============================================================

def main():

    parser = argparse.ArgumentParser(description="Lyra — local AI voice assistant")
    parser.add_argument("--text", action="store_true",
                        help="type commands instead of talking")
    parser.add_argument("--always", action="store_true",
                        help="always-listening mode (no wake word)")
    parser.add_argument("--devices", action="store_true",
                        help="list audio output devices and exit")
    args = parser.parse_args()

    from lyra.logging_setup import configure_logging
    configure_logging(config.LOG_DIR, config.LOG_LEVEL)

    if args.devices:
        list_devices()
        return

    memory = Memory()

    from lyra.brain import Brain

    brain = Brain(memory)
    session = Session(brain, memory, voice=None)

    if args.text:
        run_text_mode(session)
    else:
        run_voice_mode(session, always_listening=args.always)


if __name__ == "__main__":
    main()
