"""
============================================================
 LYRA MEMORY
============================================================
 Persistent long-term memory ("remember that ...")
 stored in memory.json next to main.py.
============================================================
"""

import json

from . import config

MAX_MEMORY_ITEMS = 40        # how many items get sent to the brain


class Memory:

    def __init__(self):
        self.items = []
        self._load()

    # --------------------------------------------------------
    # LOAD / SAVE
    # --------------------------------------------------------

    def _load(self):

        try:
            with open(config.MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                self.items = [str(item) for item in data]

        except FileNotFoundError:
            self.items = []

        except Exception as e:
            print(f"Memory load error: {e}")
            self.items = []

    def _save(self):

        try:
            with open(config.MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.items, f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"Memory save error: {e}")

    # --------------------------------------------------------
    # OPERATIONS
    # --------------------------------------------------------

    def add(self, item):

        item = item.strip()

        if not item:
            return False

        if item in self.items:          # no duplicates
            return False

        self.items.append(item)
        self._save()

        return True

    def remove(self, text):
        """Remove items containing this text. Returns how many were removed."""

        text = text.strip().lower()

        if not text:
            return 0

        before = len(self.items)
        self.items = [i for i in self.items if text not in i.lower()]

        removed = before - len(self.items)

        if removed:
            self._save()

        return removed

    def clear(self):
        self.items = []
        self._save()

    # --------------------------------------------------------
    # CONTEXT FOR THE BRAIN
    # --------------------------------------------------------

    def context_block(self):
        """Text block injected into the system prompt, or empty string."""

        if not self.items:
            return ""

        recent = self.items[-MAX_MEMORY_ITEMS:]
        lines = "\n".join(f"- {item}" for item in recent)

        return (
            "\nThings " + config.USER_NAME + " asked you to remember:\n"
            + lines + "\n"
        )
