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
                 alternates: list | None = None, parent=None):
        super().__init__(parent)
        self.identifier = identifier
        self.filename = filename
        self.title = title
        self.system = system
        self.emudeck_dir = emudeck_dir
        self.sha1 = sha1
        self.alternates = alternates or []
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
            cache = os.path.join(os.path.expanduser("~"), ".cache",
                                 "romfetcher")
            os.makedirs(cache, exist_ok=True)
            attempts = self._build_attempts(cache)
            if not attempts:
                self.failed.emit("Nothing downloadable found.")
                return
            auth_failures = 0
            last_error = "Download failed."
            for att in attempts:
                if self._cancel:
                    self.failed.emit("Cancelled.")
                    return
                url = archive.download_url(att["identifier"],
                                           att["filename"])
                try:
                    try:
                        download.fetch(url, att["dest"],
                                       expected_size=att["size"],
                                       progress_cb=self._emit_progress)
                    except download.ExistsError:
                        self.log_line.emit("Already staged — installing it.")
                    if self._cancel:
                        self.failed.emit("Cancelled.")
                        return
                    final = extract.install(
                        att["dest"], roms_root, self.emudeck_dir,
                        expected_sha1=att["sha1"])
                    try:
                        os.remove(att["dest"])
                    except OSError:
                        pass
                    self.finished.emit(final)
                    return
                except download.AuthRequiredError as exc:
                    auth_failures += 1
                    last_error = str(exc)
                    self.log_line.emit(
                        f"{att['source']} needs a login — trying next source…")
                except download.IncompleteError as exc:
                    last_error = str(exc)
                    self.log_line.emit(
                        f"{att['source']} failed: {exc} — "
                        "trying next source…")
            if auth_failures and auth_failures == len(attempts):
                self.failed.emit(
                    "This release lives in login-restricted archives — "
                    "an Archive.org login isn't supported yet. "
                    "Try another region or version.")
            else:
                self.failed.emit(f"{last_error}")
        except download.SpaceError as exc:
            self.failed.emit(f"Not enough free space: {exc}")
        except Exception as exc:  # network, archive, bug: show, don't crash
            self.failed.emit(f"Download failed: {exc} — check network, "
                             "then try again.")

    def _build_attempts(self, cache: str) -> list:
        """Primary source first, then alternates. Sizes/sha1 travel along."""
        attempts = []
        size = None
        try:
            files = archive.list_files(self.identifier)
        except Exception:
            files = []
        for entry in files:
            if entry.get("name") == self.filename:
                try:
                    size = int(entry.get("size"))
                except (TypeError, ValueError):
                    size = None
        if size is None:
            self.log_line.emit("Size unknown — downloading without "
                               "a pre-check.")
        attempts.append({"identifier": self.identifier,
                         "filename": self.filename,
                         "size": size, "sha1": self.sha1,
                         "source": "primary",
                         "dest": download.cache_path(
                             cache, self.identifier, self.filename)})
        for alt in self.alternates or []:
            attempts.append({
                "identifier": alt.get("identifier"),
                "filename": alt.get("filename"),
                "size": alt.get("size"),
                "sha1": alt.get("sha1"),
                "source": alt.get("source", "mirror"),
                "dest": download.cache_path(
                    cache, alt.get("identifier"), alt.get("filename")),
            })
        return attempts

    def _settings_sh(self):
        home = os.path.expanduser("~")
        for cand in (os.path.join(home, ".config", "EmuDeck", "settings.sh"),
                     os.path.join(home, "Emulation", "tools",
                                  "settings.sh")):
            if os.path.isfile(cand):
                return cand
        return None
