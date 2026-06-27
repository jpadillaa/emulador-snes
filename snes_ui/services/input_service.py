"""Servicio de entrada (simulado).

Modela los dispositivos disponibles, el estado de conexion y el mapa de
asignacion de botones del SNES. No accede a hardware real; la enumeracion y
las pulsaciones se simulan para demostrar la experiencia. Una integracion
real sustituiria la enumeracion y la captura sin cambiar la UI.
"""
from __future__ import annotations

from dataclasses import dataclass, field

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


def key_label(code: int | None) -> str:
    """Etiqueta legible para mostrar un codigo de tecla Qt en el panel."""
    if not code:
        return "Sin asignar"
    name = QKeySequence(code).toString()
    return f"Tecla: {name}" if name else "Sin asignar"


@dataclass
class MappingModel:
    """Mapa logico SNES -> codigo de tecla fisica. Restaurable y persistible.

    Es la unica fuente de verdad de las asignaciones: el panel muestra la
    etiqueta derivada del codigo y la ventana resuelve las pulsaciones de
    juego contra este modelo, de modo que reasignar una tecla surte efecto
    inmediato en la emulacion.
    """
    bindings: dict[str, int] = field(default_factory=dict)

    @classmethod
    def defaults(cls) -> "MappingModel":
        return cls(dict(DEFAULT_KEYBOARD))

    def assign(self, input_key: str, code: int) -> None:
        self.bindings[input_key] = code

    def reset(self) -> None:
        self.bindings = dict(DEFAULT_KEYBOARD)

    def code_for(self, input_key: str) -> int | None:
        return self.bindings.get(input_key)

    def label_for(self, input_key: str) -> str:
        return key_label(self.bindings.get(input_key))

    def input_for_code(self, code: int) -> str | None:
        """Entrada SNES asignada a un codigo de tecla fisica (busqueda inversa)."""
        for input_key, bound in self.bindings.items():
            if bound == code:
                return input_key
        return None


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
