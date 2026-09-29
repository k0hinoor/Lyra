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


# ------------------------------------------------------------
# "open youtube and search for lofi"  (one breath, two steps)
# ------------------------------------------------------------

def test_open_youtube_and_search(opened):
    # The regex used to treat "and search for lofi" as the query.
    assert web.handle("open youtube and search for lofi") == (
        "Searching YouTube for lofi."
    )
    assert opened == ["https://www.youtube.com/results?search_query=lofi"]


@pytest.mark.parametrize("text, query", [
    ("youtube and search for lofi", "lofi"),
    ("open youtube and play lofi beats", "lofi beats"),
    ("open youtube and find lofi", "lofi"),
])
def test_more_youtube_and_search_phrasings(opened, text, query):
    reply = web.handle(text)
    assert reply == f"Searching YouTube for {query}."
    assert opened == [
        "https://www.youtube.com/results?search_query=" + quote(query)
    ]


# ------------------------------------------------------------
# NAMED BROWSER  ("open youtube in brave")
# ------------------------------------------------------------

@pytest.mark.parametrize("text, browser, url, reply", [
    ("open youtube in brave", "brave", "https://www.youtube.com",
     "Opening Youtube in Brave."),
    ("open gmail in chrome", "chrome", "https://mail.google.com",
     "Opening Gmail in Chrome."),
    ("open github in firefox", "firefox", "https://github.com",
     "Opening Github in Firefox."),
    ("open github in edge", "edge", "https://github.com",
     "Opening Github in Edge."),
    ("open youtube in google chrome", "chrome", "https://www.youtube.com",
     "Opening Youtube in Chrome."),
    ("open github in microsoft edge", "edge", "https://github.com",
     "Opening Github in Edge."),
])
def test_open_site_in_named_browser(browser_launches, opened, text, browser, url, reply):
    assert web.handle(text) == reply
    assert browser_launches == [(browser, url)]
    assert opened == [], "the default browser must not also fire"


def test_search_youtube_in_named_browser(browser_launches, opened):
    assert web.handle("search youtube for lofi in brave") == (
        "Searching YouTube for lofi in Brave."
    )
    assert browser_launches == [
        ("brave", "https://www.youtube.com/results?search_query=lofi")
    ]


def test_google_search_in_named_browser(browser_launches):
    assert web.handle("search for best laptops in firefox") == (
        "Searching for best laptops in Firefox."
    )
    assert browser_launches == [
        ("firefox", "https://www.google.com/search?q=" + quote("best laptops"))
    ]


def test_missing_named_browser_falls_back_to_default(monkeypatch, opened):
    from lyra import browsers

    monkeypatch.setattr(browsers, "find_browser", lambda name: None)
    monkeypatch.setattr(browsers, "launch_browser", lambda name, url=None: False)

    assert web.handle("open youtube in brave") == (
        "I couldn't find Brave, so I opened it in your default browser."
    )
    assert opened == ["https://www.youtube.com"]


def test_a_site_name_in_a_browser_is_not_a_search_query(opened):
    # Regression guard for the old behaviour: "open youtube in brave"
    # searched YouTube for "in brave".
    web.handle("open youtube in brave")
    assert opened == [] or all("search_query" not in url for url in opened)


# ------------------------------------------------------------
# MULTI-STEP: "open brave and open youtube"
# ------------------------------------------------------------

@pytest.mark.parametrize("text, url, reply", [
    ("open brave and open youtube", "https://www.youtube.com",
     "Opening Youtube in Brave."),
    ("open brave and go to youtube", "https://www.youtube.com",
     "Opening Youtube in Brave."),
    ("open brave and search youtube for lofi",
     "https://www.youtube.com/results?search_query=lofi",
     "Searching YouTube for lofi in Brave."),
    ("open chrome and open gmail", "https://mail.google.com",
     "Opening Gmail in Chrome."),
    ("open brave and youtube", "https://www.youtube.com",
     "Opening Youtube in Brave."),
])
def test_open_browser_and_then_a_site(browser_launches, opened, text, url, reply):
    assert web.handle(text) == reply
    assert browser_launches == [("brave" if "brave" in text else "chrome", url)]
    assert opened == []


def test_open_browser_and_unresolvable_second_half(browser_launches):
    # A web verb with an unknown target: open the browser alone.
    assert web.handle("open brave and open nowhereville dot org") == (
        "Opening nowhereville.org in Brave."
    )


def test_open_browser_and_a_non_web_second_half_is_left_alone(browser_launches):
    assert web.handle("open brave and make me a coffee") is None
    assert browser_launches == []


def test_multistep_does_not_swallow_other_apps(opened):
    # Only a browser name may lead this pattern.
    assert web.handle("open notepad and open calculator") is None


# ------------------------------------------------------------
# BROWSER SETTING  (default for every web command)
# ------------------------------------------------------------

def test_configured_browser_is_used_for_plain_opens(monkeypatch, browser_launches):
    monkeypatch.setattr(config, "BROWSER", "brave")
    opened_default = []
    monkeypatch.setattr(web.webbrowser, "open", opened_default.append)

    assert web.handle("open youtube") == "Opening Youtube."
    assert browser_launches == [("brave", "https://www.youtube.com")]
    assert opened_default == []


def test_configured_browser_falls_back_when_missing(monkeypatch):
    from lyra import browsers

    monkeypatch.setattr(config, "BROWSER", "brave")
    monkeypatch.setattr(browsers, "find_browser", lambda name: None)
    monkeypatch.setattr(browsers, "launch_browser", lambda name, url=None: False)
    opened_default = []
    monkeypatch.setattr(web.webbrowser, "open", opened_default.append)

    assert web.handle("open youtube") == "Opening Youtube."
    assert opened_default == ["https://www.youtube.com"]


def test_empty_browser_setting_uses_the_windows_default(monkeypatch):
    monkeypatch.setattr(config, "BROWSER", "")
    opened_default = []
    monkeypatch.setattr(web.webbrowser, "open", opened_default.append)

    web.handle("open youtube")
    assert opened_default == ["https://www.youtube.com"]
