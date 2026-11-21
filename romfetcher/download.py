"""Single-file resumable downloader (one connection, polite)."""

import os


class SpaceError(OSError):
    pass


class ExistsError(OSError):
    pass


def _prod_stream(url, headers):
    import httpx

    return httpx.stream("GET", url, headers=headers, timeout=60)


def fetch(url: str, dest: str, expected_size: int | None = None,
          progress_cb=None, http_stream=None, overwrite: bool = False) -> str:
    """Download `url` to `dest` with Range resume. Returns dest path."""
    http_stream = http_stream or _prod_stream
    existing = os.path.getsize(dest) if os.path.isfile(dest) else 0

    if expected_size is not None and not overwrite and existing >= expected_size > 0:
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
    result = http_stream(url, headers)

    if isinstance(result, dict):  # test seam
        status, chunks = result.get("status", 200), result.get("chunks", [])
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
        return dest

    total = expected_size
    if hasattr(result, "headers"):
        content_range = result.headers.get("content-range", "")
        if "/" in content_range:
            try:
                total = int(content_range.rsplit("/", 1)[1])
            except ValueError:
                pass
    with result as r:
        if getattr(r, "status_code", 200) == 200 and existing and not overwrite:
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
    return dest
