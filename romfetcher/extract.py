"""Extract outer archives and install playables into roms/<system>/."""

import os
import shutil
import subprocess
import tempfile
import zipfile

from romfetcher.paths import rom_dir_for

PLAYABLE_EXTS = (".iso", ".bin", ".cue", ".chd", ".cso")
SIDECAR_EXTS = (".cue", ".sbi")
SEVEN_Z_MAGIC = bytes.fromhex("37 7A BC AF 27 1C")


def _unique_dest(directory: str, filename: str) -> str:
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(directory, filename)
    n = 0
    while os.path.exists(candidate):
        n += 1
        candidate = os.path.join(directory, f"{base} ({n}){ext}")
    return candidate


def _safe_extract_zip(zip_path: str, tmpdir: str) -> None:
    """Extract guarding against Zip-Slip (absolute / .. / drive members)."""
    with zipfile.ZipFile(zip_path) as zh:
        for member in zh.infolist():
            name = member.filename
            if (not name or os.path.isabs(name) or ".." in name.split("/")
                    or ":" in name
                    or not os.path.realpath(os.path.join(tmpdir, name))
                    .startswith(os.path.realpath(tmpdir))):
                raise ValueError(f"Unsafe archive member: {name!r}")
        zh.extractall(tmpdir)


def _rank_playables(names: list[str]) -> list[str]:
    def rank(n: str) -> tuple:
        low = n.lower()
        if low.endswith(".chd"):
            return (0, low)
        if low.endswith(".iso"):
            return (1, low)
        return (2, low)

    return sorted(names, key=rank)


def install(download_path: str, roms_root: str, emudeck_dir: str,
            run=None, expected_sha1: str | None = None) -> str:
    """Move/extract `download_path` into the ROM dir. Returns final path."""
    run = run or subprocess.run
    dest_dir = rom_dir_for(roms_root, emudeck_dir)
    os.makedirs(dest_dir, exist_ok=True)

    candidates: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        if download_path.lower().endswith(".zip"):
            with open(download_path, "rb") as f:
                if f.read(2) != b"PK":
                    raise ValueError("Not a zip file")
            _safe_extract_zip(download_path, tmp)
            search_root: str | None = tmp
        elif download_path.lower().endswith(".7z"):
            with open(download_path, "rb") as f:
                if f.read(6) != SEVEN_Z_MAGIC:
                    raise ValueError("Not a 7z file")
            proc = run(["7z", "x", download_path, f"-o{tmp}"],
                       capture_output=True)
            if proc.returncode != 0:
                raise RuntimeError("7z is required to extract this file")
            search_root = tmp
        else:
            search_root = None
            candidates = [download_path]

        if search_root is not None:
            for root, _dirs, files in os.walk(search_root):
                for name in files:
                    if name.lower().endswith(PLAYABLE_EXTS):
                        candidates.append(os.path.join(root, name))
            if not candidates:
                raise ValueError("Archive contains no playable file")

        ranked = _rank_playables([os.path.basename(c) for c in candidates])
        by_name = {os.path.basename(c): c for c in candidates}
        first = by_name[ranked[0]]
        final_rel = ranked[0]

        if expected_sha1:
            import hashlib

            digest = hashlib.sha1()
            with open(first, "rb") as f:
                digest.update(f.read())
            if digest.hexdigest() != expected_sha1.lower():
                print(f"Warning: SHA1 mismatch for {final_rel} (continuing).")

        stem = os.path.splitext(first)[0]
        sidecars = [c for c in candidates
                    if os.path.splitext(c)[0] == stem
                    and c.lower().endswith(SIDECAR_EXTS)]
        final_path = None
        for path in [first] + sidecars:
            dest_path = _unique_dest(dest_dir, os.path.basename(path))
            shutil.move(path, dest_path)
            if path == first:
                final_path = dest_path
    return final_path
