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
