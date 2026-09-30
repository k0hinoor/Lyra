"""Bilingual setup preserves other settings and refuses unsafe overwrites."""

import json
import os
import subprocess
import sys

import pytest

from lyra import config, settings, setup_voice
from lyra.voice_catalog import VOICE_CHOICES, parse_voice_model


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    path = tmp_path / "user-data" / "settings.json"
    monkeypatch.setattr(config, "SETTINGS_FILE", path)
    return path


@pytest.fixture
def downloads(monkeypatch, tmp_path):
    models = []

    def download(model):
        models.append(model)
        return tmp_path / (model + ".onnx")

    monkeypatch.setattr(setup_voice, "ensure_voice_pack", download)
    return models


def test_settings_update_merges_without_losing_existing_values(settings_file):
    settings_file.parent.mkdir()
    settings_file.write_text(json.dumps({"BROWSER": "brave", "VOICE_SPEED": 1.2, "custom": "kept"}))
    settings.update_settings({"HINDI_VOICE_MODEL": "hi_IN-rohan-medium"})
    assert json.loads(settings_file.read_text()) == {
        "BROWSER": "brave", "VOICE_SPEED": 1.2, "custom": "kept",
        "HINDI_VOICE_MODEL": "hi_IN-rohan-medium",
    }
    assert list(settings_file.parent.glob("*.tmp")) == []


@pytest.mark.parametrize("contents", ["{not json", "[]", "null"])
def test_settings_update_never_overwrites_a_malformed_file(settings_file, contents):
    settings_file.parent.mkdir()
    settings_file.write_text(contents)
    with pytest.raises(ValueError):
        settings.update_settings({"VOICE_SPEED": 1.1})
    assert settings_file.read_text() == contents


def test_failed_atomic_replace_preserves_original_settings(settings_file, monkeypatch):
    settings.update_settings({"BROWSER": "brave"})
    previous = settings_file.read_bytes()

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(settings.os, "replace", fail)
    with pytest.raises(OSError):
        settings.update_settings({"HINDI_VOICE_MODEL": "hi_IN-rohan-medium"})
    assert settings_file.read_bytes() == previous
    assert list(settings_file.parent.glob("*.tmp")) == []


def test_list_voices_is_offline(settings_file, downloads, capsys):
    assert setup_voice.main(["--list"]) == 0
    assert downloads == []
    assert not settings_file.exists()
    output = capsys.readouterr().out
    for model in VOICE_CHOICES["hi"]:
        assert model in output


def test_hindi_selection_and_whisper_setup_preserve_english_voice(settings_file, downloads):
    settings.update_settings({"VOICE_MODEL": "en_US-amy-medium", "OUTPUT_DEVICE": 4})
    assert setup_voice.main([
        "--language", "hi", "--model", "hi_IN-rohan-medium",
        "--set-default", "--whisper-model", "small",
    ]) == 0
    assert downloads == ["hi_IN-rohan-medium"]
    assert json.loads(settings_file.read_text()) == {
        "VOICE_MODEL": "en_US-amy-medium", "OUTPUT_DEVICE": 4,
        "HINDI_VOICE_MODEL": "hi_IN-rohan-medium", "WHISPER_MODEL": "small", "WHISPER_LANGUAGE": "auto",
    }


def test_all_hindi_downloads_three_packs_without_changing_settings(settings_file, downloads):
    assert setup_voice.main(["--all-hindi"]) == 0
    assert downloads == list(VOICE_CHOICES["hi"])
    assert not settings_file.exists()


def test_setup_without_flags_still_downloads_the_configured_english_voice(settings_file, downloads):
    assert setup_voice.main([]) == 0
    assert downloads == [config.VOICE_MODEL]
    assert not settings_file.exists()


def test_language_is_inferred_from_an_explicit_model(settings_file, downloads):
    assert setup_voice.main(["--model", "hi_IN-pratham-medium", "--set-default"]) == 0
    assert json.loads(settings_file.read_text()) == {"HINDI_VOICE_MODEL": "hi_IN-pratham-medium"}


@pytest.mark.parametrize("arguments", [
    ["--model", "../bad-model"],
    ["--model", "hi_IN/../../bad"],
    ["--language", "hi", "--model", "en_US-lessac-medium"],
    ["--model", "es_ES-test-medium"],
    ["--all-hindi", "--set-default"],
    ["--all-hindi", "--model", "hi_IN-rohan-medium"],
    ["--whisper-model", "small"],
])
def test_invalid_setup_arguments_never_download_or_write_settings(settings_file, downloads, arguments):
    with pytest.raises(SystemExit) as error:
        setup_voice.main(arguments)
    assert error.value.code == 2
    assert downloads == []
    assert not settings_file.exists()


def test_download_failure_never_selects_the_failed_voice(settings_file, monkeypatch):
    settings.update_settings({"BROWSER": "brave"})
    previous = settings_file.read_bytes()

    def fail(model):
        raise OSError("offline")

    monkeypatch.setattr(setup_voice, "ensure_voice_pack", fail)
    assert setup_voice.main(["--language", "hi", "--set-default"]) == 1
    assert settings_file.read_bytes() == previous


@pytest.mark.parametrize("model", ["../voice", "hi_IN-x/medium", "en_US-foo-medium/../", "https://example.com", "", None])
def test_voice_model_names_cannot_escape_the_model_directory(model):
    with pytest.raises(ValueError):
        parse_voice_model(model)


@pytest.mark.parametrize("model, expected", [
    ("hi_IN-priyamvada-medium", ("hi", "hi_IN", "priyamvada", "medium")),
    ("en_US-lessac-high", ("en", "en_US", "lessac", "high")),
    ("en_US-test-name-x_low", ("en", "en_US", "test-name", "x_low")),
])
def test_piper_ids_are_parsed_for_their_real_language(model, expected):
    assert parse_voice_model(model) == expected


def test_json_and_environment_apply_the_new_settings(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({
        "HINDI_VOICE_MODEL": "hi_IN-pratham-medium", "WHISPER_MODEL": "small",
        "WHISPER_LANGUAGE": "Hindi", "AUTO_REMEMBER_PREFERENCES": True,
    }))
    environment = {key: value for key, value in os.environ.items() if not key.startswith("LYRA_")}
    environment.update(LYRA_DATA_DIR=str(tmp_path), LYRA_HINDI_VOICE_MODEL="hi_IN-rohan-medium",
                       LYRA_WHISPER_LANGUAGE="auto", LYRA_AUTO_REMEMBER_PREFERENCES="false")
    result = subprocess.run([
        sys.executable, "-c",
        "from lyra import config; import json; print(json.dumps([config.HINDI_VOICE_MODEL, "
        "config.WHISPER_MODEL, config.WHISPER_LANGUAGE, config.AUTO_REMEMBER_PREFERENCES]))",
    ], capture_output=True, text=True, env=environment, check=True)
    assert json.loads(result.stdout) == ["hi_IN-rohan-medium", "small", "auto", False]
