"""
============================================================
 SKILL: WEB
============================================================
 Websites, Google search, YouTube search, Wikipedia,
 and weather (via wttr.in — no API key needed).
============================================================
"""

import re
import webbrowser
from urllib.parse import quote

import requests

from .. import config

SITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "google mail": "https://mail.google.com",
    "github": "https://github.com",
    "stack overflow": "https://stackoverflow.com",
    "stackoverflow": "https://stackoverflow.com",
    "reddit": "https://www.reddit.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "whatsapp web": "https://web.whatsapp.com",
    "whatsapp": "https://web.whatsapp.com",
    "netflix": "https://www.netflix.com",
    "amazon": "https://www.amazon.in",
    "flipkart": "https://www.flipkart.com",
    "myntra": "https://www.myntra.com",
    "linkedin": "https://www.linkedin.com",
    "chatgpt": "https://chatgpt.com",
    "gemini": "https://gemini.google.com",
    "hotstar": "https://www.hotstar.com",
    "prime video": "https://www.primevideo.com",
    "wikipedia": "https://www.wikipedia.org",
    "google maps": "https://maps.google.com",
    "maps": "https://maps.google.com",
    "google drive": "https://drive.google.com",
    "translate": "https://translate.google.com",
}

_DOMAIN_RE = re.compile(
    r"^[a-z0-9-]+(\.[a-z0-9-]+)*\.(com|net|org|in|io|co|dev|ai|app|gov|edu|me|tv|xyz)$"
)


def _open(url):
    webbrowser.open(url)


# ------------------------------------------------------------
# WEATHER
# ------------------------------------------------------------

def _weather(city):

    try:

        response = requests.get(
            f"https://wttr.in/{quote(city)}?format=j1",
            timeout=8,
            headers={"User-Agent": "lyra"},
        )
        response.raise_for_status()

        current = response.json()["current_condition"][0]

        temp = current["temp_C"]
        feels = current["FeelsLikeC"]
        desc = current["weatherDesc"][0]["value"].strip()
        humidity = current["humidity"]

        return (
            f"{city.title()}: {desc}, {temp} degrees, "
            f"feels like {feels}. Humidity {humidity} percent."
        )

    except Exception:
        return f"I couldn't fetch the weather for {city.title()} right now."


# ------------------------------------------------------------
# HANDLE
# ------------------------------------------------------------

def handle(text, raw=None):

    text = text.strip()

    if not text:
        return None

    # --------------------------------------------------------
    # WEATHER
    # --------------------------------------------------------

    match = re.match(
        r"^(?:what(?:'s| is)? )?weather(?: (?:forecast|report|like|now|outside))?"
        r"(?: (?:in|for|at) (.+?))?(?: (?:today|right now|now))?$",
        text,
    )

    if match:
        city = (match.group(1) or config.DEFAULT_CITY).strip()
        return _weather(city)

    # --------------------------------------------------------
    # YOUTUBE
    # --------------------------------------------------------

    match = re.match(r"^(?:play|search|find|look up)(?: for)? (.+?) on youtube$", text)

    if match:
        query = match.group(1).strip()
        _open("https://www.youtube.com/results?search_query=" + quote(query))
        return f"Searching YouTube for {query}."

    match = re.match(r"^(?:open )?youtube (.+)$", text)

    if match and match.group(1).strip() not in ("settings",):
        query = match.group(1).strip()
        _open("https://www.youtube.com/results?search_query=" + quote(query))
        return f"Searching YouTube for {query}."

    # --------------------------------------------------------
    # WIKIPEDIA
    # --------------------------------------------------------

    match = re.match(r"^(?:wikipedia|wiki) (.+)$", text)

    if match:
        query = match.group(1).strip()
        _open("https://en.wikipedia.org/wiki/Special:Search?search=" + quote(query))
        return f"Searching Wikipedia for {query}."

    # --------------------------------------------------------
    # GOOGLE SEARCH
    # --------------------------------------------------------

    match = re.match(r"^(?:search(?: for)?|google|look up|find) (.+)$", text)

    if match:
        query = match.group(1).strip()

        # "google chrome" should open the app / site, not search the web
        from . import apps

        if (
            query in SITES
            or query in apps.OPEN_APPS
            or query in apps.OPEN_SETTINGS
            or query in ("youtube", "wikipedia", "my ip", "my location")
        ):
            return None

        _open("https://www.google.com/search?q=" + quote(query))
        return f"Searching for {query}."

    # --------------------------------------------------------
    # OPEN WEBSITE
    # --------------------------------------------------------

    match = re.match(r"^(?:open|go to|launch|visit) (.+)$", text)

    if match:
        name = match.group(1).strip()

        if name in SITES:
            _open(SITES[name])
            return f"Opening {name.title()}."

        # "open google dot com" -> "google.com"
        domain_text = re.sub(r"\s*dot\s*", ".", name)
        domain_text = domain_text.replace(" ", "")

        if _DOMAIN_RE.match(domain_text):
            _open("https://" + domain_text)
            return f"Opening {domain_text}."

    return None


def name():
    return "web"
