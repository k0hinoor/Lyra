"""
============================================================
 TESTS — lyra/memory.py
============================================================
"""

import json

import pytest

from lyra import config
from lyra.memory import MAX_MEMORY_ITEMS, Memory


@pytest.fixture
def memory():
    return Memory()


# ------------------------------------------------------------
# EMPTY
# ------------------------------------------------------------

def test_starts_empty(memory):
    assert memory.items == []
    assert memory.context_block() == ""


# ------------------------------------------------------------
# ADD
# ------------------------------------------------------------

def test_add_returns_true_and_stores(memory):
    assert memory.add("my exam is on Friday") is True
    assert memory.items == ["my exam is on Friday"]


def test_add_rejects_duplicates(memory):
    memory.add("my exam is on Friday")
    assert memory.add("my exam is on Friday") is False
    assert len(memory.items) == 1


def test_add_rejects_blank(memory):
    assert memory.add("   ") is False
    assert memory.items == []


def test_add_strips_whitespace(memory):
    memory.add("  remember the milk  ")
    assert memory.items == ["remember the milk"]


# ------------------------------------------------------------
# PERSISTENCE
# ------------------------------------------------------------

def test_memory_survives_a_reload(memory):
    memory.add("my exam is on Friday")
    assert Memory().items == ["my exam is on Friday"]


def test_missing_file_is_not_an_error():
    assert config.MEMORY_FILE.exists() is False
    assert Memory().items == []


def test_corrupted_file_falls_back_to_empty(memory, isolated_memory_file):
    isolated_memory_file.write_text("{ not json", encoding="utf-8")
    assert Memory().items == []


def test_non_list_json_falls_back_to_empty(isolated_memory_file):
    isolated_memory_file.write_text('{"items": []}', encoding="utf-8")
    assert Memory().items == []


def test_saved_file_is_valid_json(memory, isolated_memory_file):
    memory.add("call mum")
    assert json.loads(isolated_memory_file.read_text(encoding="utf-8")) == ["call mum"]


# ------------------------------------------------------------
# REMOVE
# ------------------------------------------------------------

def test_remove_matches_partial_text_case_insensitively(memory):
    memory.add("my exam is on Friday")
    memory.add("buy milk")

    assert memory.remove("EXAM") == 1
    assert memory.items == ["buy milk"]


def test_remove_returns_zero_when_nothing_matches(memory):
    memory.add("buy milk")
    assert memory.remove("homework") == 0
    assert memory.items == ["buy milk"]


def test_remove_ignores_blank_query(memory):
    memory.add("buy milk")
    assert memory.remove("  ") == 0
    assert memory.items == ["buy milk"]


def test_remove_persists(memory):
    memory.add("buy milk")
    memory.remove("milk")
    assert Memory().items == []


# ------------------------------------------------------------
# CLEAR
# ------------------------------------------------------------

def test_clear_wipes_and_persists(memory):
    memory.add("one")
    memory.add("two")
    memory.clear()

    assert memory.items == []
    assert Memory().items == []


# ------------------------------------------------------------
# CONTEXT BLOCK
# ------------------------------------------------------------

def test_context_block_lists_items_for_the_brain(memory):
    memory.add("my exam is on Friday")

    block = memory.context_block()

    assert config.USER_NAME in block
    assert "- my exam is on Friday" in block


def test_context_block_only_sends_the_most_recent_items(memory):
    for i in range(MAX_MEMORY_ITEMS + 5):
        memory.add(f"item {i}")

    block = memory.context_block()

    assert f"- item {MAX_MEMORY_ITEMS + 4}" in block
    assert "- item 0" not in block


# ------------------------------------------------------------
# AUTOMATIC, EXPLICIT LIKES / DISLIKES
# ------------------------------------------------------------

def test_preferences_survive_a_restart_and_are_available_to_the_brain(memory):
    saved = memory.remember_preferences([("likes", "Arijit Singh"), ("dislikes", "rap")])
    assert saved == ["Preference: likes Arijit Singh.", "Preference: dislikes rap."]
    reloaded = Memory()
    assert reloaded.items == saved
    assert "Arijit Singh" in reloaded.context_block()
    assert "dislikes rap" in reloaded.context_block()


def test_duplicate_taste_is_not_saved_repeatedly(memory):
    memory.remember_preferences([("likes", "jazz")])
    assert memory.remember_preferences([("likes", "JAZZ")]) == []
    assert memory.items == ["Preference: likes jazz."]
    assert memory.preference_updates == []


def test_a_changed_taste_replaces_the_opposite_for_that_topic(memory):
    memory.add("my exam is on Friday")
    memory.remember_preferences([("likes", "Rap")])
    memory.remember_preferences([("dislikes", "rap")])
    assert memory.items == ["my exam is on Friday", "Preference: dislikes rap."]
    assert Memory().items == memory.items


def test_the_last_preference_for_a_topic_on_one_turn_wins(memory):
    assert memory.remember_preferences([("likes", "rap"), ("dislikes", "rap")]) == ["Preference: dislikes rap."]
    assert memory.items == ["Preference: dislikes rap."]


def test_preferences_can_be_forgotten_using_existing_commands(memory):
    memory.remember_preferences([("likes", "Arijit Singh"), ("dislikes", "rap")])
    assert memory.remove("rap") == 1
    assert Memory().items == ["Preference: likes Arijit Singh."]
    memory.clear()
    assert Memory().items == []


def test_preferences_keep_hindi_text_in_the_saved_json(memory, isolated_memory_file):
    memory.remember_preferences([("likes", "अरिजीत के गाने"), ("dislikes", "रैप")])
    raw = isolated_memory_file.read_text(encoding="utf-8")
    assert "अरिजीत" in raw and "रैप" in raw
    assert Memory().items == memory.items


def test_failed_preference_save_is_not_claimed_as_a_new_memory(memory, isolated_memory_file, monkeypatch):
    from lyra import memory as memory_module
    memory.add("my exam is on Friday")
    original = isolated_memory_file.read_bytes()

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(memory_module.os, "replace", fail)
    assert memory.remember_preferences([("likes", "jazz")]) == []
    assert memory.items == ["my exam is on Friday"]
    assert memory.preference_updates == []
    assert isolated_memory_file.read_bytes() == original
    assert list(isolated_memory_file.parent.glob("*.tmp")) == []


def test_invalid_or_overlong_preferences_are_rejected(memory):
    assert memory.remember_preferences([("maybe", "jazz"), ("likes", ""), ("likes", "x" * 200)]) == []
    assert memory.items == []
