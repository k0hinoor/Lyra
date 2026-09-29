"""
============================================================
 TESTS — lyra/logging_setup.py
============================================================
 The console must stay clean (warnings and errors only) while
 the log file keeps full INFO detail.
============================================================
"""

import logging

import pytest

from lyra.logging_setup import configure_logging


@pytest.fixture
def clean_root():
    """Give each test a handler-free root logger and restore it after."""
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    root.handlers = []
    yield root
    for handler in list(root.handlers):
        handler.close()
    root.handlers = saved_handlers
    root.setLevel(saved_level)


def test_info_stays_out_of_the_console_but_reaches_the_file(clean_root, tmp_path, capfd):
    configure_logging(tmp_path, level="INFO", console_level="WARNING")

    logger = logging.getLogger("lyra.tests.console")
    logger.info("Processing audio with duration 00:02.090")
    logger.warning("Something deserves attention")

    err = capfd.readouterr().err
    assert "Processing audio" not in err
    assert "Something deserves attention" in err

    file_content = (tmp_path / "lyra.log").read_text(encoding="utf-8")
    assert "Processing audio with duration 00:02.090" in file_content
    assert "Something deserves attention" in file_content


def test_errors_are_shown_on_both(clean_root, tmp_path, capfd):
    configure_logging(tmp_path, level="INFO", console_level="WARNING")

    logging.getLogger("lyra.tests.errors").error("Task action open_url returned FAILURE")

    err = capfd.readouterr().err
    assert "Task action open_url returned FAILURE" in err
    assert "Task action open_url returned FAILURE" in (tmp_path / "lyra.log").read_text(
        encoding="utf-8")


def test_debug_console_level_is_possible(clean_root, tmp_path, capfd):
    configure_logging(tmp_path, level="DEBUG", console_level="DEBUG")

    logging.getLogger("lyra.tests.debug").debug("very detailed")

    assert "very detailed" in capfd.readouterr().err


def test_third_party_info_noise_is_hidden(clean_root, tmp_path, capfd):
    configure_logging(tmp_path, level="INFO", console_level="WARNING")

    # faster_whisper / executor style INFO lines
    logging.getLogger("faster_whisper").info(
        "Processing audio with duration 00:02.090")
    logging.getLogger("lyra.actions.executor").info(
        "Task action open_app returned UNKNOWN")

    assert capfd.readouterr().err == ""
