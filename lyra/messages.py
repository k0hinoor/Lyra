"""
============================================================
 LYRA MESSAGES — every fixed thing she says, in English and Hindi
============================================================
 One dictionary, key -> (english, hindi), and one accessor:

     t("apps.opening", name="Notepad")

 returns the string for the active SPEECH_LANGUAGE: Hindi when it is
 "hi", English for "auto" and "en". The English text is exactly what
 LYRA said before this catalog existed, so "auto"/"en" are unchanged.

 Hindi values are short, everyday spoken Hindi (not Sanskritised or
 literary), Devanagari, and feminine in the first person (LYRA is
 female: "खोल रही हूँ", "नहीं ले पाई"). Proper nouns and package
 names stay Latin; names the Hindi voice reads better in Devanagari
 go through spoken_name().
============================================================
"""

import string

from . import config

# key -> (english, hindi)
CATALOG = {
    # ---------------------------------------------------------- session
    "session.goodbye": ("Going offline. Goodbye.", "मैं अब बंद हो रही हूँ। अलविदा।"),
    "session.yes": ("Yes?", "हाँ, बोलिए?"),
    "session.stopping_task": ("Stopping the active task safely.", "चल रहा काम ध्यान से रोक रही हूँ।"),
    "session.still_working": (
        "I am still working. Say stop to cancel the active task.",
        "मैं अभी काम कर रही हूँ। रोकना हो तो रुको बोलिए।",
    ),
    "session.no_task": ("There is no active computer task.", "अभी कोई काम नहीं चल रहा।"),
    "session.done": ("Done.", "हो गया।"),
    "session.cancelled": ("Cancelled.", "ठीक है, रद्द कर दिया।"),
    "session.okay": ("Okay.", "ठीक है।"),
    "session.sleep": ("Okay, going back to sleep.", "ठीक है, मैं फिर से सो रही हूँ।"),
    "session.online": ("Online.", "मैं तैयार हूँ।"),
    "session.action_error": ("Action error: {error}", "काम में गड़बड़ी हुई: {error}"),

    # ---------------------------------------------------------- memory
    "memory.already": ("I already knew that.", "मुझे यह पहले से याद है।"),
    "memory.saved": ("I'll remember that.", "मैं यह याद रखूँगी।"),
    "memory.save_failed": (
        "I couldn't save that memory. Check the LYRA log.",
        "यह बात सेव नहीं हो पाई। LYRA का लॉग देखिए।",
    ),
    "memory.empty": ("I don't remember anything yet.", "अभी मुझे कुछ याद नहीं है।"),
    "memory.list_intro": ("Here's what I remember: ", "मुझे ये बातें याद हैं: "),
    "memory.forgotten": ("Forgotten.", "ठीक है, वह बात भूल गई हूँ।"),
    "memory.not_found": ("That wasn't in my memory.", "वह बात मेरी याददाश्त में नहीं थी।"),
    "memory.wipe_prompt": (
        "This deletes everything I remember. Say confirm to wipe it, or cancel.",
        "इससे मेरी सारी यादें मिट जाएँगी। मिटाना है तो हाँ बोलिए, नहीं तो नहीं।",
    ),
    "memory.wiped": ("Memory wiped clean.", "सारी यादें मिटा दीं।"),

    # ---------------------------------------------------------- planner (computer tasks)
    "planner.stopped_before": (
        "The task was stopped before any action was run.",
        "कोई भी कदम चलने से पहले काम रोक दिया गया।",
    ),
    "planner.no_plan": (
        "I couldn't create a valid, safe action plan for that task.",
        "इस काम के लिए मैं कोई सही और सुरक्षित तरीका नहीं बना पाई।",
    ),
    "planner.action_failed": (
        "The task stopped because an action failed: {detail}",
        "एक कदम नहीं हो पाया, इसलिए काम रुक गया: {detail}",
    ),
    "planner.action_failed_default": ("An action failed.", "एक कदम नहीं हो पाया।"),
    "planner.stopped": ("The task was stopped.", "काम रोक दिया गया।"),
    "planner.issued": (
        "I issued the planned actions. Their on-screen results are not yet independently verified.",
        "मैंने सारे कदम चला दिए हैं। स्क्रीन पर नतीजा अभी जाँचा नहीं गया है।",
    ),
    "planner.internal_error": (
        "The task stopped because of an internal action error. See the LYRA log.",
        "अंदर की किसी गड़बड़ी से काम रुक गया। LYRA का लॉग देखिए।",
    ),
    "planner.busy": (
        "I am already working on a computer task. Say stop to cancel it.",
        "मैं पहले से एक काम कर रही हूँ। रोकना हो तो रुको बोलिए।",
    ),
    "planner.started": (
        "Planning and carrying out the task. Say stop to cancel it.",
        "काम की तैयारी करके उसे कर रही हूँ। रोकना हो तो रुको बोलिए।",
    ),

    # ---------------------------------------------------------- brain
    "brain.offline": (
        "I can't reach my local brain. Is Ollama running?",
        "मैं अपने लोकल दिमाग तक नहीं पहुँच पा रही। क्या Ollama चल रहा है?",
    ),

    # ---------------------------------------------------------- apps
    "apps.not_found": ("I couldn't find an app called {name}.", "{name} नाम का कोई ऐप नहीं मिला।"),
    "apps.opening": ("Opening {name}.", "{name} खोल रही हूँ।"),
    "apps.closed": ("Closed {name}.", "{name} बंद कर दिया।"),
    "apps.not_running": ("I couldn't find {name} running.", "{name} अभी चल नहीं रहा।"),

    # ---------------------------------------------------------- web
    # The "action" pieces have no final punctuation: web.reply /
    # web.reply_in_browser finish the sentence.
    "web.search_youtube": ("Searching YouTube for {query}", "यूट्यूब पर {query} खोज रही हूँ"),
    "web.search_wikipedia": ("Searching Wikipedia for {query}", "विकिपीडिया पर {query} खोज रही हूँ"),
    "web.search": ("Searching for {query}", "{query} खोज रही हूँ"),
    "web.opening": ("Opening {name}", "{name} खोल रही हूँ"),
    "web.reply": ("{action}.", "{action}।"),
    "web.reply_in_browser": ("{action} in {browser}.", "{browser} में {action}।"),
    "web.opening_browser": ("Opening {browser}.", "{browser} खोल रही हूँ।"),
    "web.browser_fallback": (
        "I couldn't find {browser}, so I opened it in your default browser.",
        "{browser} नहीं मिला, इसलिए आपके डिफ़ॉल्ट ब्राउज़र में खोल दिया।",
    ),
    "web.browser_missing": ("I couldn't find {browser} on this PC.", "इस पीसी पर {browser} नहीं मिला।"),
    "web.weather": (
        "{city}: {desc}, {temp} degrees, feels like {feels}. Humidity {humidity} percent.",
        "{city} में अभी {desc}, तापमान {temp} डिग्री है, पर {feels} डिग्री जैसा लग रहा है। "
        "नमी {humidity} प्रतिशत है।",
    ),
    "web.weather_failed": (
        "I couldn't fetch the weather for {city} right now.",
        "अभी {city} का मौसम नहीं मिल पाया।",
    ),

    # ---------------------------------------------------------- media
    "media.no_pycaw": ("Volume control needs the pycaw package.", "आवाज़ बदलने के लिए pycaw पैकेज चाहिए।"),
    "media.no_brightness": (
        "Brightness control needs the screen-brightness-control package.",
        "ब्राइटनेस बदलने के लिए screen-brightness-control पैकेज चाहिए।",
    ),
    "media.volume_is": ("Volume is at {level} percent.", "आवाज़ अभी {level} प्रतिशत पर है।"),
    "media.muted": ("Muted.", "आवाज़ बंद कर दी।"),
    "media.unmuted": ("Unmuted.", "आवाज़ चालू कर दी।"),
    "media.volume_read_failed": ("I couldn't read the volume.", "आवाज़ का लेवल पता नहीं चल पाया।"),
    "media.volume_change_failed": ("I couldn't change the volume.", "आवाज़ बदल नहीं पाई।"),
    "media.volume_still_muted": (
        "Volume is muted, volume set to {level} percent.",
        "आवाज़ म्यूट है, लेवल {level} प्रतिशत कर दिया।",
    ),
    "media.unmuted_volume_set": (
        "Unmuted, volume set to {level} percent.",
        "आवाज़ चालू की और {level} प्रतिशत कर दी।",
    ),
    "media.volume_set_max": (
        "Volume set to {level} percent, that is the maximum.",
        "आवाज़ {level} प्रतिशत कर दी, इससे ज़्यादा नहीं हो सकती।",
    ),
    "media.volume_set": ("Volume set to {level} percent.", "आवाज़ {level} प्रतिशत कर दी।"),
    "media.brightness_is": ("Brightness is at {level} percent.", "ब्राइटनेस अभी {level} प्रतिशत पर है।"),
    "media.brightness_read_failed": ("I couldn't read the brightness.", "ब्राइटनेस का लेवल पता नहीं चल पाया।"),
    "media.brightness_change_failed": ("I couldn't change the brightness.", "ब्राइटनेस बदल नहीं पाई।"),
    "media.brightness_set_max": (
        "Brightness set to {level} percent, that is the maximum.",
        "ब्राइटनेस {level} प्रतिशत कर दी, इससे ज़्यादा नहीं हो सकती।",
    ),
    "media.brightness_set": ("Brightness set to {level} percent.", "ब्राइटनेस {level} प्रतिशत कर दी।"),
    "media.playing": ("Playing.", "चला दिया।"),
    "media.paused": ("Paused.", "रोक दिया।"),
    "media.next": ("Next track.", "अगला गाना।"),
    "media.previous": ("Previous track.", "पिछला गाना।"),

    # ---------------------------------------------------------- system
    "system.time": ("It's {time}.", "अभी {time} हैं।"),
    "system.date": ("Today is {date}.", "आज {date} है।"),
    "system.no_psutil_battery": ("Battery status needs the psutil package.", "बैटरी देखने के लिए psutil पैकेज चाहिए।"),
    "system.no_battery": (
        "I couldn't find a battery — probably a desktop PC.",
        "कोई बैटरी नहीं मिली, शायद यह डेस्कटॉप पीसी है।",
    ),
    "system.battery": ("Battery is at {percent} percent and {state}.", "बैटरी {percent} प्रतिशत है और {state}।"),
    "system.charging": ("charging", "चार्ज हो रही है"),
    "system.on_battery": ("on battery", "चार्जर नहीं लगा है"),
    "system.battery_left": (" About {duration} left.", " लगभग {duration} बाकी है।"),
    "system.no_psutil_stats": ("System stats need the psutil package.", "सिस्टम की जानकारी के लिए psutil पैकेज चाहिए।"),
    "system.stats": (
        "CPU is at {cpu} percent, memory at {ram} percent.",
        "सीपीयू {cpu} प्रतिशत पर है और मेमोरी {ram} प्रतिशत पर।",
    ),
    "system.no_psutil_disk": ("Disk stats need the psutil package.", "डिस्क की जानकारी के लिए psutil पैकेज चाहिए।"),
    "system.disk": (
        "The main drive has {free} gigabytes free, out of {total}.",
        "मेन ड्राइव में {total} में से {free} जीबी खाली है।",
    ),
    "system.disk_failed": ("I couldn't read the disk usage.", "डिस्क की जानकारी नहीं मिल पाई।"),
    "system.ip": ("Your local IP address is {ip}.", "आपका लोकल आईपी एड्रेस है {ip}।"),
    "system.wifi_failed": (
        "I couldn't read the Wi-Fi details. Is Wi-Fi connected?",
        "वाई-फ़ाई की जानकारी नहीं मिल पाई। क्या वाई-फ़ाई जुड़ा है?",
    ),
    "system.wifi_no_password": (
        "The network is {ssid}, but the password isn't stored on this PC.",
        "नेटवर्क {ssid} है, पर इसका पासवर्ड इस पीसी पर सेव नहीं है।",
    ),
    "system.wifi_password": ("The password for {ssid} is: {password}.", "{ssid} का पासवर्ड है: {password}।"),
    "system.no_psutil_uptime": ("Uptime needs the psutil package.", "अपटाइम देखने के लिए psutil पैकेज चाहिए।"),
    "system.uptime": ("The system has been up for {duration}.", "सिस्टम {duration} से चल रहा है।"),
    "system.no_pyautogui_screenshot": (
        "Screenshots need the pyautogui package.", "स्क्रीनशॉट के लिए pyautogui पैकेज चाहिए।",
    ),
    "system.screenshot_saved": (
        "Screenshot saved to the Pictures folder.", "स्क्रीनशॉट Pictures फ़ोल्डर में सेव कर दिया।",
    ),
    "system.screenshot_failed": ("I couldn't take the screenshot.", "स्क्रीनशॉट नहीं ले पाई।"),
    "system.lock_windows_only": ("Locking only works on Windows.", "लॉक सिर्फ़ विंडोज़ पर होता है।"),
    "system.locked": ("Locked. See you soon.", "लॉक कर दिया। जल्दी मिलते हैं।"),
    "system.windows_only": ("That only works on Windows.", "यह सिर्फ़ विंडोज़ पर होता है।"),
    "system.shutdown_cancelled": ("Shutdown cancelled.", "शटडाउन रद्द कर दिया।"),
    "system.no_shutdown": ("There was no shutdown to cancel.", "रद्द करने के लिए कोई शटडाउन नहीं था।"),
    "system.shutdown_prompt": (
        "This will shut down the PC in {seconds} seconds. Say confirm to continue, or cancel.",
        "इससे पीसी {seconds} सेकंड में बंद हो जाएगा। करना है तो हाँ बोलिए, नहीं तो नहीं।",
    ),
    "system.shutdown_confirm": (
        "Shutting down in {seconds} seconds. Goodbye.",
        "{seconds} सेकंड में पीसी बंद हो रहा है। अलविदा।",
    ),
    "system.restart_prompt": (
        "This will restart the PC in {seconds} seconds. Say confirm to continue, or cancel.",
        "इससे पीसी {seconds} सेकंड में रीस्टार्ट होगा। करना है तो हाँ बोलिए, नहीं तो नहीं।",
    ),
    "system.restart_confirm": ("Restarting in {seconds} seconds.", "{seconds} सेकंड में रीस्टार्ट हो रहा है।"),
    "system.sleep_prompt": (
        "Put the PC to sleep? Say confirm, or cancel.",
        "पीसी को स्लीप मोड में डाल दूँ? हाँ या नहीं बोलिए।",
    ),
    "system.sleep_confirm": ("Sleeping. Goodnight.", "पीसी स्लीप मोड में जा रहा है। गुड नाइट।"),
    "system.recycle_prompt": (
        "This will permanently empty the recycle bin. Say confirm, or cancel.",
        "इससे रीसायकल बिन हमेशा के लिए खाली हो जाएगा। हाँ या नहीं बोलिए।",
    ),
    "system.recycle_confirm": ("Recycle bin emptied.", "रीसायकल बिन खाली कर दिया।"),

    # ---------------------------------------------------------- durations (uptime, battery)
    "duration.day": ("{n} day", "{n} दिन"),
    "duration.days": ("{n} days", "{n} दिन"),
    "duration.hour": ("{n} hour", "{n} घंटा"),
    "duration.hours": ("{n} hours", "{n} घंटे"),
    "duration.minute": ("{n} minute", "{n} मिनट"),
    "duration.minutes": ("{n} minutes", "{n} मिनट"),
    "duration.under_minute": ("less than a minute", "एक मिनट से कम"),

    # ---------------------------------------------------------- typing / keyboard
    "typing.no_packages": (
        "Typing needs the pyautogui and pyperclip packages.",
        "टाइप करने के लिए pyautogui और pyperclip पैकेज चाहिए।",
    ),
    "typing.typed": ("Typed.", "टाइप कर दिया।"),
    "typing.no_pyautogui": ("Key control needs the pyautogui package.", "कीबोर्ड चलाने के लिए pyautogui पैकेज चाहिए।"),
    "typing.unknown_key": ("I don't know the {key} key.", "मुझे {key} बटन नहीं पता।"),
    "typing.copied": ("Copied.", "कॉपी कर दिया।"),
    "typing.no_pyperclip": ("Clipboard needs the pyperclip package.", "क्लिपबोर्ड के लिए pyperclip पैकेज चाहिए।"),
    "typing.copied_to_clipboard": ("Copied to clipboard.", "क्लिपबोर्ड में कॉपी कर दिया।"),
    "typing.clipboard_empty": ("The clipboard is empty.", "क्लिपबोर्ड खाली है।"),
    "typing.clipboard_says": ("Clipboard says: {content}", "क्लिपबोर्ड में लिखा है: {content}"),
    "typing.clipboard_cleared": ("Clipboard cleared.", "क्लिपबोर्ड साफ़ कर दिया।"),

    # ---------------------------------------------------------- windows & tabs
    "windows.minimized": ("Minimized.", "विंडो छोटी कर दी।"),
    "windows.maximized": ("Maximized.", "विंडो बड़ी कर दी।"),
    "windows.desktop": ("Showing desktop.", "डेस्कटॉप दिखा रही हूँ।"),
    "windows.switching": ("Switching.", "विंडो बदल रही हूँ।"),
    "windows.task_view": ("Opening task view.", "टास्क व्यू खोल रही हूँ।"),
    "windows.closed_window": ("Closed window.", "विंडो बंद कर दी।"),
    "windows.new_tab": ("New tab.", "नया टैब खोल दिया।"),
    "windows.new_window": ("New window.", "नई विंडो खोल दी।"),
    "windows.closed_tab": ("Closed tab.", "टैब बंद कर दिया।"),
    "windows.reopened_tab": ("Reopened tab.", "टैब फिर से खोल दिया।"),
    "windows.next_tab": ("Next tab.", "अगला टैब।"),
    "windows.previous_tab": ("Previous tab.", "पिछला टैब।"),
    "windows.refreshing": ("Refreshing.", "पेज रीफ़्रेश कर रही हूँ।"),
    "windows.back": ("Going back.", "पीछे जा रही हूँ।"),
    "windows.forward": ("Going forward.", "आगे जा रही हूँ।"),
    "windows.zoom_in": ("Zooming in.", "ज़ूम इन कर रही हूँ।"),
    "windows.zoom_out": ("Zooming out.", "ज़ूम आउट कर रही हूँ।"),
    "windows.fullscreen": ("Toggled fullscreen.", "फ़ुल स्क्रीन बदल दी।"),

    # ---------------------------------------------------------- fun
    "fun.heads": ("Heads.", "चित आया।"),
    "fun.tails": ("Tails.", "पट आया।"),
    "fun.die": ("It's a {n}.", "{n} आया।"),
    "fun.rolled": ("You rolled {rolls}.", "पासे पर आया: {rolls}।"),
    "fun.number": ("Your number is {n}.", "आपका नंबर है {n}।"),
}

# Names the Hindi voice reads far better in Devanagari. Only used for
# placeholders in Hindi mode; English mode always gets the name unchanged.
HINDI_NAMES = {
    "youtube": "यूट्यूब", "google": "गूगल", "gmail": "जीमेल", "notepad": "नोटपैड",
    "brave": "ब्रेव", "chrome": "क्रोम", "google chrome": "गूगल क्रोम", "edge": "एज",
    "microsoft edge": "माइक्रोसॉफ्ट एज", "firefox": "फ़ायरफ़ॉक्स",
    "calculator": "कैलकुलेटर", "calc": "कैलकुलेटर", "whatsapp": "व्हाट्सऐप",
    "spotify": "स्पॉटिफ़ाई", "settings": "सेटिंग्स", "file explorer": "फ़ाइल एक्सप्लोरर",
    "paint": "पेंट", "wikipedia": "विकिपीडिया", "instagram": "इंस्टाग्राम",
    "facebook": "फ़ेसबुक", "netflix": "नेटफ़्लिक्स", "amazon": "अमेज़न",
    "task manager": "टास्क मैनेजर", "control panel": "कंट्रोल पैनल",
    "downloads": "डाउनलोड्स", "documents": "डॉक्यूमेंट्स", "desktop": "डेस्कटॉप",
}

_HINDI_WEEKDAYS = ("सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार")
_HINDI_MONTHS = (
    "जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून",
    "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर",
)


# ------------------------------------------------------------
# ACCESSORS
# ------------------------------------------------------------

def current_language():
    """"hi" when replies are Hindi (SPEECH_LANGUAGE "hi"), otherwise "en"."""

    return "hi" if getattr(config, "SPEECH_LANGUAGE", "auto") == "hi" else "en"


def is_hindi():
    return current_language() == "hi"


def t(key, /, **kwargs):
    """The catalog string for `key`, formatted, in the active language."""

    return t_in(current_language(), key, **kwargs)


def t_in(language, key, /, **kwargs):
    """Like t(), but in a fixed language ("en"/"hi") regardless of the setting.

    Used where the user's own words already chose the language: a Hindi
    memory command in "auto" mode is still answered in Hindi, as before.
    """

    english, hindi = CATALOG[key]
    template = hindi if language == "hi" else english
    return template.format(**kwargs) if kwargs else template


def placeholders(template):
    """The set of {field} names in one catalog template."""

    return {field for _text, field, _spec, _conv in string.Formatter().parse(template) if field}


def matches(key, text):
    """True when `text` was produced by catalog `key` (either language).

    Used to recognise a reply after the fact, e.g. "I couldn't find an app
    called X" arming the app-name repair turn in Session.
    """

    text = text or ""
    for template in CATALOG[key]:
        head, _sep, rest = template.partition("{")
        tail = template.rpartition("}")[2] if "{" in template else ""
        if "{" not in template:
            if text == template:
                return True
        elif text.startswith(head) and text.endswith(tail) and len(text) > len(head) + len(tail):
            return True
    return False


def spoken_name(name):
    """A name as the active voice should say it: Devanagari for known names in Hindi."""

    if not is_hindi() or not name:
        return name
    return HINDI_NAMES.get(str(name).strip().casefold(), name)


# ------------------------------------------------------------
# LOCALISED FORMATTING  (Hindi forms; English keeps its old format)
# ------------------------------------------------------------

def hindi_time(now):
    """"दोपहर के 3 बजकर 5 मिनट हुए" / "सुबह के 9 बजे" — for "अभी {time} हैं।"."""

    hour = now.hour
    if 4 <= hour < 12:
        period = "सुबह"
    elif 12 <= hour < 16:
        period = "दोपहर"
    elif 16 <= hour < 20:
        period = "शाम"
    else:
        period = "रात"
    clock = hour % 12 or 12
    if now.minute:
        return f"{period} के {clock} बजकर {now.minute} मिनट हुए"
    return f"{period} के {clock} बजे"


def hindi_date(now):
    """"सोमवार, 30 सितंबर 2026"."""

    return f"{_HINDI_WEEKDAYS[now.weekday()]}, {now.day} {_HINDI_MONTHS[now.month - 1]} {now.year}"
