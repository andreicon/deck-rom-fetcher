"""Download worker: staged-file reuse, incomplete downloads, success."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from romfetcher import download  # noqa: E402
from romfetcher.worker import DownloadWorker  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def _make_worker(**kw):
    args = {"identifier": "abc", "filename": "game.iso", "title": "T",
            "system": "PS2", "emudeck_dir": "ps2"}
    args.update(kw)
    return DownloadWorker(**args)


def _common(monkeypatch, tmp_path):
    monkeypatch.setattr("os.path.expanduser", lambda p: str(tmp_path))
    monkeypatch.setattr(
        "romfetcher.worker.paths.find_roms_root",
        lambda *a: str(tmp_path / "roms"))
    monkeypatch.setattr(
        "romfetcher.worker.archive.list_files",
        lambda ident: [{"name": "game.iso", "size": "4"}])
    monkeypatch.setattr(
        "romfetcher.worker.archive.download_url",
        lambda ident, name: "http://x/" + name)


def test_exists_error_installs_staged_file(monkeypatch, tmp_path):
    _app()
    _common(monkeypatch, tmp_path)
    staged = tmp_path / ".cache" / "romfetcher" / "abc__game.iso"
    staged.parent.mkdir(parents=True)
    staged.write_bytes(b"DATA")
    installed = {}

    def fake_fetch(url, dest, expected_size=None, progress_cb=None,
                   overwrite=False):
        raise download.ExistsError("staged")

    def fake_install(path, roms_root, emudeck_dir, expected_sha1=None):
        installed["path"] = path
        return str(tmp_path / "roms" / "ps2" / "game.iso")

    monkeypatch.setattr("romfetcher.worker.download.fetch", fake_fetch)
    monkeypatch.setattr("romfetcher.worker.extract.install", fake_install)
    worker = _make_worker()
    done, failed = [], []
    worker.finished.connect(done.append)
    worker.failed.connect(failed.append)
    worker.run()
    assert not failed
    assert done == [str(tmp_path / "roms" / "ps2" / "game.iso")]
    assert installed["path"] == str(staged)


def test_incomplete_error_reports_resume(monkeypatch, tmp_path):
    _app()
    _common(monkeypatch, tmp_path)

    def fake_fetch(url, dest, expected_size=None, progress_cb=None,
                   overwrite=False):
        raise download.IncompleteError("Downloaded 5 of 10 bytes")

    monkeypatch.setattr("romfetcher.worker.download.fetch", fake_fetch)
    worker = _make_worker()
    done, failed = [], []
    worker.finished.connect(done.append)
    worker.failed.connect(failed.append)
    worker.run()
    assert not done
    assert failed and "10 bytes" in failed[0]


def test_success_installs_and_cleans_cache(monkeypatch, tmp_path):
    _app()
    _common(monkeypatch, tmp_path)

    def fake_fetch(url, dest, expected_size=None, progress_cb=None,
                   overwrite=False):
        with open(dest, "wb") as f:
            f.write(b"DATA")
        return dest

    def fake_install(path, roms_root, emudeck_dir, expected_sha1=None):
        return str(tmp_path / "roms" / "ps2" / "game.iso")

    monkeypatch.setattr("romfetcher.worker.download.fetch", fake_fetch)
    monkeypatch.setattr("romfetcher.worker.extract.install", fake_install)
    worker = _make_worker()
    done, failed = [], []
    worker.finished.connect(done.append)
    worker.failed.connect(failed.append)
    worker.run()
    assert not failed
    assert done == [str(tmp_path / "roms" / "ps2" / "game.iso")]
