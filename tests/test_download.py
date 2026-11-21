import pytest

from romfetcher import download
from romfetcher.download import ExistsError, SpaceError


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
    assert not issubclass(ExistsError, SpaceError)
