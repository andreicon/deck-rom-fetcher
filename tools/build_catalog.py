#!/usr/bin/env python3
"""Build a local Redump catalog JSON from a Logiqx datfile.

Usage:
    python3 tools/build_catalog.py <datfile.dat> <out.json>

The datfile is public: http://redump.org/datfile/<system>/ (e.g. ps2).
Re-run whenever Redump publishes a newer datfile and ship the JSON.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from romfetcher.redump import parse_datfile


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    catalog = parse_datfile(sys.argv[1])
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False)
    size = os.path.getsize(sys.argv[2])
    print(f"{catalog['meta']['count']} releases, "
          f"dat version {catalog['meta']['version']}, "
          f"{size / 1024 / 1024:.1f} MB -> {sys.argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
