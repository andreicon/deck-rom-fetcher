"""Gamepad + touch friendly Qt interface for the Deck (1280x800)."""

import json
import os
from functools import partial

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from romfetcher import archive, redump, resolver, systems
from romfetcher.gamepad import GamepadThread
from romfetcher.worker import DownloadWorker

OWNERSHIP_LINE = ("Only fetch games you own — one file per tap, "
                  "no bulk downloads.")


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_allowlist(redump_id: str) -> dict:
    for base in (os.environ.get("ROMFETCHER_CONFIG"),
                 os.path.join(_repo_root(), "config")):
        if not base:
            continue
        path = (base if base.endswith(".json")
                else os.path.join(base, f"allowlist.{redump_id.lower()}.json"))
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            continue
    return {}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GetROM")
        self.resize(1280, 800)
        self._systems: dict = {}
        self._hits: list = []
        self._files: list = []
        self._identifier: str | None = None
        self._title = ""
        self._sha1_override: str | None = None
        self._alternates: list = []
        self._row_mode = "catalog"
        self._pad = None
        self._worker: DownloadWorker | None = None
        self._build_ui()
        self._load_systems()

    def start_pad(self) -> None:
        """Start gamepad driving (production entry calls this, not tests)."""
        if self._pad is None:
            self._pad = GamepadThread(self)
            self._pad.up.connect(self._on_pad_up)
            self._pad.down.connect(self._on_pad_down)
            self._pad.left.connect(self._on_pad_left)
            self._pad.right.connect(self._on_pad_right)
            self._pad.confirm.connect(self._on_pad_confirm)
            self._pad.back.connect(self._go_back)
            self._pad.log_line.connect(self._on_pad_log)
            self._pad.start()
        app = QApplication.instance()
        if app is not None:
            try:
                app.aboutToQuit.connect(self._cleanup_threads)
            except (RuntimeError, TypeError):
                pass

    def _on_pad_log(self, message: str) -> None:
        print(message, flush=True)
        self._pad_status = message
        if hasattr(self, "_pad_label"):
            self._pad_label.setText(message)

    def _cleanup_threads(self) -> None:
        worker, self._worker = self._worker, None
        try:
            if worker is not None and worker.isRunning():
                worker.cancel()
                worker.wait(5000)
        except RuntimeError:
            pass
        pad, self._pad = self._pad, None
        try:
            if pad is not None and pad.isRunning():
                pad.stop()
                pad.wait(5000)
        except RuntimeError:
            pass

    def closeEvent(self, event) -> None:  # never trap the user in the app
        self._cleanup_threads()
        super().closeEvent(event)

    # -- layout ---------------------------------------------------------
    def _build_ui(self) -> None:
        self.setStyleSheet(
            "QMainWindow, QWidget { font-size: 26px; }"
            "QPushButton { padding: 18px; min-height: 64px; }"
            "QListWidget { font-size: 28px; }"
            "QLineEdit { padding: 14px; font-size: 30px; }"
            "QProgressBar { min-height: 40px; font-size: 24px; }"
            "QLabel#hint { color: palette(mid); font-size: 20px; }"
            "QLabel#status { font-size: 22px; }"
        )
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.stack.addWidget(self._systems_page())
        self.stack.addWidget(self._search_page())
        self.stack.addWidget(self._detail_page())

    def _nav_row(self, *buttons: QPushButton) -> QHBoxLayout:
        nav = QHBoxLayout()
        for button in buttons:
            nav.addWidget(button)
        exit_btn = QPushButton("Exit")
        exit_btn.clicked.connect(QApplication.quit)
        nav.addWidget(exit_btn)
        return nav

    def _systems_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("GetROM — pick a system"))
        self.systems_list = QListWidget()
        self.systems_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff)
        self.systems_list.itemActivated.connect(self._on_system_chosen)
        self.systems_list.itemClicked.connect(self._on_system_chosen)
        layout.addWidget(self.systems_list, 1)
        layout.addWidget(self._hint_label(OWNERSHIP_LINE))
        self._pad_label = QLabel("Gamepad: starting…")
        self._pad_label.setObjectName("hint")
        layout.addWidget(self._pad_label)
        open_btn = QPushButton("Open →")
        open_btn.setMinimumHeight(90)
        open_btn.clicked.connect(self._on_system_open_current)
        layout.addLayout(self._nav_row(open_btn))
        return page

    def _search_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.search_title = QLabel("Search")
        layout.addWidget(self.search_title)
        row = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Game title…")
        self.search_box.returnPressed.connect(self._on_search)
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self._on_search)
        row.addWidget(self.search_box, 1)
        row.addWidget(self.search_btn)
        layout.addLayout(row)
        layout.addWidget(self._hint_label(
            "Steam+X opens the keyboard. D-pad moves, A selects, B goes back."))
        self.results_list = QListWidget()
        self.results_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff)
        self.results_list.itemActivated.connect(self._on_result_chosen)
        self.results_list.itemClicked.connect(self._on_result_chosen)
        layout.addWidget(self.results_list, 1)
        back = QPushButton("Back")
        back.clicked.connect(self._go_systems)
        layout.addLayout(self._nav_row(back))
        return page

    def _detail_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.detail_title = QLabel("")
        self.detail_title.setWordWrap(True)
        layout.addWidget(self.detail_title)
        self.file_combo = QComboBox()
        self.file_combo.setVisible(False)
        layout.addWidget(self.file_combo)
        self.get_btn = QPushButton("⬇ GET")
        self.get_btn.setMinimumHeight(110)
        self.get_btn.setStyleSheet("font-size: 40px; font-weight: bold;")
        self.get_btn.clicked.connect(self._on_get)
        layout.addWidget(self.get_btn)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.status = QLabel("")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        layout.addWidget(self.status, 1)
        nav = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        back = QPushButton("Back")
        back.clicked.connect(self._go_search)
        nav.addWidget(self.cancel_btn)
        nav.addWidget(back)
        exit_btn = QPushButton("Exit")
        exit_btn.clicked.connect(QApplication.quit)
        nav.addWidget(exit_btn)
        layout.addLayout(nav)
        return page

    @staticmethod
    def _hint_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("hint")
        label.setWordWrap(True)
        return label

    # -- navigation ------------------------------------------------------
    def keyPressEvent(self, event) -> None:  # B button / Esc goes back
        if event.key() == Qt.Key_Escape:
            self._go_back()
            return
        super().keyPressEvent(event)

    def _go_back(self) -> None:
        if self.stack.currentIndex() == 2:
            self._go_search()
        elif self.stack.currentIndex() == 1:
            self._go_systems()

    def _current_list(self) -> QListWidget | None:
        if self.stack.currentIndex() == 0:
            return self.systems_list
        if self.stack.currentIndex() == 1:
            return self.results_list
        return None

    def _move_selection(self, delta: int) -> None:
        if (self.stack.currentIndex() == 2
                and self.file_combo.isVisible()):
            idx = self.file_combo.currentIndex()
            self.file_combo.setCurrentIndex(
                max(0, min(self.file_combo.count() - 1, idx + delta)))
            return
        lst = self._current_list()
        if lst is None or lst.count() == 0:
            return
        row = lst.currentRow()
        if row < 0:
            row = 0 if delta > 0 else lst.count() - 1
        else:
            row = (row + delta) % lst.count()
        lst.setCurrentRow(row)
        lst.scrollToItem(lst.item(row))

    def _on_pad_up(self) -> None:
        self._move_selection(-1)

    def _on_pad_down(self) -> None:
        self._move_selection(1)

    def _on_pad_left(self) -> None:
        self._move_selection(-5)

    def _on_pad_right(self) -> None:
        self._move_selection(5)

    def _on_pad_confirm(self) -> None:
        focused = QApplication.focusWidget()
        if isinstance(focused, QPushButton):
            focused.click()
            return
        if isinstance(focused, QLineEdit):
            self._on_search()
            return
        lst = self._current_list()
        if lst is not None:
            item = lst.currentItem()
            if item is not None:
                if lst is self.systems_list:
                    self._on_system_chosen(item)
                else:
                    self._on_result_chosen(item)
        elif self.stack.currentIndex() == 2:
            self.get_btn.click()

    def _go_systems(self) -> None:
        self._stop_worker()
        self.stack.setCurrentIndex(0)
        self.systems_list.setFocus()

    def _go_search(self) -> None:
        self._stop_worker()
        self.stack.setCurrentIndex(1)
        self.results_list.setFocus()

    # -- systems ----------------------------------------------------------
    def _load_systems(self) -> None:
        cfg = os.path.join(_repo_root(), "config", "systems.yaml")
        try:
            self._systems = systems.load_systems(cfg) or {}
        except Exception as exc:  # bad config must not kill the UI
            QMessageBox.warning(self, "Config problem",
                                f"Cannot load systems.yaml: {exc}")
            self._systems = {}
        for redump_id, mapping in self._systems.items():
            QListWidgetItem(
                f"{redump_id}  →  roms/{mapping.get('emudeck_dir', '')}",
                self.systems_list)
        if self.systems_list.count():
            self.systems_list.setCurrentRow(0)
            self.systems_list.setFocus()

    def _on_system_open_current(self) -> None:
        item = self.systems_list.currentItem()
        if item is not None:
            self._on_system_chosen(item)

    def _on_system_chosen(self, item: QListWidgetItem) -> None:
        redump_id = item.text().split("  ")[0]
        self._redump_id = redump_id
        mapping = self._systems.get(redump_id, {})
        self._emudeck_dir = mapping.get("emudeck_dir",
                                        redump_id.lower())
        self._allowlist = _load_allowlist(redump_id)
        self._catalog = self._load_catalog(redump_id)
        count = len(self._catalog)
        self.search_title.setText(
            f"{redump_id} — {count} releases (Redump catalog, on-device)")
        self.stack.setCurrentIndex(1)
        self.search_box.setFocus()

    @staticmethod
    def _load_catalog(redump_id: str) -> list:
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(os.path.dirname(here), "data", "redump",
                            f"{redump_id.lower()}.json")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            releases = data.get("releases", [])
            return releases if isinstance(releases, list) else []
        except (OSError, ValueError):
            return []

    # -- search ------------------------------------------------------------
    def _row_label(self, hit: dict) -> str:
        if "discs" in hit:  # Redump catalog entry
            meta = " • ".join(p for p in (hit.get("region", ""),
                                          ("v" + hit["version"]
                                           if hit.get("version") else ""))
                              if p)
            return f"{hit.get('name', '')}\n{meta}"
        return f"{hit.get('title', '')}\n{hit.get('identifier', '')}"

    def _fill_results(self, hits: list, mode: str) -> None:
        self._row_mode = mode
        self._hits = hits
        self.results_list.clear()
        for hit in hits:
            item = QListWidgetItem(self.results_list)
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(12, 8, 12, 8)
            label = QLabel(self._row_label(hit))
            label.setWordWrap(True)
            install = QPushButton("Install")
            install.setMinimumHeight(90)
            install.setMinimumWidth(220)
            install.clicked.connect(partial(self._on_row_install, hit))
            layout.addWidget(label, 1)
            layout.addWidget(install)
            # Bounded width: long titles must wrap, never stretch the UI.
            item.setSizeHint(
                QSize(10, max(row.sizeHint().height(), 110)))
            self.results_list.setItemWidget(item, row)
        if hits:
            self.results_list.setCurrentRow(0)
        self.results_list.setFocus()

    def _show_archive_candidates(self, candidates: list) -> None:
        """Several Archive.org items matched: let the user pick one."""
        self.search_title.setText("Archive.org matches — pick one")
        self._fill_results(candidates, mode="archive")

    def _on_search(self) -> None:
        query = self.search_box.text().strip()
        if not query:
            return
        # Redump first: instant local search, no network involved.
        hits = redump.search_catalog(query, getattr(self, "_catalog", []))
        if not hits:
            self._row_mode = "catalog"
            self._hits = []
            self.results_list.clear()
            QListWidgetItem(f'No releases matching "{query}".', self.results_list)
            return
        self._fill_results(hits, mode="catalog")

    def _on_result_chosen(self, item: QListWidgetItem) -> None:
        row = self.results_list.row(item)
        if row >= len(self._hits):
            return  # the "no results" placeholder row
        hit = self._hits[row]
        if self._row_mode == "archive":
            self._open_identifier_detail(hit)
        else:
            self._resolve_title(hit.get("title", ""))

    def _on_row_install(self, hit: dict) -> None:
        if "discs" in hit:
            self._on_install_hit(hit)
        else:
            self._on_install_identifier(hit, autostart=True)

    def _open_identifier_detail(self, hit: dict) -> None:
        """Tap on an Archive.org candidate row: show it, don't download."""
        try:
            result = resolver.resolve_identifier(
                hit.get("identifier", ""), archive.list_files,
                self._allowlist)
        except Exception as exc:
            QMessageBox.warning(self, "Could not resolve",
                                f"{exc} — check your network and try again.")
            return
        if result.get("status") == "empty":
            QMessageBox.information(
                self, "Nothing playable",
                f'"{hit.get("title", "")}" has no playable file.')
            return
        self._show_detail(hit.get("title", ""), result.get("identifier"),
                          result.get("files", []) or [],
                          result.get("status", ""), result.get("sha1"),
                          autostart=False)

    def _on_install_identifier(self, hit: dict, autostart: bool = True) -> None:
        """Install button on an Archive.org candidate row."""
        try:
            result = resolver.resolve_identifier(
                hit.get("identifier", ""), archive.list_files,
                self._allowlist)
        except Exception as exc:
            QMessageBox.warning(self, "Could not resolve",
                                f"{exc} — check your network and try again.")
            return
        if result.get("status") == "empty":
            QMessageBox.information(
                self, "Nothing playable",
                f'"{hit.get("title", "")}" has no playable file.')
            return
        self._show_detail(hit.get("title", ""), result.get("identifier"),
                          result.get("files", []) or [],
                          result.get("status", ""), result.get("sha1"),
                          autostart=(autostart
                                     and result.get("status") == "ok"))

    def _on_install_hit(self, hit: dict) -> None:
        """Install button on a search row: Redump metadata -> Archive.org."""
        try:
            result = resolver.resolve_from_redump(
                hit, getattr(self, "_redump_id", "PS2"),
                archive.search_titles, archive.list_files, self._allowlist)
        except Exception as exc:
            QMessageBox.warning(self, "Could not resolve",
                                f"{exc} — check your network and try again.")
            return
        if result.get("status") == "empty":
            QMessageBox.information(
                self, "Not on Archive.org",
                f'No Archive.org item found for\n"{hit.get("name", "")}".\n'
                "Try a different region or version.")
            return
        if result.get("status") == "ambiguous":
            self._show_archive_candidates(result.get("candidates", []))
            return
        self._show_detail(hit.get("name", ""), result.get("identifier"),
                          result.get("files", []) or [],
                          result.get("status", ""), result.get("sha1"),
                          autostart=(result.get("status") == "ok"),
                          alternates=result.get("alternates"))

    def _show_detail(self, title: str, identifier: str | None,
                     files: list, status: str, sha1: str | None,
                     autostart: bool, alternates: list | None = None) -> None:
        self._title = title
        self._identifier = identifier
        self._files = files
        self._sha1_override = sha1
        self._alternates = alternates or []
        self.detail_title.setText(title)
        if status == "need_file_choice":
            self.file_combo.clear()
            for entry in files:
                self.file_combo.addItem(
                    f"{entry.get('name', '')}  ({entry.get('size', '?')} bytes)")
            self.file_combo.setVisible(True)
        else:
            self.file_combo.setVisible(False)
        self.progress.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.get_btn.setEnabled(True)
        self.status.setText("Ready. Tap GET to download.")
        self.stack.setCurrentIndex(2)
        self.get_btn.setFocus()
        if autostart and status == "ok":
            self._on_get()

    def _resolve_title(self, title: str) -> None:
        self._title = title
        try:
            result = resolver.resolve(
                title, getattr(self, "_redump_id", "PS2"),
                archive.search_titles, archive.list_files, self._allowlist)
        except Exception as exc:
            QMessageBox.warning(self, "Could not resolve",
                                f"{exc} — check your network and try again.")
            return
        status = result.get("status")
        if status == "empty":
            QMessageBox.information(self, "No match",
                                    f'Nothing downloadable for "{title}".')
            return
        if status == "ambiguous":
            lines = "\n".join(
                f"• {c.get('title', '')}" for c in result.get("candidates", [])
                [:8])
            QMessageBox.information(
                self, "Too many matches",
                f'"{title}" matches several items — pick the exact one:\n'
                f"{lines}")
            return
        self._show_detail(title, result.get("identifier"),
                          result.get("files", []) or [], status or "",
                          None, autostart=False)

    # -- download -----------------------------------------------------------
    def _on_get(self) -> None:
        if self.file_combo.isVisible():
            filename = self._files[self.file_combo.currentIndex()].get("name")
        else:
            filename = next(
                (f.get("name") for f in self._files
                 if f.get("name", "").lower().endswith(
                     (".iso", ".bin", ".cue", ".chd", ".cso"))),
                (self._files[0].get("name") if self._files else None))
        if not filename:
            QMessageBox.warning(self, "Nothing to fetch",
                                "This item has no downloadable file.")
            return
        sha1 = self._sha1_override
        if sha1 is None:
            entry = self._allowlist.get(self._title)
            if isinstance(entry, dict):
                sha1 = entry.get("sha1")
        self._stop_worker()  # never run two downloads at once
        self.get_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # busy until first progress signal
        self.progress.setValue(0)
        self.cancel_btn.setVisible(True)
        self.status.setText(f"Downloading {filename}…")
        self._worker = DownloadWorker(
            self._identifier, filename, self._title,
            getattr(self, "_redump_id", "PS2"), self._emudeck_dir,
            sha1=sha1, alternates=self._alternates)
        self._worker.progress.connect(self._on_progress)
        self._worker.log_line.connect(self.status.setText)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, done: int, total: int) -> None:
        if total and total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(done)
            pct = (done * 100) // total
            self.status.setText(f"{done}/{total} bytes ({pct}%)")
        else:
            self.progress.setRange(0, 0)
            self.status.setText(f"{done} bytes…")

    def _on_finished(self, final: str) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.cancel_btn.setVisible(False)
        self.get_btn.setEnabled(True)
        self.status.setText(f"Installed:\n{final}\nRescan ES-DE if needed.")
        QMessageBox.information(self, "Done", f"Installed:\n{final}")

    def _on_failed(self, message: str) -> None:
        self.progress.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.get_btn.setEnabled(True)
        self.status.setText(message)
        QMessageBox.warning(self, "Fetch failed", message)

    def _on_cancel(self) -> None:
        self._stop_worker()
        self.status.setText("Cancelled.")

    def _stop_worker(self) -> None:
        worker, self._worker = self._worker, None
        if worker is not None and worker.isRunning():
            worker.cancel()
            worker.wait(5000)
        self.cancel_btn.setVisible(False)
        self.get_btn.setEnabled(True)


def run() -> int:
    import sys

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()
    return app.exec()
