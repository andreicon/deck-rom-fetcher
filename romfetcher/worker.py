"""Qt download worker: streams one file, then installs it."""

import os

from PySide6.QtCore import QThread, Signal

from romfetcher import archive, download, extract, paths


class DownloadWorker(QThread):
    progress = Signal(int, int)  # done_bytes, total_bytes (-1 if unknown)
    finished = Signal(str)  # final installed path
    failed = Signal(str)  # human-readable error
    log_line = Signal(str)

    def __init__(self, identifier: str, filename: str, title: str,
                 system: str, emudeck_dir: str, sha1: str | None = None,
                 parent=None):
        super().__init__(parent)
        self.identifier = identifier
        self.filename = filename
        self.title = title
        self.system = system
        self.emudeck_dir = emudeck_dir
        self.sha1 = sha1
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def _emit_progress(self, done: int, total):
        self.progress.emit(done, total if total else -1)

    def run(self):
        try:
            try:
                roms_root = paths.find_roms_root(
                    os.path.expanduser("~"), self._settings_sh(),
                    ["/run/media/*/Emulation/roms",
                     "/media/*/Emulation/roms"])
            except FileNotFoundError as exc:
                self.failed.emit(f"Cannot locate EmuDeck ROMs folder: {exc}")
                return
            files = archive.list_files(self.identifier)
            size = None
            for entry in files:
                if entry.get("name") == self.filename:
                    try:
                        size = int(entry.get("size"))
                    except (TypeError, ValueError):
                        size = None
            if size is None:
                self.log_line.emit("Size unknown — downloading without "
                                   "a pre-check.")
            cache = os.path.join(os.path.expanduser("~"), ".cache",
                                 "romfetcher")
            os.makedirs(cache, exist_ok=True)
            dest = download.cache_path(cache, self.identifier, self.filename)
            url = archive.download_url(self.identifier, self.filename)
            if self._cancel:
                self.failed.emit("Cancelled.")
                return
            try:
                download.fetch(url, dest, expected_size=size,
                               progress_cb=self._emit_progress)
            except download.ExistsError:
                self.log_line.emit("Already staged — installing it.")
            if self._cancel:
                self.failed.emit("Cancelled.")
                return
            final = extract.install(dest, roms_root, self.emudeck_dir,
                                    expected_sha1=self.sha1)
            try:
                os.remove(dest)
            except OSError:
                pass
            self.finished.emit(final)
        except download.SpaceError as exc:
            self.failed.emit(f"Not enough free space: {exc}")
        except download.IncompleteError as exc:
            self.failed.emit(f"{exc}")
        except Exception as exc:  # network, archive, bug: show, don't crash
            self.failed.emit(f"Download failed: {exc} — check network, "
                             "then try again.")

    def _settings_sh(self):
        home = os.path.expanduser("~")
        for cand in (os.path.join(home, ".config", "EmuDeck", "settings.sh"),
                     os.path.join(home, "Emulation", "tools",
                                  "settings.sh")):
            if os.path.isfile(cand):
                return cand
        return None
