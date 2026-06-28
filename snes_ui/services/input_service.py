"""Servicio de entrada (simulado).

Modela los dispositivos disponibles, el estado de conexion y el mapa de
asignacion de botones del SNES. No accede a hardware real; la enumeracion y
las pulsaciones se simulan para demostrar la experiencia. Una integracion
real sustituiria la enumeracion y la captura sin cambiar la UI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QKeySequence

from ..state import ConnectionState


# Identificadores logicos de las entradas del SNES (orden de la tabla de la
# especificacion). El id numerico replica el RETRO_DEVICE_ID_JOYPAD del core.
@dataclass(frozen=True)
class SnesInput:
    key: str            # identificador estable
    name: str           # nombre mostrado
    icon: str           # caracter/icono representativo
    retro_id: int       # id libretro del boton


SNES_INPUTS: list[SnesInput] = [
    SnesInput("up", "D-Pad Arriba", "↑", 4),
    SnesInput("down", "D-Pad Abajo", "↓", 5),
    SnesInput("left", "D-Pad Izquierda", "←", 6),
    SnesInput("right", "D-Pad Derecha", "→", 7),
    SnesInput("a", "A", "Ⓐ", 8),
    SnesInput("b", "B", "Ⓑ", 0),
    SnesInput("x", "X", "Ⓧ", 9),
    SnesInput("y", "Y", "Ⓨ", 1),
    SnesInput("select", "Select", "▭", 2),
    SnesInput("start", "Start", "▶", 3),
    SnesInput("l", "L", "⮜", 10),
    SnesInput("r", "R", "⮞", 11),
]

DEFAULT_DEVICES = [
    "Keyboard",
]

# Perfil de teclado por defecto: input_key del SNES -> codigo Qt.Key.
# Replica el MAPEO_TECLADO de poc.py y es la fuente unica de verdad tanto
# para mostrar la asignacion en el panel como para alimentar el nucleo.
DEFAULT_KEYBOARD: dict[str, int] = {
    "up": 0x01000013,      # Qt.Key_Up
    "down": 0x01000015,    # Qt.Key_Down
    "left": 0x01000012,    # Qt.Key_Left
    "right": 0x01000014,   # Qt.Key_Right
    "a": 0x58,             # X
    "b": 0x5A,             # Z
    "x": 0x53,             # S
    "y": 0x41,             # A
    "l": 0x51,             # Q
    "r": 0x57,             # W
    "start": 0x01000004,   # Return
    "select": 0x01000020,  # Shift  (equivalente al RSHIFT de poc.py)
}


# Direcciones de hat empaquetadas (x,y in {-1,0,1}) -> 0..8.
def pack_hat(x: int, y: int) -> int:
    return (x + 1) * 3 + (y + 1)


_HAT_ARROWS = {5: "↑", 3: "↓", 1: "←", 7: "→", 8: "↗", 2: "↘", 0: "↙", 6: "↖"}

# Glifos al estilo de los atajos de macOS para teclas comunes, de modo que la
# cápsula de asignación muestre un símbolo compacto (↑, ↩, ⇧) en vez del nombre
# largo. Las teclas no listadas (letras, F1…) usan su propio nombre.
_KEY_GLYPHS = {
    "Up": "↑", "Down": "↓", "Left": "←", "Right": "→",
    "Return": "↩", "Enter": "↩", "Shift": "⇧", "Ctrl": "⌃",
    "Alt": "⌥", "Meta": "⌘", "Tab": "⇥", "Backspace": "⌫",
    "Space": "Espacio", "Esc": "Esc",
}


@dataclass(frozen=True)
class Binding:
    """Asignacion fisica: tecla o entrada de mando."""
    kind: str          # "key" | "button" | "hat" | "axis"
    code: int
    value: int = 0     # hat: direccion empaquetada; axis: signo (+1/-1)

    def label(self) -> str:
        if self.kind == "key":
            name = QKeySequence(self.code).toString()
            if not name:
                return "Sin asignar"
            return _KEY_GLYPHS.get(name, name)
        if self.kind == "button":
            return f"Botón {self.code}"
        if self.kind == "hat":
            return f"D-Pad {_HAT_ARROWS.get(self.value, '·')}"
        if self.kind == "axis":
            return f"Eje {self.code} {'+' if self.value >= 0 else '−'}"
        return "Sin asignar"

    def to_dict(self) -> dict:
        return {"kind": self.kind, "code": self.code, "value": self.value}

    @classmethod
    def from_dict(cls, d: dict) -> "Binding | None":
        try:
            return cls(str(d["kind"]), int(d["code"]), int(d.get("value", 0)))
        except (KeyError, TypeError, ValueError):
            return None


def key_binding(code: int) -> Binding:
    return Binding("key", code)


KEYBOARD_KEY = "keyboard"


def default_keyboard_profile() -> dict[str, Binding]:
    return {k: key_binding(c) for k, c in DEFAULT_KEYBOARD.items()}


# Layout estandar (estilo Xbox): indices de boton/hat de pygame.
DEFAULT_GAMEPAD: dict[str, Binding] = {
    "b": Binding("button", 0),
    "a": Binding("button", 1),
    "y": Binding("button", 2),
    "x": Binding("button", 3),
    "l": Binding("button", 4),
    "r": Binding("button", 5),
    "select": Binding("button", 6),
    "start": Binding("button", 7),
    "up": Binding("hat", 0, pack_hat(0, 1)),
    "down": Binding("hat", 0, pack_hat(0, -1)),
    "left": Binding("hat", 0, pack_hat(-1, 0)),
    "right": Binding("hat", 0, pack_hat(1, 0)),
}


class MappingProfiles:
    """Perfiles de asignacion por dispositivo (teclado y mandos)."""

    def __init__(self) -> None:
        self._profiles: dict[str, dict[str, Binding]] = {}

    def _defaults(self, *, gamepad: bool) -> dict[str, Binding]:
        return dict(DEFAULT_GAMEPAD) if gamepad else default_keyboard_profile()

    def ensure(self, device_key: str, *, gamepad: bool) -> None:
        if device_key not in self._profiles:
            self._profiles[device_key] = self._defaults(gamepad=gamepad)

    def profile(self, device_key: str) -> dict[str, Binding]:
        return self._profiles.get(device_key, {})

    def binding(self, device_key: str, input_key: str) -> "Binding | None":
        return self._profiles.get(device_key, {}).get(input_key)

    def label_for(self, device_key: str, input_key: str) -> str:
        b = self.binding(device_key, input_key)
        return b.label() if b else "Sin asignar"

    def assign(self, device_key: str, input_key: str, binding: Binding) -> None:
        self._profiles.setdefault(device_key, {})[input_key] = binding

    def reset(self, device_key: str, *, gamepad: bool) -> None:
        self._profiles[device_key] = self._defaults(gamepad=gamepad)

    def input_for_key(self, device_key: str, code: int) -> "str | None":
        for input_key, b in self._profiles.get(device_key, {}).items():
            if b.kind == "key" and b.code == code:
                return input_key
        return None

    def to_json(self) -> str:
        data = {
            dk: {ik: b.to_dict() for ik, b in prof.items()}
            for dk, prof in self._profiles.items()
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, raw: "str | None") -> "MappingProfiles":
        out = cls()
        if not raw:
            return out
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return out
        if not isinstance(data, dict):
            return out
        # Formato heredado (plano): {input_key: int} -> perfil de teclado.
        if data and all(isinstance(v, int) for v in data.values()):
            out._profiles[KEYBOARD_KEY] = {
                ik: key_binding(code) for ik, code in data.items()
            }
            return out
        # Formato anidado por dispositivo.
        for dk, prof in data.items():
            if not isinstance(prof, dict):
                continue
            built: dict[str, Binding] = {}
            for ik, bd in prof.items():
                b = Binding.from_dict(bd) if isinstance(bd, dict) else None
                if b is not None:
                    built[ik] = b
            out._profiles[dk] = built
        return out


class InputService(QObject):
    """Enumeracion de dispositivos y estado de conexion (simulados)."""
    devices_changed = Signal(list)                 # list[str]
    connection_changed = Signal(ConnectionState)

    # input_key -> id libretro del boton, para alimentar el nucleo real.
    RETRO_ID = {i.key: i.retro_id for i in SNES_INPUTS}

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._devices = list(DEFAULT_DEVICES)
        self._current = DEFAULT_DEVICES[0]
        self._state = ConnectionState.CONNECTED
        self._refresh_count = 0

    @property
    def devices(self) -> list[str]:
        return list(self._devices)

    @property
    def current_device(self) -> str:
        return self._current

    @property
    def connection_state(self) -> ConnectionState:
        return self._state

    def set_current_device(self, name: str) -> None:
        # Solo se aceptan dispositivos enumerados; cualquier valor obsoleto
        # (p. ej. un mando persistido en una version anterior) cae al primero.
        if name not in self._devices:
            name = self._devices[0]
        self._current = name
        # El teclado siempre esta conectado; los demas dependen del estado.
        if name == "Keyboard":
            self._set_connection(ConnectionState.CONNECTED)
        else:
            self._set_connection(self._state)

    def _set_connection(self, state: ConnectionState) -> None:
        self._state = state
        self.connection_changed.emit(state)

    def refresh(self) -> None:
        """Re-enumera dispositivos. Simula variacion del estado de conexion."""
        self._refresh_count += 1
        # Alterna el estado de conexion de forma deterministica para demostrar
        # los tres indicadores sin hardware real.
        cycle = self._refresh_count % 3
        if self._current == "Keyboard":
            state = ConnectionState.CONNECTED
        else:
            state = [
                ConnectionState.CONNECTED,
                ConnectionState.RECONNECTING,
                ConnectionState.DISCONNECTED,
            ][cycle]
        self.devices_changed.emit(self.devices)
        self._set_connection(state)

    def retro_id_for(self, input_key: str) -> int | None:
        """Devuelve el id libretro del boton para un input_key del SNES."""
        return self.RETRO_ID.get(input_key)
