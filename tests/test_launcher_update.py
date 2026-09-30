"""
============================================================
 TESTS — the updater hand-off in lyra/launcher.py
============================================================
 After a release is installed the old modules already loaded
 in memory must not keep running: LYRA re-runs pip install and
 restarts the process.
============================================================
"""

import sys
from pathlib import Path

import pytest

from lyra import launcher


REPO_ROOT = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------
# run_lyra.bat — must work from any working directory
# ------------------------------------------------------------

def test_run_lyra_bat_changes_to_its_own_directory():
    content = (REPO_ROOT / "run_lyra.bat").read_text(encoding="utf-8")
    assert 'cd /d "%LYRA_HOME%"' in content or "cd /d %~dp0" in content


# ------------------------------------------------------------
# DEPENDENCY REFRESH
# ------------------------------------------------------------

def test_install_requirements_runs_pip(monkeypatch, tmp_path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("requests\n", encoding="utf-8")

    commands = []
    monkeypatch.setattr(
        launcher.subprocess, "run",
        lambda command, **kwargs: commands.append(command) or SimpleReturncode(),
    )

    assert launcher.install_requirements(app_dir=tmp_path) is True

    (command,) = commands
    assert command[:3] == [sys.executable, "-m", "pip"]
    assert command[3] == "install"
    assert command[4] == "-r"
    assert command[5] == str(requirements)


class SimpleReturncode:
    returncode = 0


def test_install_requirements_reports_failure(monkeypatch, tmp_path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("requests\n", encoding="utf-8")

    class Failed:
        returncode = 1

    monkeypatch.setattr(launcher.subprocess, "run", lambda command, **kwargs: Failed())

    assert launcher.install_requirements(app_dir=tmp_path) is False


def test_install_requirements_is_a_noop_without_the_file(tmp_path):
    assert launcher.install_requirements(app_dir=tmp_path) is True


# ------------------------------------------------------------
# RESTART
# ------------------------------------------------------------

def test_restart_relaunches_the_launcher_without_an_update_loop(monkeypatch):
    captured = {}

    def fake_execv(executable, args):
        captured["executable"] = executable
        captured["args"] = args
        raise OSError("exec intercepted for the test")

    monkeypatch.setattr(launcher.os, "execv", fake_execv)
    monkeypatch.setattr(launcher.sys, "argv", ["launcher.py", "--text"])

    with pytest.raises(OSError, match="intercepted"):
        launcher.restart_after_update()

    assert captured["executable"] == sys.executable
    assert captured["args"][:3] == [sys.executable, "-m", "lyra.launcher"]
    assert "--no-update-check" in captured["args"]
    assert "--text" in captured["args"]


# ------------------------------------------------------------
# check_for_updates() wiring
# ------------------------------------------------------------

def test_check_for_updates_reports_an_installed_update(monkeypatch):
    installed = []
    monkeypatch.setattr(
        "lyra.updater.check_latest_release",
        lambda timeout=5: {"version": "9.9.9", "archive_url": "x", "checksum_url": "y"},
    )
    monkeypatch.setattr("lyra.updater.download_and_install", installed.append)
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")

    assert launcher.check_for_updates() is True
    assert len(installed) == 1


def test_check_for_updates_is_false_when_up_to_date(monkeypatch):
    monkeypatch.setattr("lyra.updater.check_latest_release", lambda timeout=5: None)
    assert launcher.check_for_updates() is False


def test_check_for_updates_is_false_when_declined(monkeypatch):
    installed = []
    monkeypatch.setattr(
        "lyra.updater.check_latest_release",
        lambda timeout=5: {"version": "9.9.9", "archive_url": "x", "checksum_url": "y"},
    )
    monkeypatch.setattr("lyra.updater.download_and_install", installed.append)
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")

    assert launcher.check_for_updates() is False
    assert installed == []


# ------------------------------------------------------------
# CORE FLAG PASS-THROUGH
# ------------------------------------------------------------

def _run_launcher(monkeypatch, argv):
    """Run the launcher with a stubbed core and return the core's argv."""

    captured = {}
    monkeypatch.setattr(launcher.sys, "argv", argv)
    monkeypatch.setattr(launcher, "check_for_updates", lambda: False)
    monkeypatch.setattr(
        launcher.runpy, "run_path",
        lambda path, run_name=None: captured.setdefault("argv", list(launcher.sys.argv)),
    )
    assert launcher.main() == 0
    return captured["argv"]


def test_launcher_forwards_debug_wake_to_the_core(monkeypatch):
    monkeypatch.setattr(launcher, "ensure_ollama", lambda: True)

    argv = _run_launcher(monkeypatch, ["lyra-launcher", "--debug-wake", "--text"])

    assert argv[0].endswith("main.py")
    assert "--debug-wake" in argv
    assert "--text" in argv                     # unknown core flags still pass through


def test_launcher_forwards_mic_test_without_requiring_ollama(monkeypatch):
    def fail():
        raise AssertionError("--mic-test must not require Ollama")

    monkeypatch.setattr(launcher, "ensure_ollama", fail)

    argv = _run_launcher(monkeypatch, ["lyra-launcher", "--mic-test"])

    assert "--mic-test" in argv
