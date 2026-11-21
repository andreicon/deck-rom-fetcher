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


def find_gamepads() -> list:
    """Device paths that look like gamepads, best first."""
    if evdev is None:
        return []
    found, others = [], []
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
            name = (dev.name or "").lower()
            caps = dev.capabilities()
        except OSError:
            continue
        keys = caps.get(ecodes.EV_KEY, ())
        has_pad = (ecodes.BTN_A in keys
                   and (ecodes.ABS_HAT0X in caps.get(ecodes.EV_ABS, ())
                        or ecodes.BTN_DPAD_UP in keys))
        if has_pad:
            (found if any(h in name for h in NAME_HINTS) else others
             ).append(path)
    return found + others


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
        self.log_line.emit("Gamepad: waiting for controller…")
        held: dict[str, float] = {}
        next_repeat: dict[str, float] = {}
        dev = None
        while not self._stop:
            if dev is None:
                paths = find_gamepads()
                if not paths:
                    self.msleep(2000)
                    continue
                try:
                    dev = evdev.InputDevice(paths[0])
                    self.log_line.emit(f"Gamepad: {dev.name}")
                except OSError:
                    self.msleep(2000)
                    continue
            try:
                readable, _, _ = select.select([dev.fd], [], [], 0.2)
            except (OSError, ValueError):
                dev = None
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
                dev = None
                held.clear()
