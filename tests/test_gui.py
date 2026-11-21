"""Offscreen smoke tests for the Qt interface (no Deck needed)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QMessageBox,
    QPushButton,
)

import pytest  # noqa: E402

from romfetcher import gui  # noqa: E402


@pytest.fixture(autouse=True)
def no_modal_dialogs(monkeypatch):
    """Never block a test on a modal dialog; record calls instead."""
    calls = []
    for name in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(
            QMessageBox, name,
            staticmethod(lambda *a, **k: calls.append((a, k)) or 0))
    return calls


def _all_buttons(window):
    return window.findChildren(QPushButton)


def test_every_page_has_exit_button():
    _app, window = _window()
    for page in range(window.stack.count()):
        window.stack.setCurrentIndex(page)
        texts = [b.text() for b in window.stack.widget(page).findChildren(QPushButton)]
        assert "Exit" in texts, f"page {page} has no Exit button"


def test_systems_page_has_open_button():
    _app, window = _window()
    texts = [b.text() for b in _all_buttons(window)]
    assert any("Open" in t for t in texts)


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


def test_search_populates_results_from_local_catalog():
    _app, window = _window()
    window._on_system_chosen(window.systems_list.item(0))
    assert len(window._catalog) > 1000
    window.search_box.setText("god of war")
    window._on_search()
    assert 1 <= window.results_list.count() <= 50


def test_result_rows_each_have_install_button(monkeypatch):
    _app, window = _window()
    called = []
    # Patch BEFORE the search: row buttons bind this handler at creation.
    monkeypatch.setattr(
        gui.MainWindow, "_on_install_hit",
        lambda self, hit: called.append(hit["name"]))
    window._on_system_chosen(window.systems_list.item(0))
    window.search_box.setText("tekken tag")
    window._on_search()
    assert window.results_list.count() >= 1
    installs = []
    for row in range(window.results_list.count()):
        widget = window.results_list.itemWidget(
            window.results_list.item(row))
        btns = [b for b in widget.findChildren(QPushButton)
                if b.text() == "Install"]
        assert len(btns) == 1
        installs.append(btns[0])
    installs[0].click()
    assert len(called) == 1 and called[0]


def test_install_hit_single_file_autostarts(monkeypatch):
    _app, window = _window()
    window.show()
    window._on_system_chosen(window.systems_list.item(0))
    monkeypatch.setattr(
        gui.archive, "search_titles",
        lambda q, s: [{"identifier": "abc", "title": "Some Game (USA)"}])
    monkeypatch.setattr(
        gui.archive, "list_files",
        lambda ident: [{"name": "game.chd", "size": "10"}])
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
    window._on_install_hit({"name": "Some Game (USA)", "title": "Some Game",
                            "discs": [{"name": "game.chd", "size": 10,
                                       "sha1": ""}]})
    assert started.get("yes") is True
    assert window.stack.currentIndex() == 2
    assert window.progress.isVisible()


def test_install_hit_many_files_shows_combo_no_autostart(monkeypatch):
    _app, window = _window()
    window.show()
    window._on_system_chosen(window.systems_list.item(0))
    monkeypatch.setattr(
        gui.archive, "search_titles",
        lambda q, s: [{"identifier": "abc", "title": "Some Game (USA)"}])
    monkeypatch.setattr(
        gui.archive, "list_files",
        lambda ident: [{"name": "game.iso", "size": "10"},
                       {"name": "game.chd", "size": "8"}])
    started = {}

    class FakeWorker:
        def __init__(self, *a, **k):
            raise AssertionError("must not autostart with choices pending")

        progress = type("S", (), {"connect": staticmethod(lambda *a: None)})()
        log_line = type("S", (), {"connect": staticmethod(lambda *a: None)})()
        finished = type("S", (), {"connect": staticmethod(lambda *a: None)})()
        failed = type("S", (), {"connect": staticmethod(lambda *a: None)})()

    monkeypatch.setattr(gui, "DownloadWorker", FakeWorker)
    window._on_install_hit({"name": "Some Game (USA)", "title": "Some Game",
                            "discs": []})
    assert window.file_combo.isVisible()
    assert window.file_combo.count() == 2
    assert window.get_btn.isEnabled()
    _app, window = _window()
    window.show()  # offscreen: makes child isVisible() meaningful
    window._identifier = "abc"
    window._files = [{"name": "game.chd", "size": "10"}]
    window._redump_id = "PS2"
    window._emudeck_dir = "ps2"
    window._allowlist = {}
    window._sha1_override = None
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
