"""GitHub Releases updater with digest verification and rollback-on-error."""

import argparse
import hashlib
import logging
import os
import shutil
import tempfile
import threading
import zipfile
from pathlib import Path, PurePosixPath

import requests

from . import config
from .version import LYRA_VERSION

log = logging.getLogger(__name__)


def _version_tuple(value):
    value = value.strip().lstrip("vV")
    parts = value.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise ValueError(f"Not a stable semantic version: {value!r}")
    return tuple(int(part) for part in parts)


UPDATE_CHECK_TIMEOUT = (3.05, 5)  # (connect, read) seconds
UPDATE_CHECK_DEADLINE = 8.0  # hard wall-clock cap for the whole check


def _fetch_latest_release_json(timeout):
    url = f"https://api.github.com/repos/{config.GITHUB_REPOSITORY}/releases/latest"
    response = requests.get(url, timeout=timeout, headers={"Accept": "application/vnd.github+json"})
    response.raise_for_status()
    return response.json()


def _run_with_deadline(func, deadline, *args):
    """Run func in a daemon thread; raise TimeoutError after `deadline` seconds.

    requests' timeouts don't cover DNS resolution or some proxy stalls, which is
    what makes the check hang on some networks. A daemon thread can be abandoned.
    """
    result = {}

    def target():
        try:
            result["value"] = func(*args)
        except BaseException as exc:  # re-raised in caller thread
            result["error"] = exc

    worker = threading.Thread(target=target, name="lyra-update-check", daemon=True)
    worker.start()
    worker.join(deadline)
    if worker.is_alive():
        raise TimeoutError(f"GitHub update check exceeded {deadline:g}s")
    if "error" in result:
        raise result["error"]
    return result["value"]


def check_latest_release(timeout=UPDATE_CHECK_TIMEOUT, deadline=UPDATE_CHECK_DEADLINE):
    if isinstance(timeout, (int, float)):
        timeout = (min(float(timeout), 3.05), float(timeout))
    release = _run_with_deadline(_fetch_latest_release_json, deadline, timeout)
    tag = release.get("tag_name", "")
    if _version_tuple(tag) <= _version_tuple(LYRA_VERSION):
        return None
    assets = release.get("assets", [])
    archive = next((asset for asset in assets if asset.get("name") == "lyra-app.zip"), None)
    checksum = next((asset for asset in assets if asset.get("name") == "lyra-app.zip.sha256"), None)
    if archive is None or checksum is None:
        raise ValueError("Latest release is missing its app archive or SHA-256 checksum")
    return {
        "version": tag.lstrip("vV"),
        "html_url": release.get("html_url"),
        "archive_url": archive["browser_download_url"],
        "archive_digest": archive.get("digest"),
        "checksum_url": checksum["browser_download_url"],
    }


def download_and_install(release, app_dir=None, data_dir=None, timeout=60):
    """Download, verify, stage, replace files and roll back if any replacement fails."""
    app_dir = Path(app_dir or config.BASE_DIR).resolve()
    data_dir = Path(data_dir or config.DATA_DIR).resolve()
    if app_dir == data_dir or app_dir in data_dir.parents:
        raise ValueError("Application root must not contain the user-data directory")
    app_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lyra-update-") as temporary:
        temp = Path(temporary)
        archive_path = temp / "lyra-app.zip"
        response = requests.get(release["archive_url"], timeout=timeout)
        response.raise_for_status()
        archive_path.write_bytes(response.content)
        digest = hashlib.sha256(response.content).hexdigest()
        expected = release.get("archive_digest")
        if expected:
            expected = expected.removeprefix("sha256:")
        else:
            check = requests.get(release["checksum_url"], timeout=timeout)
            check.raise_for_status()
            expected = check.text.strip().split()[0].lower()
        if digest.lower() != expected.lower():
            raise ValueError("Update archive SHA-256 verification failed")

        stage = temp / "stage"
        stage.mkdir()
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                path = PurePosixPath(member.filename)
                if path.is_absolute() or ".." in path.parts:
                    raise ValueError("Update archive contains an unsafe path")
                if not path.parts or path.parts[0] in {".git", "data", "models", "logs"}:
                    continue
                target = (stage / Path(*path.parts)).resolve()
                if stage.resolve() not in target.parents and target != stage.resolve():
                    raise ValueError("Update archive path escapes staging directory")
            archive.extractall(stage)

        # Support the repository archive's root layout; user files live outside it.
        files = [path for path in stage.rglob("*") if path.is_file()]
        if not files:
            raise ValueError("Update archive contains no application files")
        backup = temp / "backup"
        replaced = []
        staged_files = []
        try:
            for source in files:
                relative = source.relative_to(stage)
                if relative.parts[0] in {".git", "data", "models", "logs"}:
                    continue
                destination = (app_dir / relative).resolve()
                if app_dir not in destination.parents:
                    raise ValueError("Update destination escaped application directory")
                destination.parent.mkdir(parents=True, exist_ok=True)
                old = backup / relative
                if destination.exists():
                    old.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(destination, old)
                incoming = destination.with_name(destination.name + ".lyra-update")
                shutil.copy2(source, incoming)
                staged_files.append(incoming)
                replaced.append((destination, old))
                os.replace(incoming, destination)
        except Exception:
            for destination, old in reversed(replaced):
                if old.exists():
                    shutil.copy2(old, destination)
                else:
                    destination.unlink(missing_ok=True)
            for staged_file in staged_files:
                staged_file.unlink(missing_ok=True)
            raise
    log.info("Updated application files to v%s (user data preserved)", release["version"])


def main():
    parser = argparse.ArgumentParser(description="Check or apply LYRA GitHub Releases")
    parser.add_argument("--check", action="store_true", help="check latest stable release")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    release = check_latest_release()
    if release is None:
        print(f"LYRA is up to date (v{LYRA_VERSION}).")
    else:
        print(f"LYRA update available: v{LYRA_VERSION} → v{release['version']}")
        if args.check and input("Install it now? [y/N] ").strip().casefold() in {"y", "yes"}:
            download_and_install(release)
            print("Update installed. Restart LYRA to use it.")


if __name__ == "__main__":
    main()
