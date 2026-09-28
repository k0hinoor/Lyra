"""
============================================================
 TESTS — lyra/skills/__init__.py  (the skill router)
============================================================
"""

import pytest

from lyra.skills import apps, fun, route, system, typing, web, windows
from lyra.skills.base import Confirmation


# ------------------------------------------------------------
# HAPPY PATH
# ------------------------------------------------------------

def test_joke_routes_to_fun(pc):
    reply, confirmation = route("tell me a joke")

    assert any(reply.startswith(joke) for joke in fun.JOKES)   # joke + why
    assert confirmation is None


def test_time_routes_to_system(pc):
    reply, confirmation = route("what time is it")
    assert reply.startswith("It's ")


def test_open_app_routes_to_apps(pc):
    reply, confirmation = route("open notepad")

    assert reply == "Opening Notepad."
    assert pc.started == ["notepad"]


def test_open_site_routes_to_web_before_apps(pc):
    reply, confirmation = route("open youtube")

    assert reply == "Opening Youtube."
    assert pc.urls == ["https://www.youtube.com"]
    assert pc.started == [], "the apps skill must not also fire"


def test_search_routes_to_web(pc):
    reply, confirmation = route("search for best laptops")
    assert reply == "Searching for best laptops."


@pytest.mark.parametrize("text, target, reply", [
    ("open storage settings", "ms-settings:storagesense", "Opening Storage Settings."),
    ("open battery settings", "ms-settings:batterysaver", "Opening Battery Settings."),
])
def test_open_settings_page_is_not_swallowed_by_an_earlier_skill(pc, text, target, reply):
    # Regression: "open storage settings" reached the system skill first,
    # which matched the word "storage" and read out free disk space.
    assert route(text) == (reply, None)
    assert pc.started == [target]


def test_shortcut_routes_to_typing_before_windows(pc):
    reply, confirmation = route("copy")
    assert reply == "Done."
    assert pc.pyauto.hotkeyed("ctrl", "c")


def test_unknown_text_is_left_to_the_brain(pc):
    assert route("why is the sky blue") == (None, None)


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_text_matches_nothing(pc, text):
    assert route(text) == (None, None)


# ------------------------------------------------------------
# SKILL ORDER
# ------------------------------------------------------------

def test_typing_is_asked_before_windows(monkeypatch, pc):
    monkeypatch.setattr(typing, "handle", lambda text, raw=None: "typing wins")
    monkeypatch.setattr(windows, "handle", lambda text, raw=None: "windows wins")

    assert route("copy") == ("typing wins", None)


def test_the_first_matching_skill_wins(monkeypatch, pc):
    monkeypatch.setattr(typing, "handle", lambda text, raw=None: "typing wins")

    assert route("show desktop") == ("typing wins", None)


def test_web_is_asked_before_apps(monkeypatch, pc):
    monkeypatch.setattr(web, "handle", lambda text, raw=None: "web wins")

    assert route("open notepad") == ("web wins", None)


def test_apps_is_the_last_resort(monkeypatch, pc):
    monkeypatch.setattr(apps, "handle", lambda text, raw=None: "apps wins")

    assert route("open notepad") == ("apps wins", None)


# ------------------------------------------------------------
# RAW TEXT
# ------------------------------------------------------------

def test_raw_text_is_passed_through(monkeypatch, pc):
    seen = []

    def spy(text, raw=None):
        seen.append((text, raw))
        return None

    for skill in (typing, windows, system, fun, web, apps):
        monkeypatch.setattr(skill, "handle", spy)

    route("open some random app", raw="open Some Random App")

    assert seen
    assert all(text == "open some random app" for text, _raw in seen)
    assert all(raw == "open Some Random App" for _text, raw in seen)


# ------------------------------------------------------------
# CONFIRMATIONS
# ------------------------------------------------------------

def test_dangerous_commands_return_a_confirmation(pc):
    reply, confirmation = route("shutdown the pc")

    assert reply is None
    assert isinstance(confirmation, Confirmation)
    assert pc.shell.commands == [], "nothing may run before the user confirms"


def test_confirmation_action_runs_only_when_called(pc):
    _reply, confirmation = route("empty the recycle bin")
    assert pc.shell.commands == []

    confirmation.action()
    assert pc.shell.commands


# ------------------------------------------------------------
# ROBUSTNESS
# ------------------------------------------------------------

def test_a_broken_skill_does_not_break_the_router(monkeypatch, pc):
    def boom(text, raw=None):
        raise RuntimeError("skill exploded")

    monkeypatch.setattr(system, "handle", boom)

    # the failing skill is skipped and no other skill claims the text
    assert route("what time is it") == (None, None)


def test_a_broken_skill_does_not_hide_later_skills(monkeypatch, pc):
    def boom(text, raw=None):
        raise RuntimeError("skill exploded")

    monkeypatch.setattr(typing, "handle", boom)

    reply, confirmation = route("tell me a joke")
    assert any(reply.startswith(joke) for joke in fun.JOKES)    # joke + why


def test_router_is_quiet_about_skills_that_opt_out(monkeypatch, pc):
    assert route("blah blah") == (None, None)
