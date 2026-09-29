"""
============================================================
 LYRA BRAIN
============================================================
 Talks to the local LLM through Ollama.

 Key speed trick: responses are STREAMED and split into
 sentences, so Piper starts speaking the first sentence
 while the rest is still being generated.
============================================================
"""

import datetime
import json
import logging
import re
import threading

import requests

from .actions.schema import PlanValidationError, coerce_plan, plan_json_schema, validate_plan
from .computer.automation import HOTKEY_KEYS, PRESSABLE_KEYS

log = logging.getLogger(__name__)

from . import config
from .utils import SentenceSplitter

CONNECTION_FALLBACK = (
    "I can't reach my local brain. "
    "Is Ollama running?"
)

SYSTEM_PROMPT = (
    "You are Lyra, " + config.USER_NAME + "'s personal AI assistant, "
    "running fully local on their PC. This conversation channel is for "
    "talking only; Lyra's separate command system carries out actions "
    "on the PC before you are ever asked.\n"
    "Your name is Lyra. Never say you were made by any company, "
    "and never identify as any other AI or model.\n"
    "You are helpful, concise, natural and conversational.\n"
    "\n"
    "IMPORTANT — you cannot control the computer from here:\n"
    "- Requests about the volume, brightness and mute, opening or closing "
    "apps, files, folders, settings, windows, tabs, the keyboard, the "
    "clipboard, media playback, power, sleep mode, turbo modes and "
    "similar are handled elsewhere. If such a request reaches you, it "
    "was NOT carried out.\n"
    "- So never claim to have done anything, and never say it is done. "
    "In one short sentence, say briefly that you can't do that one.\n"
    "- You cannot see the screen, any window, the camera or the desktop, "
    "and you have no clock of your own; never describe what is on "
    "screen as if you saw it, and never invent the time or date.\n"
    "- You are not a manual: never reply with instructions. No steps, no "
    "'right-click the sound icon', no 'go to Settings', no 'press these "
    "keys', no menus, no key shortcuts, no 'here is how you do it'.\n"
    "- If something is genuinely beyond Lyra, say so in one short "
    "sentence instead of describing where the button is.\n"
    "\n"
    "IMPORTANT — your replies are spoken out loud through a voice, so:\n"
    "- Answer in plain spoken sentences only.\n"
    "- No markdown, no lists, no code blocks, no emojis, no symbols.\n"
    "- Keep answers to one or three sentences unless asked for detail.\n"
    "- Do not add unasked advice, encouragement or follow-up topics.\n"
    "- Do not mention memories unless they are directly relevant.\n"
)


def current_datetime_line(now=None):
    """The local date and time, injected fresh into every request."""
    now = now or datetime.datetime.now()
    return (
        f"Current date and time: {now.strftime('%A %d %B %Y')}, "
        f"{now.strftime('%I:%M %p').lstrip('0')}."
    )

# ------------------------------------------------------------
# COMPUTER-TASK PLANNING / WRITING PROMPTS
# ------------------------------------------------------------

# Shown to the model verbatim. A test asserts it passes validate_plan(), so
# the example can never teach a shape the validator would reject.
PLAN_EXAMPLE = {
    "intent": "computer_task",
    "actions": [
        {"type": "open_app", "app": "notepad"},
        {"type": "generate_text", "instruction": "Write a short poem about the rain."},
        {"type": "type_text", "source": "generated_text"},
    ],
}

PLANNER_SYSTEM_PROMPT = "You turn desktop tasks into JSON action plans. Reply with JSON only."

WRITER_SYSTEM_PROMPT = (
    "You write text that is typed straight into a document on the user's PC. "
    "Output only the requested text itself: no introduction such as 'Sure' or "
    "'Here is', no title unless one is asked for, no quotation marks around it, "
    "and no explanation or closing remark. Follow the requested topic and length."
)


def _planner_instruction(user_text):
    return (
        "Turn the user's desktop task into a JSON action plan.\n"
        'Reply with one JSON object: {"intent": "computer_task", "actions": [...]} '
        "with 1 to 8 actions, in order.\n"
        'Every action is an object with a "type" field and exactly these fields:\n'
        '{"type": "open_app", "app": APP_NAME}\n'
        '{"type": "open_url", "url": "https://...", "browser": BROWSER}\n'
        '{"type": "generate_text", "instruction": WHAT_TO_WRITE}\n'
        '{"type": "type_text", "source": "generated_text"}\n'
        '{"type": "type_text", "text": SHORT_TEXT}\n'
        '{"type": "press_key", "key": KEY}\n'
        '{"type": "hotkey", "keys": [KEY, KEY]}\n'
        '{"type": "move_mouse", "x": X, "y": Y}\n'
        '{"type": "click", "button": "left", "clicks": 1}\n'
        '{"type": "scroll", "direction": "down", "amount": 3}\n'
        '{"type": "drag_drop", "start_x": X, "start_y": Y, "end_x": X, "end_y": Y}\n'
        "open_url opens a website; the URL must start with http:// or https:// "
        "and the optional browser is one of: brave, chrome, edge, firefox.\n"
        "To type short text the user gave (like a search query): type_text with "
        '"text". To write longer text: generate_text, then type_text with '
        '"source": "generated_text".\n'
        "press_key KEY is one of: " + ", ".join(sorted(PRESSABLE_KEYS)) + ".\n"
        "hotkey keys come from: " + ", ".join(sorted(HOTKEY_KEYS)) + ".\n"
        "To write something: open_app, then generate_text, then type_text.\n"
        "In the generate_text instruction keep the user's own topic and length; "
        "do not add requirements they did not ask for.\n"
        "Only use screen coordinates the user gave; never invent them.\n"
        "Never plan commands, code, file deletion, power actions, messages or "
        "emails. A URL is only allowed inside open_url, http or https only.\n"
        "Example task: open notepad and write a short poem about the rain\n"
        "Example reply: " + json.dumps(PLAN_EXAMPLE) + "\n"
        "Task: " + user_text
    )


def _clean_written_text(text):
    """Trim wrapping a model adds despite instructions: code fences, quotes."""
    text = (text or "").strip()
    fenced = re.fullmatch(r"```[\w-]*\n?(.*?)\n?```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    for opening, closing in (('"', '"'), ("'", "'"), ("“", "”")):
        inner = text[1:-1]
        if len(text) >= 2 and text[0] == opening and text[-1] == closing \
                and opening not in inner and closing not in inner:
            text = inner.strip()
            break
    return text


class Brain:

    def __init__(self, memory):
        self.memory = memory
        self.history = []                       # [{"role": ..., "content": ...}, ...]

        # warm the model in the background so the first real
        # question doesn't pay the model-load penalty
        threading.Thread(target=self._warmup, daemon=True).start()

    # --------------------------------------------------------
    # WARMUP
    # --------------------------------------------------------

    def _warmup(self):

        try:
            requests.post(
                config.OLLAMA_URL,
                json={
                    "model": config.OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                    "keep_alive": config.OLLAMA_KEEP_ALIVE,
                    "options": {"num_predict": 1},
                },
                timeout=90,
            )

        except Exception:
            log.info("Ollama warm-up unavailable; requests will retry when needed", exc_info=True)

    # --------------------------------------------------------
    # PROMPT BUILDING
    # --------------------------------------------------------

    def _messages(self, user_text):

        # The date/time line is rebuilt on every request so the model never
        # has to guess (or invent) what day and time it is.
        system = SYSTEM_PROMPT + current_datetime_line() + "\n" + self.memory.context_block()

        messages = [{"role": "system", "content": system}]
        messages.extend(self.history[-config.HISTORY_MESSAGES:])
        messages.append({"role": "user", "content": user_text})

        return messages

    # --------------------------------------------------------
    # STRUCTURED COMPUTER TASK PLANNING
    # --------------------------------------------------------

    def plan_actions(self, user_text):
        """Ask Ollama for a JSON plan; reject malformed or unsafe plans."""
        payload = {
            "model": config.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {"role": "user", "content": _planner_instruction(user_text)},
            ],
            # Structured outputs: Ollama constrains generation to the plan
            # schema, so the model cannot invent its own action format.
            "format": plan_json_schema(),
            "stream": False,
            "keep_alive": config.OLLAMA_KEEP_ALIVE,
            "options": {"temperature": 0, "num_predict": 400},
        }
        content = ""
        try:
            response = requests.post(config.OLLAMA_URL, json=payload, timeout=config.OLLAMA_TIMEOUT)
            if not response.ok:
                # Ollama before 0.5 accepts only format="json", not a schema.
                log.info(
                    "Ollama refused the plan schema (HTTP %s); retrying in plain JSON mode",
                    response.status_code,
                )
                payload["format"] = "json"
                response = requests.post(config.OLLAMA_URL, json=payload, timeout=config.OLLAMA_TIMEOUT)
            response.raise_for_status()
            content = response.json().get("message", {}).get("content", "")
            if not isinstance(content, str):
                raise PlanValidationError("Ollama returned no JSON content")
            return validate_plan(coerce_plan(json.loads(content)))
        except (ValueError, PlanValidationError) as exc:
            # The raw reply makes the next failure diagnosable from the log.
            log.warning(
                "Rejected malformed computer-action plan: %s. Model reply: %.600s",
                exc, content,
            )
            return None
        except Exception:
            log.exception("Computer-action planning request failed")
            return None

    # --------------------------------------------------------
    # WRITE TEXT FOR A COMPUTER TASK
    # --------------------------------------------------------

    def write_text(self, instruction):
        """Generate text to type into a document.

        Unlike ask_stream this uses a writing prompt instead of the spoken
        chat persona, keeps the conversation history untouched, and raises
        on failure, so an error sentence is never typed into the document.
        """
        response = requests.post(
            config.OLLAMA_URL,
            json={
                "model": config.OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": WRITER_SYSTEM_PROMPT},
                    {"role": "user", "content": instruction},
                ],
                "stream": False,
                "keep_alive": config.OLLAMA_KEEP_ALIVE,
                "options": {"temperature": 0.7, "num_predict": 700},
            },
            timeout=config.OLLAMA_TIMEOUT,
        )
        response.raise_for_status()
        text = _clean_written_text(response.json().get("message", {}).get("content", ""))
        if not text:
            raise RuntimeError("The local model returned no text to type")
        return text

    # --------------------------------------------------------
    # ASK (streaming)
    # --------------------------------------------------------

    def ask_stream(self, user_text):
        """
        Generator: yields complete sentence strings as soon as
        the LLM produces them. Consume with Voice.speak_stream().
        """

        payload = {
            "model": config.OLLAMA_MODEL,
            "messages": self._messages(user_text),
            "stream": True,
            "keep_alive": config.OLLAMA_KEEP_ALIVE,
            "options": {
                "num_predict": config.MAX_REPLY_TOKENS,
                "temperature": 0.6,
            },
        }

        splitter = SentenceSplitter()
        spoke_anything = False
        full_reply = ""

        try:

            with requests.post(
                config.OLLAMA_URL,
                json=payload,
                stream=True,
                timeout=config.OLLAMA_TIMEOUT,
            ) as response:

                response.raise_for_status()

                for line in response.iter_lines():

                    if not line:
                        continue

                    data = json.loads(line.decode("utf-8"))
                    token = data.get("message", {}).get("content", "")

                    if not token:
                        continue

                    spoke_anything = True
                    full_reply += token

                    for sentence in splitter.feed(token):
                        yield sentence

                tail = splitter.finish()

                if tail:
                    yield tail

            # keep short-term context
            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": full_reply.strip()})
            del self.history[:-config.HISTORY_MESSAGES * 2]

        except Exception as e:

            log.exception("Ollama streaming request failed")

            if not spoke_anything:
                yield CONNECTION_FALLBACK
