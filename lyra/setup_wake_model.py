"""Explicit one-time download for Vosk's optional small English wake model."""

import shutil
import tempfile
import zipfile
from pathlib import Path

import requests

from . import config

URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"


def install_model():
    destination = config.WAKE_VOSK_MODEL_DIR
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lyra-vosk-") as directory:
        archive = Path(directory) / "model.zip"
        with requests.get(URL, stream=True, timeout=60) as response:
            response.raise_for_status()
            with archive.open("wb") as output:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        output.write(chunk)
        with zipfile.ZipFile(archive) as zipped:
            root = Path(directory) / "unpacked"
            root.mkdir()
            for member in zipped.infolist():
                path = Path(member.filename)
                if path.is_absolute() or ".." in path.parts:
                    raise ValueError("Wake model archive contains an unsafe path")
            zipped.extractall(root)
            candidates = list(root.glob("vosk-model-small-en-us-0.15"))
            if not candidates or not candidates[0].is_dir():
                raise ValueError("Downloaded archive does not contain the expected Vosk model")
            staged = candidates[0]
            temporary_destination = destination.with_name(destination.name + ".new")
            if temporary_destination.exists():
                shutil.rmtree(temporary_destination)
            shutil.copytree(staged, temporary_destination)
            if destination.exists():
                shutil.rmtree(destination)
            temporary_destination.replace(destination)
    return destination


if __name__ == "__main__":
    print("Downloading Vosk wake model (~40 MB)...")
    print("Installed:", install_model())
    print("Restart LYRA to use lightweight wake detection.")
