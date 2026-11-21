"""Archive.org search + metadata client."""

from urllib.parse import quote, quote_plus


def _prod_get(url, params=None):
    import httpx

    return httpx.get(url, params=params, timeout=30).json()


def search_titles(query: str, system: str, http_get=None,
                  collection: str | None = None) -> list:
    """Search Archive.org. `system` is caller-side only (no server filter).

    Pass collection="redump" to scope to the Unofficial Redump Hoard.
    """
    http_get = http_get or _prod_get
    q = f"{quote_plus(query)}+AND+mediatype:software"
    if collection:
        q += f"+AND+collection:{quote_plus(collection)}"
    url = ("https://archive.org/advancedsearch.php"
           f"?q={q}&fl[]=identifier,title&rows=20&page=1&output=json")
    data = http_get(url) or {}
    docs = (data.get("response") or {}).get("docs") or []
    return [
        {"identifier": d.get("identifier"), "title": d.get("title", "")}
        for d in docs
        if d.get("identifier")
    ]


_SIDECARS = ("_meta.sqlite", "_meta.xml", "_files.xml", "_archive.torrent")
_SIDECAR_PREFIXES = ("__ia",)
_SIDECAR_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".torrent", ".sqlite",
                 ".xml", ".txt", ".md5", ".sha1", ".nfo")


def _is_sidecar(name: str) -> bool:
    if name.endswith(_SIDECARS):
        return True
    if name.startswith(_SIDECAR_PREFIXES):
        return True
    return name.lower().endswith(_SIDECAR_EXTS)


def list_files(identifier: str, http_get=None) -> list:
    http_get = http_get or _prod_get
    data = http_get(f"https://archive.org/metadata/{identifier}") or {}
    out = []
    for entry in data.get("files", []) or []:
        name = entry.get("name", "")
        if not name or _is_sidecar(name):
            continue
        out.append(
            {"name": name, "size": entry.get("size", 0),
             "format": entry.get("format", "")}
        )
    return out


def download_url(identifier: str, filename: str) -> str:
    return f"https://archive.org/download/{identifier}/{quote(filename, safe='/')}"
