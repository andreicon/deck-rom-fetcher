"""Gamepad + touch friendly Qt interface for the Deck (1280x800)."""

import json
import os

from PySide6.QtCore import Qt
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

from romfetcher import archive, resolver, systems
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
        self._worker: DownloadWorker | None = None
        self._build_ui()
        self._load_systems()

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

    def _systems_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("GetROM — pick a system"))
        self.systems_list = QListWidget()
        self.systems_list.itemActivated.connect(self._on_system_chosen)
        layout.addWidget(self.systems_list, 1)
        layout.addWidget(self._hint_label(OWNERSHIP_LINE))
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
        self.results_list.itemActivated.connect(self._on_result_chosen)
        layout.addWidget(self.results_list, 1)
        back = QPushButton("Back")
        back.clicked.connect(self._go_systems)
        layout.addWidget(back)
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
            if self.stack.currentIndex() == 2:
                self._go_search()
            elif self.stack.currentIndex() == 1:
                self._go_systems()
            return
        super().keyPressEvent(event)

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

    def _on_system_chosen(self, item: QListWidgetItem) -> None:
        redump_id = item.text().split("  ")[0]
        self._redump_id = redump_id
        mapping = self._systems.get(redump_id, {})
        self._emudeck_dir = mapping.get("emudeck_dir",
                                        redump_id.lower())
        self._allowlist = _load_allowlist(redump_id)
        self.search_title.setText(f"{redump_id} — search Archive.org")
        self.stack.setCurrentIndex(1)
        self.search_box.setFocus()

    # -- search ------------------------------------------------------------
    def _on_search(self) -> None:
        query = self.search_box.text().strip()
        if not query:
            return
        self.results_list.clear()
        self.status.setText("Searching…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self._hits = archive.search_titles(
                query, getattr(self, "_redump_id", "PS2"))
        except Exception as exc:
            QMessageBox.warning(self, "Search failed",
                                f"{exc} — check your network and try again.")
            return
        finally:
            QApplication.restoreOverrideCursor()
        if not self._hits:
            QListWidgetItem(f'No results for "{query}".', self.results_list)
            return
        for hit in self._hits:
            QListWidgetItem(f"{hit.get('title', '')}\n"
                            f"{hit.get('identifier', '')}",
                            self.results_list)
        self.results_list.setCurrentRow(0)
        self.results_list.setFocus()

    def _on_result_chosen(self, item: QListWidgetItem) -> None:
        row = self.results_list.row(item)
        if row >= len(self._hits):
            return  # the "no results" placeholder row
        hit = self._hits[row]
        self._resolve_title(hit.get("title", ""))

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
        self._identifier = result.get("identifier")
        self._files = result.get("files", []) or []
        self.detail_title.setText(title)
        if status == "need_file_choice":
            self.file_combo.clear()
            for entry in self._files:
                self.file_combo.addItem(
                    f"{entry.get('name', '')}  ({entry.get('size', '?')} bytes)")
            self.file_combo.setVisible(True)
        else:
            self.file_combo.setVisible(False)
        self.progress.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.status.setText("Ready. Tap GET to download.")
        self.stack.setCurrentIndex(2)
        self.get_btn.setFocus()

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
        sha1 = None
        entry = self._allowlist.get(self._title)
        if isinstance(entry, dict):
            sha1 = entry.get("sha1")
        self.get_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # busy until first progress signal
        self.progress.setValue(0)
        self.cancel_btn.setVisible(True)
        self.status.setText(f"Downloading {filename}…")
        self._worker = DownloadWorker(
            self._identifier, filename, self._title,
            getattr(self, "_redump_id", "PS2"), self._emudeck_dir,
            sha1=sha1)
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
