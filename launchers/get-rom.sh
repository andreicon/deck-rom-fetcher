#!/bin/bash
# GetROM launcher for ES-DE on Steam Deck.
#
# Install: copy the whole project directory to either
#   ~/Emulation/roms/ports/GetROM/      (project root copy)
#     get-rom.sh   (this file, copied from launchers/get-rom.sh)
#     getrom.py
#     romfetcher/
#     config/
#   or the same layout under ~/Emulation/tools/GetROM/.
# Copying get-rom.sh alone is NOT supported.
# In ES-DE set this entry to Suspend (not Keep-running) so the window
# stays usable while it runs.
#
# Graphical app: no terminal is needed or opened. Everything is also
# appended to get-rom.log next to this script for diagnosis.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/getrom.py" ]; then
  ROOT="$SCRIPT_DIR"
else
  # Dev checkout: script lives in launchers/, project root is one level up.
  ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi
LOG="$ROOT/get-rom.log"
{
  echo "=== $(date '+%F %T') get-rom ==="
  exec python3 "$ROOT/getrom.py"
} >>"$LOG" 2>&1
