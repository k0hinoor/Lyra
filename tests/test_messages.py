"""
============================================================
 TESTS — lyra/messages.py and Hindi output (SPEECH_LANGUAGE="hi")
============================================================
 Evidence this guards: with Hindi selected, every fixed reply was still
 English ("Opening Notepad.", "Volume set to 40 percent.", "This will
 shut down the PC in 10 seconds...") and was read by the Hindi voice or
 by the English pack mid-conversation.

 English values must stay byte-identical: "auto"/"en" users hear exactly
 what they heard before (the rest of the suite asserts those strings).
============================================================
"""

import ast
import re
from pathlib import Path

import pytest

from lyra import config, messages
from lyra.messages import CATALOG, placeholders, t

_DEVANAGARI = re.compile(r"[\u0900-\u097F]")


# ------------------------------------------------------------
# (a) (b)  CATALOG SHAPE
# ------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(CATALOG))
def test_every_hindi_value_is_devanagari(key):
    english, hindi = CATALOG[key]
    assert english and hindi
    assert _DEVANAGARI.search(hindi), f"{key}: Hindi value has no Devanagari: {hindi!r}"


@pytest.mark.parametrize("key", sorted(CATALOG))
def test_placeholders_match_between_languages(key):
    english, hindi = CATALOG[key]
    assert placeholders(english) == placeholders(hindi), key


@pytest.mark.parametrize("key", sorted(CATALOG))
def test_first_person_hindi_is_feminine(key):
    # LYRA is female: "रही हूँ", "पाई", never the masculine first person.
    # (Impersonal "पता नहीं चल पाया" is correct: its subject is पता.)
    hindi = CATALOG[key][1]
    for masculine in ("रहा हूँ", "सकता हूँ", "पाया हूँ", "करूँगा", "गया हूँ", "मैं समझ गया", "नहीं ले पाया"):
        assert masculine not in hindi, f"{key}: masculine first person in {hindi!r}"


def test_key_names_are_namespaced():
    for key in CATALOG:
        assert re.fullmatch(r"[a-z]+\.[a-z_]+", key), key


# ------------------------------------------------------------
# (c)  t() FOLLOWS THE MODE
# ------------------------------------------------------------

def test_t_is_english_in_auto_mode():
    assert config.SPEECH_LANGUAGE == "auto"
    assert t("apps.opening", name="Notepad") == "Opening Notepad."
    assert t("media.volume_set", level=40) == "Volume set to 40 percent."
    assert t("session.goodbye") == "Going offline. Goodbye."


def test_t_is_english_in_en_mode(monkeypatch):
    monkeypatch.setattr(config, "SPEECH_LANGUAGE", "en")
    assert t("apps.opening", name="Notepad") == "Opening Notepad."


def test_t_is_hindi_in_hi_mode(hindi_mode):
    assert t("apps.opening", name="Notepad") == "Notepad खोल रही हूँ।"
    assert t("media.volume_set", level=40) == "आवाज़ 40 प्रतिशत कर दी।"
    assert t("session.goodbye") == "मैं अब बंद हो रही हूँ। अलविदा।"


def test_a_placeholder_named_key_does_not_clash_with_the_accessor(hindi_mode):
    assert t("typing.unknown_key", key="f13") == "मुझे f13 बटन नहीं पता।"


def test_t_in_forces_a_language_regardless_of_the_setting(hindi_mode):
    assert messages.t_in("en", "memory.saved") == "I'll remember that."
    assert messages.t_in("hi", "memory.saved") == "मैं यह याद रखूँगी।"


def test_matches_recognises_a_formatted_reply_in_either_language():
    assert messages.matches("apps.not_found", "I couldn't find an app called Foo.")
    assert messages.matches("apps.not_found", "फू नाम का कोई ऐप नहीं मिला।")
    assert not messages.matches("apps.not_found", "Opening Foo.")


def test_spoken_name_uses_devanagari_only_in_hindi_mode(monkeypatch):
    assert messages.spoken_name("YouTube") == "YouTube"
    monkeypatch.setattr(config, "SPEECH_LANGUAGE", "hi")
    assert messages.spoken_name("YouTube") == "यूट्यूब"
    assert messages.spoken_name("Some Unknown App") == "Some Unknown App"


def test_hindi_time_and_date_formats():
    import datetime
    assert messages.hindi_time(datetime.datetime(2026, 9, 30, 15, 5)) == "दोपहर के 3 बजकर 5 मिनट हुए"
    assert messages.hindi_time(datetime.datetime(2026, 9, 30, 9, 0)) == "सुबह के 9 बजे"
    assert messages.hindi_time(datetime.datetime(2026, 9, 30, 0, 30)) == "रात के 12 बजकर 30 मिनट हुए"
    assert messages.hindi_date(datetime.datetime(2026, 9, 30)) == "बुधवार, 30 सितंबर 2026"


# ------------------------------------------------------------
# NO HARD-CODED REPLIES LEFT IN THE SKILLS
# ------------------------------------------------------------

_SKILLS = Path(__file__).resolve().parents[1] / "lyra" / "skills"


@pytest.mark.parametrize("module", sorted(p.name for p in _SKILLS.glob("*.py")))
def test_skills_return_no_hard_coded_english_sentences(module):
    """A `return "Something."` in a skill would bypass the catalog."""

    tree = ast.parse((_SKILLS / module).read_text(encoding="utf-8"))
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            text = value.value
        elif isinstance(value, ast.JoinedStr):
            text = "".join(
                part.value for part in value.values
                if isinstance(part, ast.Constant) and isinstance(part.value, str)
            )
        else:
            continue
        if re.search(r"[A-Za-z]{2,}.*[.?!]\s*$", text) and " " in text:
            offenders.append((node.lineno, text))
    assert offenders == [], f"{module}: hard-coded replies {offenders}"


# ------------------------------------------------------------
# (d)  HINDI-MODE SESSION SMOKE — nothing English-only is spoken
# ------------------------------------------------------------

class RecordingVoice:
    """Stands in for Voice: records every sentence handed to the speaker."""

    def __init__(self):
        self.spoken = []

    def speak(self, text):
        self.spoken.append(text)
        return True

    def speak_stream(self, sentences):
        for sentence in sentences:
            if sentence and sentence.strip():
                self.spoken.append(sentence)
        return True


@pytest.fixture
def hindi_session(hindi_mode, fake_brain):
    import main
    from lyra.memory import Memory

    voice = RecordingVoice()
    return main.Session(fake_brain, Memory(), voice=voice), voice


def _assert_all_hindi(spoken):
    assert spoken, "nothing was spoken"
    for sentence in spoken:
        assert _DEVANAGARI.search(sentence), f"English-only sentence in Hindi mode: {sentence!r}"


def test_hindi_mode_volume_reply_is_hindi(hindi_session, pc):
    session, voice = hindi_session
    session.process("आवाज़ बढ़ाओ")
    session.process("volume up")                         # typed English, same reply language
    assert voice.spoken == ["आवाज़ 40 प्रतिशत कर दी।", "आवाज़ 50 प्रतिशत कर दी।"]


def test_hindi_mode_app_open_reply_is_hindi(hindi_session, pc):
    session, voice = hindi_session
    session.process("नोटपैड खोलो")
    assert voice.spoken == ["नोटपैड खोल रही हूँ।"]


def test_hindi_mode_browser_reply_is_hindi(hindi_session, pc, browser_launches):
    session, voice = hindi_session
    session.process("ब्रेव क्रोम यूट्यूब खोलो")
    assert voice.spoken == ["ब्रेव में यूट्यूब खोल रही हूँ।"]


def test_hindi_mode_confirmation_flow_is_hindi(hindi_session, pc):
    session, voice = hindi_session
    session.process("कंप्यूटर बंद करो")
    session.process("नहीं")
    session.process("कंप्यूटर रीस्टार्ट करो")
    session.process("हाँ")
    _assert_all_hindi(voice.spoken)
    assert voice.spoken[0].startswith("इससे पीसी")
    assert voice.spoken[1] == "ठीक है, रद्द कर दिया।"


def test_hindi_mode_session_replies_are_hindi(hindi_session, pc):
    session, voice = hindi_session
    for said in ("stop", "लायरा", "time", "what is the date", "volume", "mute",
                 "flip a coin", "remember that I like chai", "what do you remember",
                 "terminate execution"):
        session.process(said)
    _assert_all_hindi(voice.spoken)


def test_hindi_mode_app_not_found_still_arms_the_repair_turn(hindi_session, pc, monkeypatch):
    from lyra.skills import apps

    def start(target):
        if target != "notepad":
            raise OSError("not found")
        pc.started.append(target)

    monkeypatch.setattr(apps, "_start", start)
    session, voice = hindi_session
    session.process("open notpad")
    assert session.last_app_not_found
    session.process("no i meant notepad")
    assert pc.started == ["notepad"]
    _assert_all_hindi(voice.spoken)


def test_auto_mode_session_replies_are_unchanged(session, pc):
    spoken = []
    session.say = lambda text, handler="session": spoken.append(text)
    session.process("volume up")
    session.process("stop")
    assert spoken == ["Volume set to 40 percent.", "There is no active computer task."]


# ------------------------------------------------------------
# §7.1 BRAIN — Hindi block only in hi mode
# ------------------------------------------------------------

def _system_prompt(brain_module):
    from lyra.memory import Memory
    brain = brain_module.Brain.__new__(brain_module.Brain)
    brain.memory = Memory()
    brain.history = []
    return brain._messages("hello")[0]["content"]


def test_the_hindi_block_is_appended_only_in_hindi_mode(monkeypatch):
    from lyra import brain as brain_module

    assert brain_module.HINDI_MODE_PROMPT not in _system_prompt(brain_module)
    monkeypatch.setattr(config, "SPEECH_LANGUAGE", "en")
    assert brain_module.HINDI_MODE_PROMPT not in _system_prompt(brain_module)

    monkeypatch.setattr(config, "SPEECH_LANGUAGE", "hi")
    prompt = _system_prompt(brain_module)
    assert prompt.startswith(brain_module.SYSTEM_PROMPT)       # base prompt untouched
    assert prompt.endswith(brain_module.HINDI_MODE_PROMPT)     # last, where small models look


def test_the_hindi_block_covers_the_brief():
    from lyra import brain as brain_module
    block = brain_module.HINDI_MODE_PROMPT
    assert "Devanagari" in block and "Never reply with an English" in block
    assert "सकती" in block and "female" in block
    assert "Never invent brand" in block
    assert "repeat" in block


def test_the_offline_fallback_is_hindi_in_hindi_mode(monkeypatch, hindi_mode):
    from lyra import brain as brain_module

    def boom(*_args, **_kwargs):
        raise ConnectionError("no ollama")

    brain = brain_module.Brain.__new__(brain_module.Brain)
    from lyra.memory import Memory
    brain.memory = Memory()
    brain.history = []
    monkeypatch.setattr(brain_module.requests, "post", boom)
    assert list(brain.ask_stream("नमस्ते")) == [t("brain.offline")]
    assert _DEVANAGARI.search(t("brain.offline"))


# ------------------------------------------------------------
# §7.2 VOICE — forced Hindi pack in hi mode
# ------------------------------------------------------------

def test_run_voice_test_follows_hindi_mode(monkeypatch, hindi_mode, capfd):
    import main
    from lyra import voice as voice_module
    calls = []

    class HindiVoice:
        def __init__(self, language):
            calls.append(language)
            self.ok = True

        def speak(self, text):
            calls.append(text)
            return True

    monkeypatch.setattr(voice_module, "Voice", HindiVoice)
    assert main.run_voice_test() == 0
    assert calls == ["hi", main.HINDI_VOICE_TEST_SENTENCE]
