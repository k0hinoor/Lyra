"""
============================================================
 SKILL ROUTER
============================================================
 Skills are checked in order — first match wins.
 The order matters: specific skills (typing, windows) must
 run before broad ones (web, apps).
============================================================
"""

import logging

from .base import Confirmation
from . import apps
from . import fun
from . import media
from . import system
from . import typing
from . import web
from . import windows

log = logging.getLogger(__name__)

_SKILLS = (
    typing,     # type/press/copy/paste — very specific verbs first
    windows,    # window/tab management
    media,      # volume/brightness/playback
    system,     # time/battery/power/screenshot ...
    fun,        # jokes/coin/dice
    web,        # searches, sites, weather
    apps,       # open/close anything — broadest, last
)


def route_with_handler(text, raw=None):
    """
    Try every skill with the normalized text.

    Returns (reply, confirmation, handler):
      reply        str to speak, or None
      confirmation Confirmation object, or None
      handler      "skill:<name>" of the skill that answered, or None
    """

    raw = raw if raw is not None else text

    for skill in _SKILLS:

        try:
            result = skill.handle(text, raw)

        except Exception:
            log.exception("Skill %s failed", skill.name())
            result = None

        if result is None:
            continue

        handler = f"skill:{skill.name()}"

        if isinstance(result, Confirmation):
            return None, result, handler

        return str(result), None, handler

    return None, None, None


def route(text, raw=None):
    """
    Try every skill with the normalized text.

    Returns (reply, confirmation):
      reply        str to speak, or None
      confirmation Confirmation object, or None
    """

    reply, confirmation, _handler = route_with_handler(text, raw)
    return reply, confirmation
