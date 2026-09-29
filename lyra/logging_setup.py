"""Readable console and rotating file diagnostics.

The console stays clean — warnings and errors only — while the log
file under %APPDATA%\\Lyra\\logs keeps the full INFO detail that bug
reports need (Whisper audio durations, VAD decisions, executor
results, ...).
"""

import logging
from logging.handlers import RotatingFileHandler

_MARK = "_lyra_configured"


def configure_logging(log_dir, level="INFO", console_level="WARNING"):
    """Attach a quiet console handler and a full-detail file handler."""
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    # Skip only when LYRA's own handlers are already attached — unrelated
    # handlers (test harnesses, embedders) must not block configuration.
    if any(getattr(handler, _MARK, False) for handler in root.handlers):
        return root

    file_level = getattr(logging, str(level).upper(), logging.INFO)
    console_level = getattr(logging, str(console_level).upper(), logging.WARNING)

    # The root must pass every record the most verbose handler wants.
    root.setLevel(min(file_level, console_level))

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(console_level)

    file_handler = RotatingFileHandler(
        log_dir / "lyra.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(file_level)

    setattr(console, _MARK, True)
    setattr(file_handler, _MARK, True)

    root.addHandler(console)
    root.addHandler(file_handler)
    return root
