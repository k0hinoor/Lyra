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
import re
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
            except Exception as e:
                print(f"Action error: {e}")

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
            self.say("Going offline. Goodbye.")
            return True

        # pending shutdown/restart confirmations
        if self._check_confirmation(normalized):
            return False

        # memory commands (need the Memory instance, not in the skill router)
        reply, confirmation = self._handle_memory(normalized, raw)

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

    ear = Ear()

    voice = Voice()
    session.voice = voice

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

                # ------------------------------------------------
                # LISTEN
                # ------------------------------------------------

                state = "awake" if time.time() < awake_until else "asleep"

                try:
                    audio = recognizer.listen(
                        source,
                        timeout=config.LISTEN_TIMEOUT,
                        phrase_time_limit=config.PHRASE_TIME_LIMIT,
                    )
                except sr.WaitTimeoutError:
                    if state == "awake" and time.time() >= awake_until:
                        print("(went back to sleep)")
                    continue

                # ------------------------------------------------
                # TRANSCRIBE
                # ------------------------------------------------

                heard = ear.transcribe_audio(audio)

                if not heard:
                    continue

                print(f"You: {correct_name(heard)}")

                normalized = normalize(heard)

                # terminate works in every mode, no wake word needed
                if is_terminate(normalized):
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
                voice.stop()
                print()
                print("Lyra stopped by user.")
                break

            # ====================================================
            # OTHER ERRORS
            # ====================================================

            except Exception as e:
                print(f"Error: {e}")
                continue

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
