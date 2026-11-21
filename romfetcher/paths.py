"""EmuDeck ROM root detection (no hardcoded device names)."""

import glob
import os
import re
import shutil


def _expand_roms_path(raw: str, home: str) -> str:
    # Deck settings.sh uses split-quote form: "/run/media/deck/XXX"/Emulation
    # so strip ALL quotes, not just outer ones.
    value = raw.strip().replace('"', "").replace("'", "").strip()
    value = value.replace("${HOME}", home).replace("$HOME", home)
    if value == "~" or value.startswith("~/"):
        value = home + value[1:]
    return os.path.expandvars(os.path.expanduser(value))


def _parse_settings_roms_path(settings_sh: str | None, home: str) -> str | None:
    if not settings_sh:
        return None
    try:
        with open(settings_sh, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    match = re.search(
        r'^\s*(?:export\s+)?romsPath\s*=\s*(?P<val>"[^"]*"\S*|\'[^\']*\'\S*|\S+)\s*$',
        text,
        re.MULTILINE,
    )
    if not match:
        return None
    return _expand_roms_path(match.group("val"), home)


def _looks_like_roms_root(root: str) -> bool:
    if os.path.isdir(os.path.join(root, "psx")):
        return True
    if os.path.isdir(os.path.join(root, "ps2")):
        return True
    if os.path.isdir(os.path.join(os.path.dirname(root.rstrip(os.sep)), "bios")):
        return True
    return False


def find_roms_root(home: str, settings_sh: str | None, media_glob: list[str]) -> str:
    """Locate the EmuDeck ROMs root directory."""
    candidates: list[str] = []
    parsed = _parse_settings_roms_path(settings_sh, home)
    if parsed:
        candidates.append(parsed)
    candidates.append(os.path.join(home, "Emulation", "roms"))
    for pattern in media_glob or []:
        candidates.extend(sorted(glob.glob(pattern)))
    for candidate in candidates:
        if os.path.isdir(candidate) and _looks_like_roms_root(candidate):
            return candidate
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    raise FileNotFoundError(f"No EmuDeck ROMs root found (home={home!r})")


def rom_dir_for(roms_root: str, emudeck_dir: str) -> str:
    return os.path.join(roms_root, emudeck_dir)


def free_bytes(path: str) -> int:
    return shutil.disk_usage(path).free
