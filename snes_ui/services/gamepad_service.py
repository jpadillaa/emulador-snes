"""Servicio de gamepad: lectura de mandos via pygame.joystick.

Las funciones puras de traduccion/captura no dependen de pygame y se prueban
con estados sinteticos. El servicio (clase QObject) se anade en una tarea
posterior.
"""
from __future__ import annotations

from dataclasses import dataclass

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
