"""Redump title -> Archive.org file resolver with allowlist."""

from collections.abc import Callable
import os

import yaml
_DEFAULT_PLAYABLE = (".iso", ".bin", ".cue", ".chd", ".cso")
_DEFAULT_OUTER = (".zip", ".7z")


def _playable_extensions() -> tuple:
    here = os.path.dirname(os.path.abspath(__file__))
    cfg = os.path.join(os.path.dirname(here), "config", "systems.yaml")
    try:
        with open(cfg, encoding="utf-8") as f:
            systems = yaml.safe_load(f) or {}
        exts: list[str] = []
        for mapping in systems.values():
            exts.extend(mapping.get("extensions", []))
        if exts:
            return tuple(e.lower() for e in exts)
    except (OSError, yaml.YAMLError, AttributeError, KeyError):
        pass
    return _DEFAULT_PLAYABLE


def _is_playable(name: str, playable: tuple) -> bool:
    return name.lower().endswith(playable)


def _size_of(entry: dict) -> int | None:
    try:
        return int(entry.get("size"))
    except (TypeError, ValueError):
        return None


def resolve_from_redump(release: dict, redump_id: str,
                        search_fn: Callable, list_fn: Callable,
                        allowlist: dict | None) -> dict:
    """Redump-first resolution: exact release metadata -> Archive.org.

    Uses the catalog entry's exact title for the archive query (quoted
    first, unquoted exact-match fallback) and its byte sizes to auto-pick
    the right file when several playables exist.
    """
    allowlist = allowlist or {}

    def blank(**kw):
        base = {"status": "", "identifier": None, "filename": None,
                "candidates": [], "files": [], "sha1": None}
        base.update(kw)
        return base

    title = (release.get("name") or "").strip()
    sizes = {d.get("size") for d in release.get("discs", []) if d.get("size")}
    if not title:
        return blank(status="empty")

    hits = search_fn(f'"{title}"', redump_id) or []
    if not hits:
        for hit in search_fn(title, redump_id) or []:
            if ((hit.get("title") or "").strip().casefold()
                    == title.casefold()):
                hits.append(hit)
    if not hits:
        return blank(status="empty")
    if len(hits) > 1:
        exact = [h for h in hits
                 if (h.get("title") or "").strip().casefold()
                 == title.casefold()]
        if len(exact) != 1:
            return blank(status="ambiguous", candidates=hits)
        hits = exact

    identifier = hits[0].get("identifier")
    files = list_fn(identifier) or []
    playable = [f for f in files
                if _is_playable(f.get("name", ""), _playable_extensions())]
    if not playable:
        return blank(status="empty", identifier=identifier, files=files)

    disc_by_name = {d.get("name"): d for d in release.get("discs", [])
                    if d.get("name")}

    def sha1_for(filename: str | None) -> str | None:
        if filename and filename in disc_by_name:
            return disc_by_name[filename].get("sha1") or None
        return None

    if sizes:
        sized = [f for f in playable if _size_of(f) in sizes]
        if len(sized) == 1:
            name = sized[0].get("name")
            return blank(status="ok", identifier=identifier, filename=name,
                         files=files, sha1=sha1_for(name))
    if len(playable) == 1:
        name = playable[0].get("name")
        return blank(status="ok", identifier=identifier, filename=name,
                     files=files, sha1=sha1_for(name))
    return blank(status="need_file_choice", identifier=identifier,
                 files=files)


def resolve_identifier(identifier: str, list_fn: Callable,
                     allowlist: dict | None) -> dict:
    """Resolve a known Archive.org identifier straight to a file.

    Skips the fuzzy title search entirely, so region/revision ambiguity
    cannot happen. Same status vocabulary as resolve().
    """
    allowlist = allowlist or {}

    def blank(**kw):
        base = {"status": "", "identifier": identifier, "filename": None,
                "candidates": [], "files": []}
        base.update(kw)
        return base

    files = list_fn(identifier) or []
    playable = _playable_extensions()
    playables = [f for f in files if _is_playable(f.get("name", ""), playable)]
    sha1 = None
    for entry in allowlist.values():
        if isinstance(entry, dict) and entry.get("identifier") == identifier:
            sha1 = entry.get("sha1")
            break
    if not playables:
        return blank(status="empty", files=files)
    if len(playables) == 1:
        return blank(status="ok", filename=playables[0].get("name"),
                     files=files, sha1=sha1)
    return blank(status="need_file_choice", files=files, sha1=sha1)


def resolve(title_query: str, redump_id: str,
            search_fn: Callable, list_fn: Callable,
            allowlist: dict | None) -> dict:
    """Return {status, identifier, filename, candidates, files}.

    Statuses: ok | empty | ambiguous | need_file_choice. Never auto-picks
    across regions/revisions.
    """
    allowlist = allowlist or {}
    playable = _playable_extensions()

    def blank(**kw):
        base = {"status": "", "identifier": None, "filename": None,
                "candidates": [], "files": []}
        base.update(kw)
        return base

    entry = allowlist.get(title_query)
    if isinstance(entry, dict) and entry.get("identifier"):
        identifier = entry["identifier"]
        files = list_fn(identifier) or []
        wanted = entry.get("filename")
        if wanted and any(f.get("name") == wanted for f in files):
            return blank(status="ok", identifier=identifier,
                         filename=wanted, files=files)
        return blank(status="need_file_choice", identifier=identifier,
                     files=files)

    hits = search_fn(title_query, redump_id) or []
    if not hits:
        return blank(status="empty")
    if len(hits) > 1:
        exact = [h for h in hits
                 if (h.get("title") or "").strip().lower()
                 == title_query.strip().lower()]
        if len(exact) != 1:
            return blank(status="ambiguous", candidates=hits)
        hits = exact
    identifier = hits[0].get("identifier")
    files = list_fn(identifier) or []
    playables = [f for f in files if _is_playable(f.get("name", ""), playable)]
    if len(playables) == 1:
        return blank(status="ok", identifier=identifier,
                     filename=playables[0].get("name"), files=files)
    return blank(status="need_file_choice", identifier=identifier,
                 files=files)
