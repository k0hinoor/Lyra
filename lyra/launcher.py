"""User-facing launcher: checks Ollama/model, optionally updates, then starts core."""

import argparse
import logging
import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

import requests

from . import config
from .logging_setup import configure_logging
from .version import LYRA_VERSION

log = logging.getLogger(__name__)


def ollama_status(timeout=2):
    tags_url = config.OLLAMA_URL.rsplit("/api/", 1)[0] + "/api/tags"
    response = requests.get(tags_url, timeout=timeout)
    response.raise_for_status()
    models = [item.get("name", "") for item in response.json().get("models", [])]
    required = config.OLLAMA_MODEL
    installed = any(name.casefold() == required.casefold() for name in models)
    return installed, models


def _ollama_executable():
    found = shutil.which("ollama")
    if found:
        return found
    candidates = []
    if os.environ.get("LOCALAPPDATA"):
        candidates.append(Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Ollama" / "ollama.exe")
    candidates.append(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Ollama" / "ollama.exe")
    return next((str(path) for path in candidates if path.is_file()), None)


def ensure_ollama():
    ollama_executable = _ollama_executable()

    for attempt in range(2):
        try:
            installed, _models = ollama_status()
            break
        except Exception as exc:
            log.info("Ollama check attempt %s failed: %s", attempt + 1, exc)
            if attempt == 0:
                print("LYRA cannot reach Ollama. Start Ollama, then press Enter to retry (or Ctrl+C to cancel).")
                try:
                    input()
                except (EOFError, KeyboardInterrupt):
                    return False
    else:
        if ollama_executable is None:
            print("Ollama was not found. Install it from https://ollama.com, start it, then launch LYRA again.")
        else:
            print("Ollama is installed but not responding at " + config.OLLAMA_URL.rsplit("/api/", 1)[0])
        return False

    if installed:
        print(f"Ollama is ready. Model available: {config.OLLAMA_MODEL}")
        return True

    print(f"LYRA AI model is not installed: {config.OLLAMA_MODEL}")
    print("This model download is multiple gigabytes and may use several GB of disk space.")
    if ollama_executable is None:
        print("Ollama's command-line tool is unavailable. Install/restart Ollama before model setup.")
        return False
    if input("Download it now with Ollama? [y/N] ").strip().casefold() not in {"y", "yes"}:
        print("Install later with: ollama pull " + config.OLLAMA_MODEL)
        return False
    result = subprocess.run([ollama_executable, "pull", config.OLLAMA_MODEL], check=False)
    if result.returncode:
        print("Model download did not complete. Retry with: ollama pull " + config.OLLAMA_MODEL)
        return False
    return True


def check_for_updates():
    from .updater import check_latest_release, download_and_install
    try:
        release = check_latest_release(timeout=5)
    except Exception as exc:
        log.info("GitHub update check unavailable; continuing offline: %s", exc)
        return
    if release is None:
        return
    print(f"LYRA update available: v{LYRA_VERSION} → v{release['version']}")
    if input("Install update before launching? [y/N] ").strip().casefold() in {"y", "yes"}:
        try:
            download_and_install(release)
            print("Update installed. Launching LYRA with the updated application files.")
        except Exception as exc:
            log.exception("Update failed; current installation was rolled back")
            print(f"Update failed safely: {exc}")


def main():
    parser = argparse.ArgumentParser(description="LYRA desktop launcher")
    parser.add_argument("--no-update-check", action="store_true", help="skip GitHub release check")
    parser.add_argument("--skip-llm-check", action="store_true", help="start core without validating Ollama")
    args, core_args = parser.parse_known_args()
    configure_logging(config.LOG_DIR, config.LOG_LEVEL)
    print(f"LYRA v{LYRA_VERSION}")
    if not args.no_update_check:
        check_for_updates()
    if not args.skip_llm_check and not ensure_ollama():
        return 2
    main_path = config.BASE_DIR / "main.py"
    sys.argv = [str(main_path), *core_args]
    runpy.run_path(str(main_path), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
