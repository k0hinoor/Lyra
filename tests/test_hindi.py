"""
============================================================
 TESTS — lyra/hindi.py  (Hindi -> intent) and its Session hook
============================================================
 Evidence this guards (real session, SPEECH_LANGUAGE unset):

   You: ब्रेव क्रोम यूट्यू          (said "Brave Chrome YouTube kholo")
   Lyra: ब्रह्मक्रोम यूट्यू एक लोकप्रिय ब्रशिंग प्लेटफ़ॉर्म है ...   no browser
   You: यूट्यूट्यूब                  (bare "YouTube")
   Lyra: मल्टी-ट्यून यूट्यू लायरा, हाँ!                          chat reply

 Every Hindi pattern has a negative test proving it cannot hijack
 unrelated speech. All hardware is faked (pc / browser_launches).
============================================================
"""

import pytest

from lyra import config, hindi


# ------------------------------------------------------------
# REWRITES
# ------------------------------------------------------------

@pytest.mark.parametrize("spoken, command", [
    # open
    ("ब्रेव क्रोम यूट्यूब खोलो", "open brave and youtube"),
    ("Brave Chrome YouTube खोलो", "open brave and youtube"),      # mixed script (D)
    ("ब्रेव में यूट्यूब खोल दो", "open brave and youtube"),
    ("ब्रेव क्रोम यूट्यूट्यूट्यूब खोलो।", "open brave and youtube"),
    ("यूट्यूट्यूब", "open youtube"),                              # bare, stuttered (G)
    ("यूट्यूब", "open youtube"),
    ("नोटपैड खोलो", "open notepad"),
    ("कृपया नोटपैड ओपन करो", "open notepad"),
    ("गूगल क्रोम खोलो", "open chrome"),
    ("फ़ायरफ़ॉक्स चालू करो", "open firefox"),
    ("एज खोलो", "open edge"),
    ("गूगल खोलो", "open google"),
    # close
    ("नोटपैड बंद करो", "close notepad"),
    ("क्रोम बंद कर दो", "close chrome"),
    ("यूट्यूब बंद करो", "close tab"),
    ("कंप्यूटर बंद करो", "shut down the pc"),
    ("कंप्यूटर रीस्टार्ट करो", "restart the pc"),
    # volume / brightness
    ("आवाज़ बढ़ाओ", "volume up"),
    ("आवाज बढ़ाओ", "volume up"),                                   # nukta-less spelling
    ("वॉल्यूम कम करो", "volume down"),
    ("वोल्यूम तेज़ करो", "volume up"),
    ("आवाज़ थोड़ा कम करो", "volume down a bit"),
    ("आवाज़ बहुत बढ़ाओ", "volume up a lot"),
    ("आवाज़ 50 कर दो", "set volume to 50"),
    ("वॉल्यूम ५० पर करो", "set volume to 50"),
    ("आवाज़ 20 बढ़ाओ", "turn volume up by 20"),
    ("आवाज़ बंद करो", "mute"),
    ("म्यूट करो", "mute"),
    ("आवाज़ चालू करो", "unmute"),
    ("ब्राइटनेस बढ़ाओ", "brightness up"),
    ("चमक कम करो", "brightness down"),
    ("आवाज़ बताओ", "what is the volume"),
    ("ब्राइटनेस बताओ", "what is the brightness"),
    # playback
    ("गाना बजाओ", "play music"),
    ("गाना चलाओ", "play music"),
    ("प्ले करो", "play"),
    ("गाना बंद करो", "pause music"),
    # tell
    ("समय बताओ", "what time is it"),
    ("टाइम क्या है", "what time is it"),
    ("कितने बजे हैं", "what time is it"),
    ("मौसम बताओ", "weather"),
    ("मौसम कैसा है", "weather"),
    ("आज की तारीख बताओ", "what is the date"),
    ("रुको", "stop"),
])
def test_recognised_hindi_commands_are_rewritten(spoken, command):
    assert hindi.to_command(spoken) == command


# ------------------------------------------------------------
# NEGATIVES — no pattern may hijack unrelated speech
# ------------------------------------------------------------

@pytest.mark.parametrize("spoken", [
    "मुझे कहानी सुनाओ",
    "मुझे यूट्यूब पसंद है",                 # names a site, but it is conversation
    "यूट्यूब क्या है",                      # a question about YouTube, not "open"
    "यूट्यूब के बारे में बताओ",
    "ब्रेव लोग कभी डरते नहीं",              # "brave" the word
    "दरवाज़ा बंद करो",                      # close verb, unknown object
    "बंद",                                  # verb alone
    "खोलो",
    "आवाज़",                                # a knob alone is not a command
    "आवाज़ बहुत अच्छी है",                  # opinion about a voice
    "तुम्हारी आवाज़ प्यारी है",
    "गाना कौन सा अच्छा है",
    "मुझे गाने पसंद हैं",
    "समय बहुत कीमती है",
    "मौसम",                                 # topic alone
    "कम से कम एक बार",                      # "कम" (down) in ordinary speech
    "ज़रा सोचो",
    "नोटपैड यूट्यूब खोलो",                   # two non-browser targets: ambiguous
    "क्रोम 50 खोलो",                         # a number that means nothing here
    "आवाज़ करो",                             # set verb without a number
    "नमस्ते लायरा",
    "पापा को फोन करो",
    "क्या तुम्हें संगीत पसंद है",
    "मुझे हिंदी में जवाब दो",
    "याद रखना कि मेरा पसंदीदा गायक अरिजीत है",
    "यूट्यूब चलाओ और गाना बढ़ाओ",            # two verbs
])
def test_unrelated_speech_is_never_rewritten(spoken):
    assert hindi.to_command(spoken) is None


@pytest.mark.parametrize("command, skill", [
    ("open brave and youtube", "skill:web"), ("open youtube", "skill:web"),
    ("open google", "skill:web"), ("open notepad", "skill:apps"),
    ("open chrome", "skill:apps"), ("close notepad", "skill:apps"),
    ("close tab", "skill:windows"), ("shut down the pc", "skill:system"),
    ("restart the pc", "skill:system"), ("volume up", "skill:media"),
    ("volume down a bit", "skill:media"), ("volume up a lot", "skill:media"),
    ("set volume to 50", "skill:media"), ("turn volume up by 20", "skill:media"),
    ("mute", "skill:media"), ("unmute", "skill:media"),
    ("brightness up", "skill:media"), ("what is the volume", "skill:media"),
    ("what is the brightness", "skill:media"), ("play music", "skill:media"),
    ("play", "skill:media"), ("pause music", "skill:media"),
    ("what time is it", "skill:system"), ("what is the date", "skill:system"),
])
def test_every_rewrite_target_is_understood_by_its_skill(pc, browser_launches, monkeypatch, command, skill):
    from lyra.skills import route_with_handler, web
    monkeypatch.setattr(web, "_weather", lambda city: "weather report")
    reply, confirmation, handler = route_with_handler(command, command)
    assert handler == skill
    assert reply is not None or confirmation is not None


def test_the_weather_rewrite_reaches_the_weather_skill(monkeypatch):
    from lyra.skills import route_with_handler, web
    monkeypatch.setattr(web, "_weather", lambda city: f"weather for {city}")
    reply, _confirmation, handler = route_with_handler("weather", "weather")
    assert handler == "skill:web" and reply == f"weather for {config.DEFAULT_CITY}"


@pytest.mark.parametrize("typed", [
    "open notepad", "volume up", "open brave and youtube", "youtube", "tell me a story",
])
def test_english_text_is_never_touched(typed):
    assert hindi.to_command(typed) is None


def test_ordinary_words_are_never_destuttered_into_names():
    # "नाना" / "पापा" repeat a syllable but are not stuttered brand names.
    assert hindi.to_command("नाना") is None
    assert hindi.to_command("पापा") is None


# ------------------------------------------------------------
# SESSION HOOK — hi mode reaches the real skills
# ------------------------------------------------------------

def test_brave_chrome_youtube_kholo_opens_youtube_in_brave(
        hindi_mode, session, fake_brain, pc, browser_launches):
    session.process("ब्रेव क्रोम यूट्यूब खोलो")
    assert browser_launches == [("brave", "https://www.youtube.com")]
    assert fake_brain.asked == []                       # no essay (E)


def test_a_bare_stuttered_youtube_opens_youtube(hindi_mode, session, fake_brain, pc):
    session.process("यूट्यूट्यूब")
    assert pc.urls == ["https://www.youtube.com"]
    assert fake_brain.asked == []


def test_notepad_kholo_opens_notepad(hindi_mode, session, fake_brain, pc):
    session.process("नोटपैड खोलो")
    assert pc.started == ["notepad"]
    assert fake_brain.asked == []


def test_awaaz_badhao_turns_the_volume_up(hindi_mode, session, pc):
    session.process("आवाज़ बढ़ाओ")
    assert pc.volume["level"] == 40                     # 30 + the default step
    assert pc.volume["calls"] == [40]


@pytest.mark.parametrize("spoken, level", [
    ("आवाज़ 50 कर दो", 50), ("आवाज़ थोड़ा कम करो", 25), ("आवाज़ 20 बढ़ाओ", 50),
])
def test_volume_levels_and_steps_reach_the_media_skill(hindi_mode, session, pc, spoken, level):
    session.process(spoken)
    assert pc.volume["level"] == level


def test_awaaz_band_karo_mutes(hindi_mode, session, pc):
    session.process("आवाज़ बंद करो")
    assert pc.volume["muted"] is True


def test_brightness_is_raised(hindi_mode, session, pc):
    session.process("चमक बढ़ाओ")
    assert pc.brightness.level == 60


def test_gaana_bajao_presses_play(hindi_mode, session, pc):
    session.process("गाना बजाओ")
    assert pc.pyauto.pressed("playpause")


def test_a_hindi_story_request_still_reaches_the_chat_model(hindi_mode, session, fake_brain, pc):
    session.process("मुझे कहानी सुनाओ")
    assert fake_brain.asked == ["मुझे कहानी सुनाओ"]
    assert pc.started == [] and pc.urls == [] and pc.volume["calls"] == []


def test_conversation_about_youtube_is_not_turned_into_an_action(
        hindi_mode, session, fake_brain, pc, browser_launches):
    session.process("मुझे यूट्यूब पसंद है")
    assert fake_brain.asked == ["मुझे यूट्यूब पसंद है"]
    assert pc.urls == [] and browser_launches == []


def test_the_hindi_wake_name_is_stripped_before_the_intent(hindi_mode, session, fake_brain, pc):
    session.process("हे लायरा नोटपैड खोलो")
    assert pc.started == ["notepad"]
    assert fake_brain.asked == []


def test_typed_english_routes_exactly_as_before_in_hindi_mode(hindi_mode, session, fake_brain, pc):
    session.process("open notepad")
    session.process("volume up")
    assert pc.started == ["notepad"]
    assert pc.volume["calls"] == [40]
    assert fake_brain.asked == []


def test_the_layer_is_off_outside_hindi_mode(session, fake_brain, pc):
    # SPEECH_LANGUAGE="auto" (the suite default) keeps today's behaviour.
    session.process("नोटपैड खोलो")
    assert pc.started == []
    assert fake_brain.asked == ["नोटपैड खोलो"]


def test_a_hindi_shutdown_asks_for_confirmation_and_haan_confirms(hindi_mode, session, pc):
    session.process("कंप्यूटर बंद करो")
    assert session.pending_confirmation is not None
    assert pc.shell.commands == []                       # nothing before the answer

    session.process("हाँ")
    assert session.pending_confirmation is None
    assert pc.shell.commands[-1][:2] == ["shutdown", "/s"]


def test_nahin_cancels_a_pending_confirmation(hindi_mode, session, pc):
    session.process("कंप्यूटर बंद करो")
    session.process("नहीं")
    assert session.pending_confirmation is None
    assert pc.shell.commands == []


def test_hindi_confirmation_words_are_ignored_outside_hindi_mode(session, pc, monkeypatch):
    from lyra.skills import system
    monkeypatch.setattr(system, "IS_WINDOWS", True)
    session.process("shut down the pc")
    session.process("हाँ")
    assert pc.shell.commands == []                       # auto mode: unchanged behaviour


# ------------------------------------------------------------
# HINDI STOP / SLEEP / THANKS / TERMINATE (hi mode only)
# ------------------------------------------------------------

@pytest.mark.parametrize("spoken", [
    "टर्मिनेट एक्जीक्यूशन", "टर्मिनेट एग्जीक्यूशन", "लायरा अलविदा",
])
def test_the_kill_phrase_survives_hindi_decoding(hindi_mode, session, spoken):
    from lyra.utils import normalize
    assert session.process(spoken) is True
    from lyra import utils
    assert utils.is_terminate(normalize(spoken))


def test_hindi_kill_phrases_do_nothing_outside_hindi_mode():
    from lyra import utils
    assert not utils.is_terminate("टर्मिनेट एक्जीक्यूशन")


def test_hindi_sleep_thanks_and_stop_phrases(hindi_mode):
    from lyra import utils
    assert utils.is_sleep("सो जाओ")
    assert utils.is_thanks("धन्यवाद")
    assert utils.is_stop_speech("चुप रहो")
    # Negative: ordinary sentences stay ordinary.
    assert not utils.is_sleep("मुझे नींद आ रही है")
    assert not utils.is_stop_speech("बस स्टैंड कहाँ है")
    assert not utils.is_terminate("टर्मिनेटर फिल्म")


def test_hindi_phrases_are_inert_in_auto_mode():
    from lyra import utils
    assert config.SPEECH_LANGUAGE == "auto"
    assert not utils.is_sleep("सो जाओ")
    assert not utils.is_thanks("धन्यवाद")
    assert not utils.is_stop_speech("चुप रहो")
