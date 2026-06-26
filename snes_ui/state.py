"""Enumeraciones de estado compartidas por toda la aplicacion."""
from __future__ import annotations

from enum import Enum, auto


class SessionState(Enum):
    """Las cinco vistas que expone el QStackedWidget del escenario.

    La pantalla completa es un modo de presentacion que se superpone a
    cualquiera de estas y por tanto no es un estado de sesion.
    """
    EMPTY = auto()
    LOADING = auto()
    RUNNING = auto()
    PAUSED = auto()
    ERROR = auto()


class ScaleMode(Enum):
    """Modos de visualizacion del escenario."""
    FIT_WINDOW = "fit"        # ajuste a ventana (4:3 con letterboxing) - por defecto
    INTEGER = "integer"       # escalado entero
    ORIGINAL = "original"     # relacion de pixel 8:7
    STRETCH = "stretch"       # estirar ignorando relacion de aspecto

    @property
    def label(self) -> str:
        return {
            ScaleMode.FIT_WINDOW: "Ajuste a ventana",
            ScaleMode.INTEGER: "Escalado entero",
            ScaleMode.ORIGINAL: "Relación original",
            ScaleMode.STRETCH: "Estirar",
        }[self]


class ConnectionState(Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"

    @property
    def label(self) -> str:
        return {
            ConnectionState.CONNECTED: "Conectado",
            ConnectionState.DISCONNECTED: "Desconectado",
            ConnectionState.RECONNECTING: "Reconectando",
        }[self]
