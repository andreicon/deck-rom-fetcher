from romfetcher import resolver


def test_resolver_empty_ambiguous_and_allowlist_hit():
    allow = {"Sample Game (USA)": {"identifier": "ps2-redump-sample",
                                   "filename": "game.chd"}}
    assert resolver.resolve(
        "No Such Game XYZ", "PS2",
        lambda q, s: [], lambda i: [], allow)["status"] == "empty"
    assert resolver.resolve(
        "Sample", "PS2",
        lambda q, s: [{"identifier": "a"}, {"identifier": "b"}],
        lambda i: [], allow)["status"] == "ambiguous"
    ok = resolver.resolve(
        "Sample Game (USA)", "PS2",
        lambda q, s: [{"identifier": "x"}],
        lambda i: [{"name": "game.chd"}], allow)
    assert ok["status"] == "ok" and ok["filename"] == "game.chd"
    multi = resolver.resolve(
        "Other Game", "PS2",
        lambda q, s: [{"identifier": "oid"}],
        lambda i: [{"name": "game.iso", "size": "10"},
                   {"name": "game.chd", "size": "8"},
                   {"name": "game.7z", "size": "6"}], {})
    assert multi["status"] == "need_file_choice"
    assert len(multi["files"]) == 3


def test_resolver_malformed_allowlist_entry_is_safe():
    bad = {"Weird": {"identifier": ""}}
    out = resolver.resolve(
        "Weird", "PS2", lambda q, s: [{"identifier": "x"}],
        lambda i: [{"name": "game.iso"}], bad)
    assert out["status"] in ("ambiguous", "ok", "need_file_choice")


def test_resolve_identifier_single_multi_and_empty():
    allow = {"Game (USA)": {"identifier": "abc", "filename": "g.chd",
                            "sha1": "deadbeef"}}
    one = resolver.resolve_identifier(
        "abc", lambda i: [{"name": "g.chd"}], allow)
    assert one["status"] == "ok" and one["filename"] == "g.chd"
    assert one["sha1"] == "deadbeef"
    many = resolver.resolve_identifier(
        "abc", lambda i: [{"name": "g.iso"}, {"name": "g.chd"}], allow)
    assert many["status"] == "need_file_choice"
    assert len(many["files"]) == 2
    none = resolver.resolve_identifier("abc", lambda i: [], allow)
    assert none["status"] == "empty"


def test_resolve_from_redump_size_autopick():
    entry = {"name": "Some Game (USA)",
             "discs": [{"name": "game.chd", "size": 8, "sha1": "abc"}]}
    out = resolver.resolve_from_redump(
        entry, "PS2",
        lambda q, s: [{"identifier": "abc", "title": "Some Game (USA)"}],
        lambda i: [{"name": "game.iso", "size": "10"},
                   {"name": "game.chd", "size": "8"}],
        {})
    assert out["status"] == "ok" and out["filename"] == "game.chd"
    assert out["sha1"] == "abc"


def test_resolve_from_redump_falls_back_to_unquoted():
    entry = {"name": "Some Game (USA)", "discs": []}
    calls = []

    def fake_search(query, system):
        calls.append(query)
        if query.startswith('"'):
            return []
        return [{"identifier": "abc", "title": "Some Game (USA)"}]

    out = resolver.resolve_from_redump(
        entry, "PS2", fake_search,
        lambda i: [{"name": "game.iso", "size": "10"}], {})
    assert out["status"] == "ok"
    assert len(calls) == 2


def test_resolve_from_redump_ambiguous_and_empty():
    entry = {"name": "Some Game (USA)", "discs": []}
    amb = resolver.resolve_from_redump(
        entry, "PS2",
        lambda q, s: [{"identifier": "a", "title": "Other"},
                      {"identifier": "b", "title": "Else"}],
        lambda i: [], {})
    assert amb["status"] == "ambiguous"
    assert len(amb["candidates"]) == 2
    empty = resolver.resolve_from_redump(
        entry, "PS2", lambda q, s: [], lambda i: [], {})
    assert empty["status"] == "empty"


def test_resolve_identifier_unknown_id_lists_files():
    out = resolver.resolve_identifier(
        "xyz", lambda i: [{"name": "g.iso"}, {"name": "g.chd"}], {})
    assert out["status"] == "need_file_choice"
