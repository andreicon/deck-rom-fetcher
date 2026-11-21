"""Redump catalog parsing and local search."""

import textwrap

from romfetcher import redump


SAMPLE_DAT = textwrap.dedent("""\
    <?xml version="1.0"?>
    <datafile>
      <header><version>2026-01-01</version></header>
      <game name="Sample Game (USA) (v1.0)">
        <category>Games</category>
        <rom name="Sample Game (USA) (v1.0).iso" size="100" crc="a"
             md5="b" sha1="c0ffee"/>
      </game>
      <game name="Sample Game (Europe) (En,Fr,De)">
        <category>Games</category>
        <rom name="Sample Game (Europe) (En,Fr,De).bin" size="200" crc="d"
             md5="e" sha1="f00d"/>
      </game>
    </datafile>
    """)


def _catalog(tmp_path):
    dat = tmp_path / "sample.dat"
    dat.write_text(SAMPLE_DAT, encoding="utf-8")
    return redump.parse_datfile(str(dat))


def test_parse_datfile_extracts_releases(tmp_path):
    catalog = _catalog(tmp_path)
    assert catalog["meta"]["count"] == 2
    usa = catalog["releases"][0]
    assert usa["title"] == "Sample Game"
    assert usa["region"] == "USA"
    assert usa["version"] == "1.0"
    assert usa["discs"][0]["size"] == 100
    assert usa["discs"][0]["sha1"] == "c0ffee"


def test_region_skips_language_groups(tmp_path):
    catalog = _catalog(tmp_path)
    europe = catalog["releases"][1]
    assert europe["region"] == "Europe"
    assert europe["version"] == ""


def test_search_catalog_prefix_first(tmp_path):
    catalog = _catalog(tmp_path)["releases"]
    hits = redump.search_catalog("sample game (e", catalog)
    assert hits[0]["region"] == "Europe"
    assert redump.search_catalog("   ", catalog) == []
    assert len(redump.search_catalog("sample", catalog, limit=1)) == 1
