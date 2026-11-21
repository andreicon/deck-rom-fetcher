from romfetcher import archive


def fake_get_factory():
    def fake_get(url, params=None):
        if "advancedsearch" in url:
            return {"response": {"docs": [
                {"identifier": "ps2-redump-sample",
                 "title": "Sample Game (USA)"}]}}
        return {"metadata": {"identifier": "ps2-redump-sample"},
                "files": [{"name": "game.chd", "size": "1234",
                           "format": "CHD"}]}
    return fake_get


def test_search_and_list_files_with_fake_http():
    fake_get = fake_get_factory()
    hits = archive.search_titles("sample", "PS2", http_get=fake_get)
    assert hits[0]["identifier"] == "ps2-redump-sample"
    files = archive.list_files("ps2-redump-sample", http_get=fake_get)
    assert files[0]["name"] == "game.chd"
    url = archive.download_url("ps2-redump-sample",
                               "My Game (USA).iso")
    assert url == ("https://archive.org/download/ps2-redump-sample/"
                   "My%20Game%20%28USA%29.iso")


def test_search_empty_returns_empty_list():
    def fake_get(url, params=None):
        return {"response": {"docs": []}}

    assert archive.search_titles("no such game xyz", "PS2",
                                 http_get=fake_get) == []


def test_list_files_skips_thumbnails_and_sidecars():
    def fake_get(url, params=None):
        return {"files": [
            {"name": "game.chd", "size": "8"},
            {"name": "__ia_thumb.jpg", "size": "9486"},
            {"name": "game_archive.torrent", "size": "12"},
            {"name": "files.xml", "size": "3"},
        ]}

    names = [f["name"] for f in archive.list_files("x", http_get=fake_get)]
    assert names == ["game.chd"]
