"""Offline Piper voice choices and validated model-name parsing.

Only model files are fetched from the official Piper voice repository;
conversation text is never sent there. More valid Piper IDs can be used
in settings without expanding this small, curated list.
"""

import re

VOICE_CHOICES = {
    "en": (
        "en_US-lessac-medium",
        "en_US-amy-medium",
        "en_US-lessac-high",
        "en_GB-jenny-high",
    ),
    "hi": (
        "hi_IN-priyamvada-medium",
        "hi_IN-pratham-medium",
        "hi_IN-rohan-medium",
    ),
}

_MODEL_ID = re.compile(
    r"(?P<locale>[a-z]{2,3}_[A-Z]{2})-"
    r"(?P<name>[a-zA-Z0-9_]+(?:-[a-zA-Z0-9_]+)*)-"
    r"(?P<quality>x_low|low|medium|high)\Z"
)


def parse_voice_model(model):
    """Return (language, locale, name, quality), rejecting unsafe paths."""
    if not isinstance(model, str):
        raise ValueError("Piper model ID must be a string")
    match = _MODEL_ID.fullmatch(model)
    if not match:
        raise ValueError(
            "Use a Piper model ID such as en_US-lessac-medium or "
            "hi_IN-priyamvada-medium, not a path or URL"
        )
    locale, name, quality = match.group("locale", "name", "quality")
    return locale.split("_", 1)[0], locale, name, quality
