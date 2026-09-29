"""
============================================================
 TESTS — lyra/transcript.py
============================================================
"""

import datetime

from lyra.transcript import Transcript


def test_record_writes_heard_reply_and_handler(tmp_path):
    transcript = Transcript(log_dir=tmp_path)

    transcript.record("what time is it", "It's 3:45 PM.", "skill:system")

    (path,) = list(tmp_path.glob("conversation-*.txt"))
    content = path.read_text(encoding="utf-8")

    assert "Heard: what time is it" in content
    assert "Handled by: skill:system" in content
    assert "Lyra: It's 3:45 PM." in content


def test_every_line_carries_a_timestamp(tmp_path):
    transcript = Transcript(log_dir=tmp_path)
    transcript.record("hello", "Hi there.", "chat model")

    (path,) = list(tmp_path.glob("conversation-*.txt"))

    for line in path.read_text(encoding="utf-8").strip().splitlines():
        assert line.startswith("[") and "] " in line


def test_exchanges_are_appended_not_overwritten(tmp_path):
    transcript = Transcript(log_dir=tmp_path)

    transcript.record("one", "First.", "skill:apps")
    transcript.record("two", "Second.", "chat model")

    (path,) = list(tmp_path.glob("conversation-*.txt"))
    content = path.read_text(encoding="utf-8")

    assert "Heard: one" in content
    assert "Heard: two" in content


def test_the_file_is_dated(tmp_path):
    transcript = Transcript(log_dir=tmp_path)

    fixed = datetime.datetime(2026, 9, 29, 10, 0)
    assert transcript.path_for(fixed).name == "conversation-2026-09-29.txt"

    transcript.record("hi", "Hello.", "chat model")
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    assert (tmp_path / f"conversation-{today}.txt").is_file()


def test_the_directory_is_created_when_missing(tmp_path):
    nested = tmp_path / "logs"
    transcript = Transcript(log_dir=nested)

    transcript.record("hi", "Hello.", "chat model")

    assert any(nested.glob("conversation-*.txt"))


def test_multiline_replies_keep_every_line(tmp_path):
    transcript = Transcript(log_dir=tmp_path)
    transcript.record("write a poem", "Roses are red.\nViolets are blue.", "planner")

    (path,) = list(tmp_path.glob("conversation-*.txt"))
    content = path.read_text(encoding="utf-8")

    assert "Lyra: Roses are red." in content
    assert "Lyra: Violets are blue." in content


def test_a_broken_directory_never_raises(tmp_path):
    # A file where the directory should be: mkdir/open will fail.
    blocker = tmp_path / "logs"
    blocker.write_text("in the way", encoding="utf-8")

    transcript = Transcript(log_dir=blocker)
    transcript.record("hi", "Hello.", "chat model")   # must not raise
