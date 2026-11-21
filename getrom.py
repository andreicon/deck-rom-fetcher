#!/usr/bin/env python3
"""GetROM entry point: launches the Qt interface."""

import os
import sys

from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from romfetcher.gui import MainWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.start_pad()
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
