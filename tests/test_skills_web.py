"""
============================================================
 TESTS — lyra/skills/web.py
============================================================
"""

import json
from urllib.parse import quote

import pytest

from lyra import config
from lyra.skills import web

from conftest import FakeResponse


# ------------------------------------------------------------
# SEARCH
# ------------------------------------------------------------

@pytest.mark.parametrize("text, query", [
    ("search for best laptops", "best laptops"),
    ("search best laptops", "best laptops"),
    ("google python tutorial", "python tutorial"),
    ("look up python tutorial", "python tutorial"),
])
def test_google_search(opened, text, query):
    assert web.handle(text) == f"Searching for {query}."
    assert opened == ["https://www.google.com/search?q=" + quote(query)]


def test_search_does_not_hijack_known_sites(opened):
    # "search google chrome" must fall through to the apps skill
    assert web.handle("search google chrome") is None
    assert opened == []


# ------------------------------------------------------------
# YOUTUBE
# ------------------------------------------------------------

@pytest.mark.parametrize("text, query", [
    ("play beliver on youtube", "beliver"),
    ("search for lofi beats on youtube", "lofi beats"),
    ("find lofi beats on youtube", "lofi beats"),
    ("youtube lofi beats", "lofi beats"),
    # "search youtube for ..." used to fall through to the Google branch
    # and search the wrong site entirely.
    ("search youtube for lofi beats", "lofi beats"),
    ("search on youtube for lofi beats", "lofi beats"),
    ("look up youtube for lofi beats", "lofi beats"),
])
def test_youtube_search(opened, text, query):
    assert web.handle(text) == f"Searching YouTube for {query}."
    assert opened == ["https://www.youtube.com/results?search_query=" + quote(query)]


def test_youtube_without_a_query_is_not_a_search(opened):
    assert web.handle("search youtube") is None
    assert opened == []


# ------------------------------------------------------------
# WIKIPEDIA
# ------------------------------------------------------------

def test_wikipedia_search(opened):
    assert web.handle("wikipedia albert einstein") == "Searching Wikipedia for albert einstein."
    assert opened == [
        "https://en.wikipedia.org/wiki/Special:Search?search=" + quote("albert einstein")
    ]


# ------------------------------------------------------------
# OPEN SITES & DOMAINS
# ------------------------------------------------------------

@pytest.mark.parametrize("name, url", [
    ("youtube", "https://www.youtube.com"),
    ("gmail", "https://mail.google.com"),
    ("github", "https://github.com"),
    ("whatsapp", "https://web.whatsapp.com"),
])
def test_open_known_site(opened, name, url):
    assert web.handle(f"open {name}") == f"Opening {name.title()}."
    assert opened == [url]


@pytest.mark.parametrize("text, domain", [
    ("open google dot com", "google.com"),
    ("open github dot com", "github.com"),
    ("open arena dot ai", "arena.ai"),
])
def test_open_spoken_domain(opened, text, domain):
    assert web.handle(text) == f"Opening {domain}."
    assert opened == [f"https://{domain}"]


@pytest.mark.parametrize("text", ["go to youtube", "launch youtube", "visit youtube"])
def test_open_verbs(opened, text):
    assert web.handle(text) == "Opening Youtube."
    assert opened == ["https://www.youtube.com"]


def test_every_known_site_is_a_valid_url():
    for name, url in web.SITES.items():
        assert url.startswith("https://"), name


# ------------------------------------------------------------
# WEATHER
# ------------------------------------------------------------

def test_weather_uses_the_default_city(monkeypatch):
    cities = []
    monkeypatch.setattr(web, "_weather", lambda city: cities.append(city) or "sunny")

    assert web.handle("weather") == "sunny"
    assert cities == [config.DEFAULT_CITY]


@pytest.mark.parametrize("text, city", [
    ("weather in paris", "paris"),
    ("weather for new york", "new york"),
    ("what is weather in tokyo", "tokyo"),
    ("weather in tokyo today", "tokyo"),
    # the natural spoken phrasings — the article "the" used to stop the
    # match, so "what's the weather" was answered by the LLM instead
    ("what's the weather", config.DEFAULT_CITY),
    ("what's the weather like", config.DEFAULT_CITY),
    ("how's the weather outside", config.DEFAULT_CITY),
    ("what's the weather in tokyo", "tokyo"),
    ("what's the weather like in tokyo", "tokyo"),
    ("what is the weather in new york today", "new york"),
])
def test_weather_extracts_the_city(monkeypatch, text, city):
    cities = []
    monkeypatch.setattr(web, "_weather", lambda c: cities.append(c) or "sunny")

    assert web.handle(text) == "sunny"
    assert cities == [city]


@pytest.mark.parametrize("text", [
    "the weather is nice today",
    "is it going to rain",
    "how are you",
])
def test_a_sentence_about_the_weather_is_not_a_question_about_it(opened, text):
    assert web.handle(text) is None
    assert opened == []


def test_weather_parses_the_wttr_payload(monkeypatch):
    payload = {
        "current_condition": [{
            "temp_C": "29",
            "FeelsLikeC": "32",
            "weatherDesc": [{"value": "Haze "}],
            "humidity": "70",
        }]
    }

    monkeypatch.setattr(
        web.requests,
        "get",
        lambda url, **kwargs: FakeResponse(payload=payload),
    )

    assert web.handle("weather in bhubaneswar") == (
        "Bhubaneswar: Haze, 29 degrees, feels like 32. Humidity 70 percent."
    )


def test_weather_failure_is_spoken_not_raised(monkeypatch):
    def boom(url, **kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr(web.requests, "get", boom)

    assert web.handle("weather in paris") == "I couldn't fetch the weather for Paris right now."


# ------------------------------------------------------------
# NOT MINE
# ------------------------------------------------------------

@pytest.mark.parametrize("text", ["open notepad", "what time is it", "open downloads", ""])
def test_other_commands_are_left_alone(opened, text):
    assert web.handle(text) is None
    assert opened == []
