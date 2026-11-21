#!/usr/bin/env python3
"""GetROM entry point: launches the Qt interface."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from romfetcher.gui import run

if __name__ == "__main__":
    sys.exit(run())
