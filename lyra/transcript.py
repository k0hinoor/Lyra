"""
============================================================
 LYRA CONVERSATION TRANSCRIPT
============================================================
 Appends every exchange — what Lyra heard, her full reply and
 what handled it (a skill, the planner or the chat model) — to
 a dated file:

     %APPDATA%\\Lyra\\logs\\conversation-YYYY-MM-DD.txt

 Writing must never break a conversation, so every failure is
 logged and swallowed.
============================================================
"""

import logging
import threading
from datetime import datetime
from pathlib import Path

from . import config

log = logging.getLogger(__name__)


class Transcript:

    def __init__(self, log_dir=None):
        self._log_dir = log_dir
        self._lock = threading.Lock()

    def _directory(self):
        if self._log_dir is not None:
            return Path(self._log_dir)
        return config.LOG_DIR

    def path_for(self, when=None):
        when = when or datetime.now()
        return self._directory() / f"conversation-{when:%Y-%m-%d}.txt"

    def record(self, heard, reply, handler):
        """Append one exchange with timestamps."""

        try:
            directory = self._directory()
            directory.mkdir(parents=True, exist_ok=True)

            path = self.path_for()
            when = datetime.now()
            stamp = when.strftime("%Y-%m-%d %H:%M:%S")

            lines = [f"[{stamp}] Heard: {str(heard).strip()}"]
            lines.append(f"[{stamp}] Handled by: {handler}")
            reply_text = str(reply or "").strip()
            if reply_text:
                for line in reply_text.splitlines():
                    lines.append(f"[{stamp}] Lyra: {line}")
            else:
                lines.append(f"[{stamp}] Lyra: (no reply)")
            lines.append("")

            with self._lock:
                with open(path, "a", encoding="utf-8") as handle:
                    handle.write("\n".join(lines) + "\n")

        except Exception:
            log.exception("Could not write the conversation transcript")
