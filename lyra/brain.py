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

import json
import threading

import requests

from . import config
from .utils import SentenceSplitter

CONNECTION_FALLBACK = (
    "I can't reach my local brain. "
    "Is Ollama running?"
)

SYSTEM_PROMPT = (
    "You are Lyra, " + config.USER_NAME + "'s personal AI assistant, "
    "running fully local on their PC. You can also control the PC.\n"
    "Your name is Lyra. Never say you were made by any company, "
    "and never identify as any other AI or model.\n"
    "You are helpful, concise, natural and conversational.\n"
    "\n"
    "IMPORTANT — you operate this computer, you are not a manual:\n"
    "- You can already do it yourself: change the volume, brightness and "
    "mute, open and close apps, files, folders and settings, control "
    "windows, tabs, the keyboard, the clipboard, media playback and "
    "power, and read the time, battery, disk and network.\n"
    "- So never reply with instructions. No steps, no 'right-click the "
    "sound icon', no 'go to Settings', no 'press these keys', no menus, "
    "no key shortcuts, no 'here is how you do it'.\n"
    "- If the user asks for something the computer can do and it has "
    "already been done, just say it is done in a few words.\n"
    "- If it is genuinely beyond you, say so in one short sentence "
    "instead of describing where the button is.\n"
    "\n"
    "IMPORTANT — your replies are spoken out loud through a voice, so:\n"
    "- Answer in plain spoken sentences only.\n"
    "- No markdown, no lists, no code blocks, no emojis, no symbols.\n"
    "- Keep answers to one or three sentences unless asked for detail.\n"
    "- Do not add unasked advice, encouragement or follow-up topics.\n"
    "- Do not mention memories unless they are directly relevant.\n"
)


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
            pass                                # offline — handled per-request later

    # --------------------------------------------------------
    # PROMPT BUILDING
    # --------------------------------------------------------

    def _messages(self, user_text):

        system = SYSTEM_PROMPT + self.memory.context_block()

        messages = [{"role": "system", "content": system}]
        messages.extend(self.history[-config.HISTORY_MESSAGES:])
        messages.append({"role": "user", "content": user_text})

        return messages

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

            print(f"Ollama error: {e}")

            if not spoke_anything:
                yield CONNECTION_FALLBACK
