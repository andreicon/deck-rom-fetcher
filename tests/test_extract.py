import zipfile

import pytest

from romfetcher import extract


def _make_zip(path, inner_name=b"game.iso", data=b"ISO!"):
    with zipfile.ZipFile(path, "w") as zh:
        zh.writestr(inner_name.decode() if isinstance(inner_name, bytes)
                    else inner_name, data)


def test_install_extracts_zip_and_moves_iso(tmp_path):
    zipped = tmp_path / "game.zip"
    _make_zip(str(zipped))
    roms = tmp_path / "roms" / "ps2"
    roms.mkdir(parents=True)
    out = extract.install(str(zipped), str(tmp_path / "roms"), "ps2")
    assert out.endswith("game.iso")
    with open(out, "rb") as f:
        assert f.read() == b"ISO!"


def test_install_prefers_chd(tmp_path):
    zipped = tmp_path / "multi.zip"
    with zipfile.ZipFile(str(zipped), "w") as zh:
        zh.writestr("game.iso", b"ISO")
        zh.writestr("game.chd", b"CHD")
    roms = tmp_path / "roms" / "ps2"
    roms.mkdir(parents=True)
    out = extract.install(str(zipped), str(tmp_path / "roms"), "ps2")
    assert out.endswith("game.chd")


def test_install_rejects_zip_slip(tmp_path):
    zipped = tmp_path / "evil.zip"
    with zipfile.ZipFile(str(zipped), "w") as zh:
        zh.writestr("../../evil.iso", b"X")
    roms = tmp_path / "roms" / "ps2"
    roms.mkdir(parents=True)
    with pytest.raises(ValueError):
        extract.install(str(zipped), str(tmp_path / "roms"), "ps2")


def test_install_never_overwrites(tmp_path):
    first = tmp_path / "roms" / "ps2"
    first.mkdir(parents=True)
    (first / "game.iso").write_bytes(b"OLD")
    src = tmp_path / "game.iso"
    src.write_bytes(b"NEW")
    out = extract.install(str(src), str(tmp_path / "roms"), "ps2")
    assert out.endswith("game (1).iso")
    assert (first / "game.iso").read_bytes() == b"OLD"
