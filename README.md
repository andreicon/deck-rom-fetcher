# GetROM — graphical ROM fetcher for Steam Deck

A big-button Qt app that runs on the Deck: pick a system, search
Archive.org, tap **GET**, and the game downloads, extracts, and lands in
the right EmuDeck ROM folder. No terminal, no typing commands — D-pad +
A to move and select, B to go back, touchscreen works everywhere, and
Steam+X brings up the keyboard for the search box.

Only fetch games you already own. One file per tap, no bulk downloads,
no BIOS files (ES-DE handles those).

## Run on the Deck

Requires Python 3.10+ with `PySide6`, `httpx`, `pyyaml` (one time):

```bash
python3 -m pip install --user PySide6 httpx pyyaml evdev pytest
```

Copy this whole folder to the SD card (or internal storage):

```bash
Emulation/roms/ports/GetROM/
  get-rom.sh   (from launchers/get-rom.sh)
  getrom.py
  romfetcher/
  config/
  data/
```

Then open ES-DE → Ports → GetROM. Set the entry to **Suspend** (not
Keep-running) so the window stays usable. Every run is appended to
`GetROM/get-rom.log`.

## How it works

- Redump first: the search box searches a local Redump catalog
  (`data/redump/ps2.json`, 11,774 PS2 releases with region, version,
  file sizes, and hashes) — instant, no network, exact release names.
- Files second: Install uses the entry's exact title against Archive.org
  `advancedsearch` + `metadata` APIs, and matches byte sizes from the
  datfile to auto-pick the right file when several playables exist.
- Single connection with resume, polite one-file-at-a-time behavior.
- Known-good entries live in `config/allowlist.<system>.json`; anything
  else goes through a disambiguation step — it never silently grabs the
  wrong region.

To refresh the catalog when Redump publishes a newer datfile:

```bash
python3 tools/build_catalog.py <downloaded.dat> data/redump/ps2.json
```

Datfiles are public at http://redump.org/datfile/<system>/ (e.g. ps2).
- Destination is detected from EmuDeck's `settings.sh` (`romsPath`),
  falling back to `~/Emulation/roms` and removable-media globs. No device
  names are hardcoded. PS2 maps to `roms/ps2` (see `config/systems.yaml`).

## Controls

- D-pad / left stick / arrows: move. A / Enter: select. B / Esc: back.
- Touchscreen: tap anything. Search box: focus it, press Steam+X to type.
- Every screen has Back and Exit buttons; lists respond to a single tap.

The gamepad is read directly from the Deck's controls on-device, so no
Steam Input remapping is needed. If no gamepad is readable, everything
still works by touch.

## Develop / test

```bash
python3 -m pytest tests -q
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_gui.py -q
```
