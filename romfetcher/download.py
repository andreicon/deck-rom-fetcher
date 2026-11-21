"""Single-file resumable downloader (one connection, polite).

Every completed download is verified: error pages are rejected before a
single byte is kept, and the finished size must match the advertised size
(the partial file is kept so a retry resumes instead of restarting).
"""

import os
import re


class SpaceError(OSError):
    pass


class ExistsError(OSError):
    pass


class IncompleteError(OSError):
    """Finished bytes don't match the advertised file. Kept for resume."""


class AuthRequiredError(IncompleteError):
    """Server demands a login (HTTP 401/403). Try another source."""


class _RangeRejected(Exception):
    pass


def cache_path(cache_dir: str, identifier: str, filename: str) -> str:
    """Per-item cache name so different titles never share a staged file."""
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "_", identifier or "item")
    return os.path.join(cache_dir, f"{safe_id}__{os.path.basename(filename)}")


def _is_error_page(content_type: str | None) -> bool:
    return "text/html" in (content_type or "").lower()


def _prod_stream(url, headers):
    import httpx

    return httpx.stream("GET", url, headers=headers, timeout=60)


def fetch(url: str, dest: str, expected_size: int | None = None,
          progress_cb=None, http_stream=None, overwrite: bool = False) -> str:
    """Download `url` to `dest` with Range resume. Returns dest path.

    Raises ExistsError if the complete file is already staged, SpaceError
    if the disk can't hold it, and IncompleteError if what arrived isn't
    the advertised file (error pages, cut connections, wrong size).
    """
    http_stream = http_stream or _prod_stream
    existing = os.path.getsize(dest) if os.path.isfile(dest) else 0

    if (expected_size is not None and not overwrite
            and existing >= expected_size > 0):
        raise ExistsError(f"Already staged (complete): {dest}")

    if expected_size is not None:
        remaining = max(expected_size - existing, 0)
        import shutil

        if shutil.disk_usage(os.path.dirname(os.path.abspath(dest))).free < remaining:
            raise SpaceError(f"Not enough free space for {dest}")

    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)

    headers = {}
    if existing and not overwrite:
        headers["Range"] = f"bytes={existing}-"
    try:
        return _fetch_once(url, dest, expected_size, progress_cb,
                           http_stream, headers, overwrite, existing)
    except _RangeRejected:
        if not headers:
            raise IncompleteError(
                "Server refused the download (HTTP 416).")
        if os.path.isfile(dest):
            os.remove(dest)
        return _fetch_once(url, dest, expected_size, progress_cb,
                           http_stream, {}, True, 0)


def _checked_size(dest: str, expected_size: int | None) -> None:
    if expected_size is None:
        return
    final = os.path.getsize(dest) if os.path.isfile(dest) else 0
    if final != expected_size:
        raise IncompleteError(
            f"Downloaded {final} of {expected_size} bytes — "
            "the file is incomplete. Try again to resume it.")


def _fetch_once(url, dest, expected_size, progress_cb, http_stream,
                headers, overwrite, existing):
    result = http_stream(url, headers)

    if isinstance(result, dict):  # test seam
        status = result.get("status", 200)
        if status == 416:
            raise _RangeRejected()
        if status in (401, 403):
            raise AuthRequiredError(
                "This file needs an Archive.org login — "
                "try another source.")
        content_type = (result.get("headers") or {}).get("content-type", "")
        if _is_error_page(content_type):
            raise IncompleteError(
                "Server returned an error page instead of the file.")
        chunks = result.get("chunks", [])
        total = result.get("total", expected_size)
        mode = "ab" if status == 206 and existing and not overwrite else "wb"
        if mode == "wb":
            existing = 0
        with open(dest, mode) as f:
            for chunk in chunks:
                f.write(chunk)
                existing += len(chunk)
                if progress_cb and total:
                    progress_cb(existing, total)
        _checked_size(dest, expected_size)
        return dest

    total = expected_size
    if hasattr(result, "headers"):
        content_type = result.headers.get("content-type", "")
        if _is_error_page(content_type):
            raise IncompleteError(
                "Server returned an error page instead of the file.")
        content_range = result.headers.get("content-range", "")
        if "/" in content_range:
            try:
                total = int(content_range.rsplit("/", 1)[1])
            except ValueError:
                pass
    with result as r:
        if getattr(r, "status_code", 200) == 416:
            raise _RangeRejected()
        if getattr(r, "status_code", 200) in (401, 403):
            raise AuthRequiredError(
                "This file needs an Archive.org login — "
                "try another source.")
        if (getattr(r, "status_code", 200) == 200 and existing
                and not overwrite):
            existing = 0
            mode = "wb"
        else:
            mode = "ab" if existing and not overwrite else "wb"
            if mode == "wb":
                existing = 0
        with open(dest, mode) as f:
            for chunk in r.iter_bytes(chunk_size=262144):
                f.write(chunk)
                existing += len(chunk)
                if progress_cb and total:
                    progress_cb(existing, total)
    _checked_size(dest, expected_size)
    return dest
