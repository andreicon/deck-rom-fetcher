"""Gamepad mapping and thread lifecycle (no hardware needed)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from romfetcher import gamepad  # noqa: E402
from romfetcher.gamepad import (  # noqa: E402
    action_for_event,
    find_gamepads,
    release_for_event,
)


def _codes():
    from evdev import ecodes
    return ecodes


def test_button_mapping():
    ecodes = _codes()
    assert action_for_event(ecodes.EV_KEY, ecodes.BTN_A, 1) == "confirm"
    assert action_for_event(ecodes.EV_KEY, ecodes.BTN_B, 1) == "back"
    assert action_for_event(ecodes.EV_KEY, ecodes.BTN_A, 0) is None
    assert action_for_event(ecodes.EV_KEY, ecodes.BTN_X, 1) is None


def test_hat_mapping():
    ecodes = _codes()
    assert action_for_event(ecodes.EV_ABS, ecodes.ABS_HAT0Y, -1) == "up"
    assert action_for_event(ecodes.EV_ABS, ecodes.ABS_HAT0Y, 1) == "down"
    assert action_for_event(ecodes.EV_ABS, ecodes.ABS_HAT0X, -1) == "left"
    assert action_for_event(ecodes.EV_ABS, ecodes.ABS_HAT0X, 1) == "right"
    assert action_for_event(ecodes.EV_ABS, ecodes.ABS_HAT0Y, 0) is None


def test_stick_deadzone():
    ecodes = _codes()
    big = gamepad.STICK_DEADZONE + 5000
    assert action_for_event(ecodes.EV_ABS, ecodes.ABS_Y, -big) == "up"
    assert action_for_event(ecodes.EV_ABS, ecodes.ABS_X, big) == "right"
    assert action_for_event(ecodes.EV_ABS, ecodes.ABS_Y, 1000) is None


def test_release_clears_only_neutral_axes():
    ecodes = _codes()
    assert set(release_for_event(
        ecodes.EV_ABS, ecodes.ABS_HAT0Y, 0)) == {"up", "down"}
    assert release_for_event(ecodes.EV_ABS, ecodes.ABS_HAT0Y, 1) == []
    assert release_for_event(ecodes.EV_KEY, ecodes.BTN_A, 0) == []


def test_find_gamepads_prefers_named_pads(monkeypatch):
    from evdev import ecodes

    class FakeDev:
        def __init__(self, name, keys, abs_axes):
            self._name = name
            self._caps = {ecodes.EV_KEY: keys, ecodes.EV_ABS: abs_axes}

        @property
        def name(self):
            return self._name

        def capabilities(self):
            return self._caps

    devs = {
        "/dev/input/event0": FakeDev("AT keyboard", (ecodes.KEY_A,), ()),
        "/dev/input/event1": FakeDev("Microsoft X-Box 360 pad",
                                      (ecodes.BTN_A, ecodes.BTN_B),
                                      (ecodes.ABS_HAT0X, ecodes.ABS_HAT0Y)),
    }
    monkeypatch.setattr(gamepad.evdev, "list_devices",
                        lambda: list(devs))
    monkeypatch.setattr(gamepad.evdev, "InputDevice",
                        lambda path: devs[path])
    assert find_gamepads() == ["/dev/input/event1"]


def test_find_gamepads_empty_without_evdev(monkeypatch):
    monkeypatch.setattr(gamepad, "evdev", None)
    assert find_gamepads() == []


def test_thread_signals_dispatch():
    _app = QApplication.instance() or QApplication([])
    received = []
    t = gamepad.GamepadThread()
    t.up.connect(lambda: received.append("up"))
    t.back.connect(lambda: received.append("back"))
    t._emit("up")
    t._emit("back")
    assert received == ["up", "back"]
    t.deleteLater()


def test_thread_stops_while_waiting_for_device(monkeypatch):
    _app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(gamepad, "find_gamepads", lambda: [])
    t = gamepad.GamepadThread()
    t.start()
    t.stop()
    assert t.wait(5000)
    assert not t.isRunning()
