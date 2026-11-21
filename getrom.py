#!/usr/bin/env python3
"""GetROM entry point: launches the Qt interface."""

import os
import sys

from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from romfetcher.gui import MainWindow


def main() -> int:
    from PySide6 import QtCore

    print(f"GetROM starting (Qt {QtCore.qVersion()}, "
          f"platform {os.environ.get('QT_QPA_PLATFORM', 'default')})",
          flush=True)
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.start_pad()
    window.showFullScreen()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
