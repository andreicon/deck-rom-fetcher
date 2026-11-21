import os

import pytest

from romfetcher import download
from romfetcher.download import ExistsError, IncompleteError, SpaceError


def test_fetch_resumes_and_blocks_on_exists_and_space(tmp_path):
    dest = str(tmp_path / "game.chd")
    with open(dest, "wb") as f:
        f.write(b"12345")

    def fake_stream(url, headers):
        assert headers.get("Range") == "bytes=5-"
        return {"status": 206, "chunks": [b"67890"], "total": 10}

    out = download.fetch("http://x/game.chd", dest, expected_size=10,
                         http_stream=fake_stream)
    with open(out, "rb") as f:
        assert f.read() == b"1234567890"
    with pytest.raises(ExistsError):
        download.fetch("http://x/game.chd", dest, expected_size=10,
                       http_stream=fake_stream, overwrite=False)
    with pytest.raises(SpaceError):
        download.fetch("http://x/big.chd", str(tmp_path / "big.chd"),
                       expected_size=10 ** 18, http_stream=fake_stream)


def test_errors_are_sibling_oserrors():
    assert issubclass(ExistsError, OSError)
    assert issubclass(SpaceError, OSError)
    assert issubclass(IncompleteError, OSError)
    assert not issubclass(ExistsError, SpaceError)


def test_short_download_raises_and_keeps_partial(tmp_path):
    dest = str(tmp_path / "game.iso")

    def fake_stream(url, headers):
        return {"status": 200, "chunks": [b"12"], "total": 10}

    with pytest.raises(download.IncompleteError):
        download.fetch("http://x/game.iso", dest, expected_size=10,
                       http_stream=fake_stream)
    assert os.path.getsize(dest) == 2  # kept for resume


def test_html_error_page_rejected_before_any_write(tmp_path):
    dest = str(tmp_path / "game.iso")

    def fake_stream(url, headers):
        return {"status": 200,
                "headers": {"content-type": "text/html; charset=utf-8"},
                "chunks": [b"<html>throttled</html>"], "total": 24}

    with pytest.raises(download.IncompleteError):
        download.fetch("http://x/game.iso", dest, expected_size=24,
                       http_stream=fake_stream)
    assert not os.path.exists(dest)


def test_416_restarts_from_scratch(tmp_path):
    dest = str(tmp_path / "game.iso")
    with open(dest, "wb") as f:
        f.write(b"OLD")
    calls = []

    def fake_stream(url, headers):
        calls.append(dict(headers))
        if "Range" in headers:
            return {"status": 416, "chunks": [], "total": 10}
        return {"status": 200, "chunks": [b"0123456789"], "total": 10}

    out = download.fetch("http://x/game.iso", dest, expected_size=10,
                         http_stream=fake_stream)
    with open(out, "rb") as f:
        assert f.read() == b"0123456789"
    assert calls[0].get("Range") == "bytes=3-"
    assert "Range" not in calls[1]


def test_cache_path_namespaces_by_identifier(tmp_path):
    a = download.cache_path(str(tmp_path), "abc-123", "game.iso")
    b = download.cache_path(str(tmp_path), "xyz", "game.iso")
    assert a != b
    assert a.endswith("abc-123__game.iso")
