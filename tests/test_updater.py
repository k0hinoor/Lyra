import hashlib
import io
import zipfile

import pytest

from lyra import updater
from lyra.updater import _version_tuple


def test_semantic_application_versions_compare_numerically():
    assert _version_tuple("v1.10.0") > _version_tuple("v1.9.9")
    assert _version_tuple("0.2.0") < _version_tuple("1.0.0")


@pytest.mark.parametrize("version", ["main", "v1.2", "1.2.3-beta", ""])
def test_unstable_or_malformed_tags_are_rejected(version):
    with pytest.raises(ValueError):
        _version_tuple(version)


def test_failed_update_rolls_back_replaced_files(monkeypatch, tmp_path):
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("main.py", "new main")
        archive.writestr("lyra/core.py", "new core")
    payload = archive_buffer.getvalue()
    digest = hashlib.sha256(payload).hexdigest()

    class Response:
        def __init__(self, content):
            self.content = content
            self.text = content.decode("utf-8", errors="ignore")

        def raise_for_status(self):
            pass

    monkeypatch.setattr(updater.requests, "get", lambda url, **_kwargs: Response(
        payload if url.endswith("app.zip") else f"{digest}  lyra-app.zip\n".encode()
    ))
    app_dir = tmp_path / "app"
    data_dir = tmp_path / "user-data"
    (app_dir / "lyra").mkdir(parents=True)
    (app_dir / "main.py").write_text("old main", encoding="utf-8")
    (app_dir / "lyra" / "core.py").write_text("old core", encoding="utf-8")

    original_replace = updater.os.replace
    failed_once = {"value": False}

    def fail_on_core(incoming, destination):
        if str(destination).endswith("core.py") and not failed_once["value"]:
            failed_once["value"] = True
            raise OSError("simulated disk error")
        return original_replace(incoming, destination)

    monkeypatch.setattr(updater.os, "replace", fail_on_core)
    release = {
        "version": "0.3.0",
        "archive_url": "https://example.invalid/app.zip",
        "archive_digest": "sha256:" + digest,
    }
    with pytest.raises(OSError, match="simulated disk error"):
        updater.download_and_install(release, app_dir=app_dir, data_dir=data_dir)
    assert (app_dir / "main.py").read_text(encoding="utf-8") == "old main"
    assert (app_dir / "lyra" / "core.py").read_text(encoding="utf-8") == "old core"


def test_update_check_fails_fast_when_network_hangs(monkeypatch):
    import time
    import pytest
    from lyra import updater

    monkeypatch.setattr(updater, "_fetch_latest_release_json", lambda timeout: time.sleep(5))
    start = time.monotonic()
    with pytest.raises(TimeoutError):
        updater.check_latest_release(deadline=0.2)
    assert time.monotonic() - start < 2


def test_update_check_uses_connect_read_timeout_tuple(monkeypatch):
    from lyra import updater

    seen = {}

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"tag_name": "v0.0.0"}

    def fake_get(url, timeout, headers):
        seen["timeout"] = timeout
        return Resp()

    monkeypatch.setattr(updater.requests, "get", fake_get)
    assert updater.check_latest_release() is None
    assert isinstance(seen["timeout"], tuple) and len(seen["timeout"]) == 2


def test_launcher_continues_when_update_check_times_out(monkeypatch):
    from lyra import launcher, updater

    def boom(*a, **k):
        raise TimeoutError("slow network")

    monkeypatch.setattr(updater, "check_latest_release", boom)
    assert launcher.check_for_updates() is False
