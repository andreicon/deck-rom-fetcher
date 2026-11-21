"""Offscreen smoke tests for the Qt interface (no Deck needed)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from romfetcher import gui  # noqa: E402


def _window():
    app = QApplication.instance() or QApplication([])
    return app, gui.MainWindow()


def test_window_shows_systems():
    _app, window = _window()
    assert window.systems_list.count() >= 1
    assert "PS2" in window.systems_list.item(0).text()


def test_system_choice_moves_to_search():
    _app, window = _window()
    window._on_system_chosen(window.systems_list.item(0))
    assert window.stack.currentIndex() == 1
    assert "PS2" in window.search_title.text()


def test_search_populates_results(monkeypatch):
    _app, window = _window()
    window._on_system_chosen(window.systems_list.item(0))
    monkeypatch.setattr(
        gui.archive, "search_titles",
        lambda q, s: [{"identifier": "abc", "title": "Some Game (USA)"}])
    window.search_box.setText("some game")
    window._on_search()
    assert window.results_list.count() == 1


def test_detail_get_button_disabled_while_downloading(monkeypatch):
    _app, window = _window()
    window.show()  # offscreen: makes child isVisible() meaningful
    window._identifier = "abc"
    window._files = [{"name": "game.chd", "size": "10"}]
    window._redump_id = "PS2"
    window._emudeck_dir = "ps2"
    window._allowlist = {}
    window.stack.setCurrentIndex(2)

    started = {}

    class FakeWorker:
        def __init__(self, *a, **k):
            pass

        def start(self):
            started["yes"] = True

        progress = type("S", (), {"connect": staticmethod(lambda *a: None)})()
        log_line = type("S", (), {"connect": staticmethod(lambda *a: None)})()
        finished = type("S", (), {"connect": staticmethod(lambda *a: None)})()
        failed = type("S", (), {"connect": staticmethod(lambda *a: None)})()

    monkeypatch.setattr(gui, "DownloadWorker", FakeWorker)
    window.file_combo.setVisible(False)
    window._on_get()
    assert started.get("yes") is True
    assert window.progress.isVisible()
    assert not window.get_btn.isEnabled()
