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
python3 -m pip install --user PySide6 httpx pyyaml
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

- Catalog: Redump-derived lists (`data/redump/`) for browsing-grade names.
- Files: Archive.org `advancedsearch` + `metadata` APIs, single
  connection with resume, polite one-file-at-a-time behavior.
- Known-good entries live in `config/allowlist.<system>.json`; anything
  else goes through a disambiguation step — it never silently grabs the
  wrong region.
- Destination is detected from EmuDeck's `settings.sh` (`romsPath`),
  falling back to `~/Emulation/roms` and removable-media globs. No device
  names are hardcoded. PS2 maps to `roms/ps2` (see `config/systems.yaml`).

## Controls

- D-pad / left stick / arrows: move. A / Enter: select. B / Esc: back.
- Touchscreen: tap anything. Search box: focus it, press Steam+X to type.

## Develop / test

```bash
python3 -m pytest tests -q
QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_gui.py -q
```
