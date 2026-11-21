"""Gamepad driving for the Deck (D-pad/stick + A/B), via evdev.

Reads Steam Input's virtual Xbox 360 pad (/dev/input/event*). Pure Qt key
events never arrive from the gamepad, so the app drives selection itself:
Up/Down move in the current list, A activates, B goes back.
Touch keeps working untouched. If no pad is readable, the app simply
runs touch-only.
"""

import select
import time

from PySide6.QtCore import QThread, Signal

try:
    import evdev
    from evdev import ecodes
except ImportError:  # dev machines without evdev: touch-only mode
    evdev = None
    ecodes = None

NAME_HINTS = ("x-box", "xbox", "360", "pad", "controller", "joystick",
              "deck", "valve", "steam")
STICK_DEADZONE = 12000
REPEAT_DELAY = 0.45
REPEAT_RATE = 0.09


def _codes(caps: dict, ev_type: int) -> list:
    """Capability codes, tolerating evdev's (code, AbsInfo) ABS tuples."""
    out = []
    for entry in caps.get(ev_type, ()):
        out.append(entry[0] if isinstance(entry, tuple) else entry)
    return out


def find_gamepads() -> list:
    """Device paths that look like gamepads, best first.

    Devices are closed after inspection: this runs in a rescan loop and
    leaking fds would eventually make every open fail.
    """
    if evdev is None:
        return []
    try:
        paths = evdev.list_devices()
    except OSError:
        return []
    found, others = [], []
    for path in paths:
        try:
            dev = evdev.InputDevice(path)
        except OSError:
            continue
        try:
            name = (dev.name or "").lower()
            caps = dev.capabilities()
        except OSError:
            continue
        finally:
            try:
                dev.close()
            except OSError:
                pass
        keys = _codes(caps, ecodes.EV_KEY)
        abs_axes = _codes(caps, ecodes.EV_ABS)
        has_pad = (ecodes.BTN_A in keys
                   and (ecodes.ABS_HAT0X in abs_axes
                        or ecodes.BTN_DPAD_UP in keys))
        if has_pad:
            (found if any(h in name for h in NAME_HINTS) else others
             ).append(path)
    return found + others


def describe_inputs() -> str:
    """One-shot diagnostic of what this process can see (logged on start)."""
    import os as _os
    who = "euid=%d" % _os.geteuid()
    try:
        listing = sorted(_os.listdir("/dev/input"))
    except OSError as exc:
        return "%s; input scan failed: %s" % (who, exc)
    lines = ["%s input-dir=%s" % (who, listing)]
    if evdev is None:
        return "evdev missing; " + lines[0]
    try:
        paths = evdev.list_devices()
    except OSError as exc:
        return "list_devices failed: %s; %s" % (exc, lines[0])
    lines.append("devices=%s" % (paths or "none"))
    for path in paths:
        try:
            dev = evdev.InputDevice(path)
            try:
                lines.append("%s name=%r keys=%d abs=%d" % (
                    path, dev.name,
                    len(dev.capabilities().get(ecodes.EV_KEY, [])),
                    len(dev.capabilities().get(ecodes.EV_ABS, []))))
            finally:
                dev.close()
        except OSError as exc:
            lines.append("%s open-failed: %s" % (path, exc))
    return "; ".join(lines)


def release_for_event(ev_type: int, code: int, value: int) -> list:
    """Held directions to drop for this event (stick/hat back to neutral)."""
    if ecodes is None:
        return []
    if ev_type != ecodes.EV_ABS:
        return []
    if code == ecodes.ABS_HAT0X and value == 0:
        return ["left", "right"]
    if code == ecodes.ABS_HAT0Y and value == 0:
        return ["up", "down"]
    if code == ecodes.ABS_X and abs(value) <= STICK_DEADZONE:
        return ["left", "right"]
    if code == ecodes.ABS_Y and abs(value) <= STICK_DEADZONE:
        return ["up", "down"]
    return []


def action_for_event(ev_type: int, code: int, value: int) -> str | None:
    """Map one evdev event to an action. Edge-triggered (presses only)."""
    if ecodes is None:
        return None
    if ev_type == ecodes.EV_KEY and value == 1:
        if code == ecodes.BTN_A:
            return "confirm"
        if code == ecodes.BTN_B:
            return "back"
    if ev_type == ecodes.EV_ABS:
        if code == ecodes.ABS_HAT0X:
            if value < 0:
                return "left"
            if value > 0:
                return "right"
        elif code == ecodes.ABS_HAT0Y:
            if value < 0:
                return "up"
            if value > 0:
                return "down"
        elif code == ecodes.ABS_X:
            if value < -STICK_DEADZONE:
                return "left"
            if value > STICK_DEADZONE:
                return "right"
        elif code == ecodes.ABS_Y:
            if value < -STICK_DEADZONE:
                return "up"
            if value > STICK_DEADZONE:
                return "down"
    return None


class GamepadThread(QThread):
    up = Signal()
    down = Signal()
    left = Signal()
    right = Signal()
    confirm = Signal()
    back = Signal()
    log_line = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop = False

    def stop(self):
        self._stop = True

    def _emit(self, action: str) -> None:
        {"up": self.up, "down": self.down, "left": self.left,
         "right": self.right, "confirm": self.confirm,
         "back": self.back}[action].emit()

    def run(self) -> None:
        if evdev is None:
            self.log_line.emit("No gamepad support (evdev missing) — "
                               "touch controls only.")
            return
        self.log_line.emit("Gamepad: %s" % describe_inputs())
        held: dict[str, float] = {}
        next_repeat: dict[str, float] = {}
        dev = None
        missing_logged = False
        try:
            while not self._stop:
                if dev is None:
                    paths = find_gamepads()
                    if not paths:
                        if not missing_logged:
                            self.log_line.emit(
                                "Gamepad: none readable yet — touch works, "
                                "retrying…")
                            missing_logged = True
                        self.msleep(500)
                        continue
                    missing_logged = False
                    try:
                        dev = evdev.InputDevice(paths[0])
                        self.log_line.emit(f"Gamepad: {dev.name}")
                    except OSError:
                        self.msleep(500)
                        continue
                try:
                    readable, _, _ = select.select([dev.fd], [], [], 0.2)
                except (OSError, ValueError):
                    dev = self._drop(dev)
                    continue
                now = time.monotonic()
                if not readable:
                    for action, t0 in list(held.items()):
                        if now - t0 >= REPEAT_DELAY and now >= next_repeat.get(
                                action, 0):
                            self._emit(action)
                            next_repeat[action] = now + REPEAT_RATE
                    continue
                try:
                    for event in dev.read():
                        for dropped in release_for_event(
                                event.type, event.code, event.value):
                            held.pop(dropped, None)
                        action = action_for_event(event.type, event.code,
                                                  event.value)
                        if action is None:
                            continue
                        if action in ("up", "down", "left", "right"):
                            held[action] = now
                            next_repeat[action] = now + REPEAT_DELAY
                        self._emit(action)
                except OSError:
                    dev = self._drop(dev)
                    held.clear()
        finally:
            self._drop(dev)

    @staticmethod
    def _drop(dev):
        try:
            if dev is not None:
                dev.close()
        except OSError:
            pass
        return None
