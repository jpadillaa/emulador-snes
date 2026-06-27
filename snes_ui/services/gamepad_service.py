"""Servicio de gamepad: lectura de mandos via pygame.joystick.

Las funciones puras de traduccion/captura no dependen de pygame y se prueban
con estados sinteticos. El servicio (clase QObject) se anade en una tarea
posterior.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from PySide6.QtCore import Qt, QObject, QTimer, Signal

from ..state import ConnectionState
from .input_service import Binding, pack_hat

DEADZONE = 0.5


@dataclass(frozen=True)
class PadInfo:
    instance_id: int
    guid: str
    name: str


@dataclass(frozen=True)
class PadState:
    buttons: tuple = ()
    hats: tuple = ()
    axes: tuple = ()


def _binding_active(b: Binding, state: PadState, deadzone: float) -> bool:
    if b.kind == "button":
        return b.code < len(state.buttons) and bool(state.buttons[b.code])
    if b.kind == "hat":
        if b.code < len(state.hats):
            x, y = state.hats[b.code]
            return pack_hat(x, y) == b.value
        return False
    if b.kind == "axis":
        if b.code < len(state.axes):
            v = state.axes[b.code]
            return v >= deadzone if b.value >= 0 else v <= -deadzone
        return False
    return False


def translate(state: PadState, profile: dict, deadzone: float = DEADZONE) -> set:
    pressed = {ik for ik, b in profile.items() if _binding_active(b, state, deadzone)}
    # Stick izquierdo (ejes 0/1) espeja el D-Pad.
    if len(state.axes) >= 2:
        x, y = state.axes[0], state.axes[1]
        if x <= -deadzone:
            pressed.add("left")
        elif x >= deadzone:
            pressed.add("right")
        if y <= -deadzone:
            pressed.add("up")
        elif y >= deadzone:
            pressed.add("down")
    return pressed


def detect_binding(prev: PadState, cur: PadState, deadzone: float = DEADZONE) -> "Binding | None":
    for i in range(len(cur.buttons)):
        was = i < len(prev.buttons) and prev.buttons[i]
        if cur.buttons[i] and not was:
            return Binding("button", i)
    for i in range(len(cur.hats)):
        x, y = cur.hats[i]
        if (x, y) != (0, 0):
            return Binding("hat", i, pack_hat(x, y))
    for i in range(len(cur.axes)):
        v = cur.axes[i]
        pv = prev.axes[i] if i < len(prev.axes) else 0.0
        if abs(v) >= deadzone and abs(pv) < deadzone:
            return Binding("axis", i, 1 if v >= 0 else -1)
    return None


class _PygamePadBackend:
    """Backend real sobre pygame.joystick (hilo principal, video dummy)."""

    def __init__(self) -> None:
        self._pg = None
        self._sticks: dict[int, object] = {}

    def init(self) -> bool:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        try:
            import pygame
            pygame.init()
            pygame.joystick.init()
        except Exception:
            return False
        self._pg = pygame
        return True

    def pump(self) -> None:
        if self._pg is None:
            return
        self._pg.event.pump()
        # Mantener objetos Joystick vivos para lectura.
        count = self._pg.joystick.get_count()
        live: dict[int, object] = {}
        for i in range(count):
            js = self._pg.joystick.Joystick(i)
            try:
                js.init()
            except Exception:
                continue
            live[js.get_instance_id()] = js
        self._sticks = live

    def devices(self) -> list:
        out = []
        for iid, js in self._sticks.items():
            try:
                out.append(PadInfo(iid, js.get_guid(), js.get_name()))
            except Exception:
                continue
        return out

    def read(self, instance_id: int):
        js = self._sticks.get(instance_id)
        if js is None:
            return None
        try:
            buttons = tuple(js.get_button(i) for i in range(js.get_numbuttons()))
            hats = tuple(js.get_hat(i) for i in range(js.get_numhats()))
            axes = tuple(js.get_axis(i) for i in range(js.get_numaxes()))
            return PadState(buttons, hats, axes)
        except Exception:
            return None


class GamepadService(QObject):
    """Detecta mandos, traduce su estado a entradas SNES y captura bindings."""

    devices_changed = Signal(list)
    connection_changed = Signal(object)
    pressed_changed = Signal(set)
    binding_captured = Signal(object)

    def __init__(self, backend=None, parent=None) -> None:
        super().__init__(parent)
        self._backend = backend if backend is not None else _PygamePadBackend()
        self._available = bool(self._backend.init())
        self._devices: list = []
        self._active_iid = None
        self._profile: dict = {}
        self._capture = False
        self._prev_state = None
        self._pressed: set = set()
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self.poll_once)

    @property
    def available(self) -> bool:
        return self._available

    @property
    def devices(self) -> list:
        return list(self._devices)

    def start(self) -> None:
        if self._available:
            self._timer.start(16)

    def stop(self) -> None:
        self._timer.stop()

    def set_active(self, instance_id, profile: dict) -> None:
        self._active_iid = instance_id
        self._profile = profile
        self._prev_state = None
        if self._pressed:
            self._pressed = set()
            self.pressed_changed.emit(set())

    def set_capture(self, enabled: bool) -> None:
        self._capture = enabled
        self._prev_state = None

    def poll_once(self) -> None:
        if not self._available:
            return
        self._backend.pump()
        self._refresh_devices()
        state = self._backend.read(self._active_iid) if self._active_iid is not None else None
        if self._capture:
            self._do_capture(state)
        else:
            self._do_feed(state)

    def _refresh_devices(self) -> None:
        devices = self._backend.devices()
        ids = {d.instance_id for d in devices}
        prev_ids = {d.instance_id for d in self._devices}
        if ids != prev_ids:
            self._devices = devices
            self.devices_changed.emit(list(devices))
            if self._active_iid is not None and self._active_iid not in ids:
                self.connection_changed.emit(ConnectionState.DISCONNECTED)
            elif devices:
                self.connection_changed.emit(ConnectionState.CONNECTED)

    def _do_feed(self, state) -> None:
        pressed = translate(state, self._profile) if state is not None else set()
        if pressed != self._pressed:
            self._pressed = pressed
            self.pressed_changed.emit(set(pressed))

    def _do_capture(self, state) -> None:
        if state is None:
            return
        if self._prev_state is None:
            self._prev_state = state
            return
        b = detect_binding(self._prev_state, state)
        self._prev_state = state
        if b is not None:
            self.binding_captured.emit(b)
