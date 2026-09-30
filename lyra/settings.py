"""Small, non-destructive settings writer used by setup commands."""

import json
import os
import tempfile
from pathlib import Path

from . import config


def update_settings(updates):
    """Atomically merge settings, preserving unrelated user preferences.

    Refuse to overwrite a malformed existing file. Setup commands report
    that error instead of erasing the user's settings with fresh defaults.
    """
    path = config.SETTINGS_FILE
    try:
        with path.open("r", encoding="utf-8") as handle:
            settings = json.load(handle)
    except FileNotFoundError:
        settings = {}
    if not isinstance(settings, dict):
        raise ValueError(f"Settings must be a JSON object: {path}")
    settings.update(updates)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=path.name + ".", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(settings, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path
