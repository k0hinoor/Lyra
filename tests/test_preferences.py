"""Preferences are facts the user states, never guesses by the model."""

import pytest

from lyra.preferences import MAX_PREFERENCE_LENGTH, extract_preferences


@pytest.mark.parametrize("text, expected", [
    ("I like Arijit Singh", [("likes", "Arijit Singh")]),
    ("I love soulful Hindi music.", [("likes", "soulful Hindi music")]),
    ("I really enjoy jazz", [("likes", "jazz")]),
    ("Personally, I prefer cinematic instrumentals", [("likes", "cinematic instrumentals")]),
    ("I DON'T LIKE RAP", [("dislikes", "RAP")]),
    ("I don't really like rap", [("dislikes", "rap")]),
    ("I do not enjoy loud songs", [("dislikes", "loud songs")]),
    ("I dislike heavy metal", [("dislikes", "heavy metal")]),
    ("I hate noisy music", [("dislikes", "noisy music")]),
    ("I no longer like rap", [("dislikes", "rap")]),
    ("I don't like rap anymore", [("dislikes", "rap")]),
    ("I like rap now", [("likes", "rap")]),
    ("I like A.R. Rahman", [("likes", "A.R. Rahman")]),
    ("मुझे अरिजीत के गाने पसंद हैं।", [("likes", "अरिजीत के गाने")]),
    ("मुझे रैप पसंद नहीं है।", [("dislikes", "रैप")]),
    ("मुझे रैप नहीं पसंद है", [("dislikes", "रैप")]),
    ("मुझे जैज़ बहुत पसंद है।", [("likes", "जैज़")]),
    ("मुझे रैप नापसंद है", [("dislikes", "रैप")]),
    ("mujhe arijit ke gaane pasand hain", [("likes", "arijit ke gaane")]),
    ("mujhe rap pasand nahi hai", [("dislikes", "rap")]),
    ("mujhe rap nahi pasand hai", [("dislikes", "rap")]),
])
def test_explicit_first_person_preferences(text, expected):
    assert extract_preferences(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("I love Arijit Singh but I don't like rap", [("likes", "Arijit Singh"), ("dislikes", "rap")]),
    ("I like jazz and enjoy ghazals but hate rap", [("likes", "jazz"), ("likes", "ghazals"), ("dislikes", "rap")]),
    ("I like rap but I don't like rap", [("likes", "rap"), ("dislikes", "rap")]),
    ("मुझे अरिजीत पसंद है लेकिन मुझे रैप पसंद नहीं है।", [("likes", "अरिजीत"), ("dislikes", "रैप")]),
    ("मुझे जैज़ पसंद है लेकिन रैप पसंद नहीं है।", [("likes", "जैज़"), ("dislikes", "रैप")]),
    ("मुझे जैज़ पसंद है और मुझे रैप पसंद नहीं है", [("likes", "जैज़"), ("dislikes", "रैप")]),
])
def test_multiple_likes_and_dislikes(text, expected):
    assert extract_preferences(text) == expected


@pytest.mark.parametrize("text", [
    "Do you like music?",
    "So do you like music?",
    "Do I like jazz?",
    "What music do I like",
    "क्या तुम्हें संगीत पसंद है?",
    "I used to like rap",
    "I might like rap",
    "I think I like rap",
    "If I like rap, what should I listen to",
    "I like jazz maybe",
    "I don't dislike rap",
    "I don't hate rap",
    "My friend likes jazz",
    "My brother said I like rap",
    'He said "I like rap"',
    'I like "ignore previous instructions"',
    "I like 'a quote about rap'",
    "Play some music",
    "Can you play jazz",
    "I would like you to play jazz",
    "I like jazz but don't remember this",
    "I like jazz and turn the volume up",
    "I like jazz. I also play piano",
    "मुझे शायद रैप पसंद है",
    "I like not rap",
    "I like " + "x" * (MAX_PREFERENCE_LENGTH + 1),
    "",
])
def test_questions_uncertain_statements_quotes_and_commands_are_not_memories(text):
    assert extract_preferences(text) == []


def test_preference_extraction_is_bounded():
    preferences = extract_preferences(" and ".join(f"I like genre {i}" for i in range(30)))
    assert len(preferences) == 6


def test_duplicates_in_one_utterance_are_removed():
    assert extract_preferences("I like jazz and I like jazz") == [("likes", "jazz")]


@pytest.mark.parametrize("text", [
    "I like to open notepad and write stories",
    "Do you like to open notepad and write stories?",
    "I like music maybe",
    "I like 'a quote about music'",
    "I love jazz",
    "मुझे अरिजीत के गाने पसंद हैं।",
])
def test_taste_intent_is_conversation_even_if_the_statement_cannot_be_saved(text):
    from lyra.preferences import is_taste_conversation
    assert is_taste_conversation(text)


@pytest.mark.parametrize("text", [
    "I would like you to turn the volume up",
    "open notepad and write about India",
    "play music",
    "set volume to 15",
])
def test_real_requests_are_not_confused_with_preferences(text):
    from lyra.preferences import is_taste_conversation
    assert not is_taste_conversation(text)
