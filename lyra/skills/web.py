"""
============================================================
 SKILL: WEB
============================================================
 Websites, Google search, YouTube search, Wikipedia,
 weather (via wttr.in), named browsers ("open youtube in
 brave"), a configurable default browser, and run-on web
 commands ("open brave and search youtube for lofi").
============================================================
"""

import re
import webbrowser
from urllib.parse import quote

import requests

from .. import browsers, config
from ..messages import is_hindi, spoken_name, t

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

# Longest-first so "google chrome" wins over "chrome" at the end of a phrase.
_BROWSER_TAIL = "|".join(sorted(config.BROWSER_ALIASES, key=len, reverse=True))

_WEB_VERBS = ("open", "go to", "launch", "visit", "search", "play", "find", "look up")


def _open(url):
    """Open a URL in the configured browser, else the system default."""

    name = config.normalize_browser_name(config.BROWSER)

    if name and browsers.launch_browser(name, url):
        return True

    webbrowser.open(url)
    return True


def _youtube_search(query):
    return (
        "https://www.youtube.com/results?search_query=" + quote(query),
        t("web.search_youtube", query=query),
    )


# ------------------------------------------------------------
# RESOLVE A PLAIN WEB REQUEST  (no browser involved yet)
# ------------------------------------------------------------

def _resolve(text):
    """Return (url, reply_prefix) for a web request, or None."""

    # "open youtube and search for lofi" — two steps said in one breath.
    # Checked BEFORE the generic "youtube ..." branch so the query cannot
    # swallow the "and search for" part.
    match = re.match(
        r"^(?:open |go to )?youtube and (?:search(?: for)?|look up|find|play) (.+)$",
        text,
    )

    if match:
        return _youtube_search(match.group(1).strip())

    match = re.match(r"^(?:play|search|find|look up)(?: for)? (.+?) on youtube$", text)

    if match:
        return _youtube_search(match.group(1).strip())

    match = re.match(r"^(?:open )?youtube (.+)$", text)

    if match and match.group(1).strip() not in ("settings",):
        return _youtube_search(match.group(1).strip())

    # "search youtube for lofi beats", "look up youtube for X"
    match = re.match(
        r"^(?:play|search|find|look up)(?: on)? youtube(?: for)? (.+)$", text
    )

    if match:
        return _youtube_search(match.group(1).strip())

    # --------------------------------------------------------
    # WIKIPEDIA
    # --------------------------------------------------------

    match = re.match(r"^(?:wikipedia|wiki) (.+)$", text)

    if match:
        query = match.group(1).strip()
        return (
            "https://en.wikipedia.org/wiki/Special:Search?search=" + quote(query),
            t("web.search_wikipedia", query=query),
        )

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

        return (
            "https://www.google.com/search?q=" + quote(query),
            t("web.search", query=query),
        )

    # --------------------------------------------------------
    # OPEN WEBSITE
    # --------------------------------------------------------

    match = re.match(r"^(?:open|go to|launch|visit) (.+)$", text)

    if match:
        name = match.group(1).strip()

        if name in SITES:
            return SITES[name], t("web.opening", name=spoken_name(name.title()))

        # "open google dot com" -> "google.com"
        domain_text = re.sub(r"\s*dot\s*", ".", name)
        domain_text = domain_text.replace(" ", "")

        if _DOMAIN_RE.match(domain_text):
            return "https://" + domain_text, t("web.opening", name=domain_text)

    return None


# ------------------------------------------------------------
# WEATHER
# ------------------------------------------------------------

def _weather(city):

    try:

        response = requests.get(
            f"https://wttr.in/{quote(city)}?format=j1" + ("&lang=hi" if is_hindi() else ""),
            timeout=8,
            headers={"User-Agent": "lyra"},
        )
        response.raise_for_status()

        current = response.json()["current_condition"][0]

        temp = current["temp_C"]
        feels = current["FeelsLikeC"]
        desc = current["weatherDesc"][0]["value"].strip()
        if is_hindi() and current.get("lang_hi"):
            # wttr.in translates the description when asked for lang=hi.
            desc = current["lang_hi"][0]["value"].strip() or desc
        humidity = current["humidity"]

        return t(
            "web.weather", city=city.title(), desc=desc, temp=temp,
            feels=feels, humidity=humidity,
        )

    except Exception:
        return t("web.weather_failed", city=city.title())


# ------------------------------------------------------------
# NAMED-BROWSER HELPERS
# ------------------------------------------------------------

def _open_in_browser(browser, url, reply_prefix):
    """Launch the named browser at a URL, with a fallback to the default."""

    pretty = spoken_name(browsers.pretty_name(browser))

    if browsers.launch_browser(browser, url):
        if url:
            return t("web.reply_in_browser", action=reply_prefix, browser=pretty)
        return t("web.opening_browser", browser=pretty)

    if url:
        _open(url)
        return t("web.browser_fallback", browser=pretty)

    return t("web.browser_missing", browser=pretty)


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
        r"^(?:(?:what|how)(?:'s| is)? )?(?:the )?weather"
        r"(?: (?:forecast|report|like|now|outside))?"
        r"(?: (?:in|for|at) (.+?))?(?: (?:today|right now|now))?$",
        text,
    )

    if match:
        city = (match.group(1) or config.DEFAULT_CITY).strip()
        return _weather(city)

    # --------------------------------------------------------
    # MULTI-STEP: "open brave and open youtube",
    # "open brave and go to youtube",
    # "open brave and search youtube for lofi"
    # --------------------------------------------------------

    match = re.match(
        r"^(?:open|launch|start|run) (" + _BROWSER_TAIL + r") and (.+)$", text
    )

    if match:
        browser = config.BROWSER_ALIASES[match.group(1)]
        second = match.group(2).strip()

        resolved = _resolve(second)

        if resolved is None and not second.startswith(_WEB_VERBS):
            # "open brave and youtube" — a bare site name after "and"
            resolved = _resolve("open " + second)

        if resolved is None and not second.startswith(_WEB_VERBS):
            # not a web task at all — leave it to the planner / chat
            return None

        url = resolved[0] if resolved else None
        reply_prefix = resolved[1] if resolved else None

        return _open_in_browser(browser, url, reply_prefix or "Opening")

    # --------------------------------------------------------
    # NAMED BROWSER: "open youtube in brave",
    # "search youtube for lofi in brave", "open gmail in chrome"
    # --------------------------------------------------------

    match = re.match(r"^(.+) in (" + _BROWSER_TAIL + r")$", text)

    if match:
        browser = config.BROWSER_ALIASES[match.group(2)]
        resolved = _resolve(match.group(1).strip())

        if resolved is not None:
            return _open_in_browser(browser, resolved[0], resolved[1])

        # unresolved — leave the whole sentence to the later skills

    # --------------------------------------------------------
    # DEFAULT BROWSER (config.BROWSER, else the Windows default)
    # --------------------------------------------------------

    resolved = _resolve(text)

    if resolved is not None:
        url, reply_prefix = resolved
        _open(url)
        return t("web.reply", action=reply_prefix)

    return None


def name():
    return "web"
