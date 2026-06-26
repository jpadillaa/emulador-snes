"""Persistencia con QSettings.

Centraliza la lectura/escritura de las preferencias que la especificacion
exige persistir: asignaciones de botones, dispositivo seleccionado, tema,
modo de visualizacion del escenario, pestaña activa del panel y geometria.
"""
from __future__ import annotations

import json

from PySide6.QtCore import QSettings, QByteArray

ORG = "SNESEmulatorDemo"
APP = "SNESEmulator"


class AppSettings:
    def __init__(self) -> None:
        self._s = QSettings(ORG, APP)

    # -- geometria / estado de ventana --------------------------------------
    def save_geometry(self, geometry: QByteArray, state: QByteArray) -> None:
        self._s.setValue("win/geometry", geometry)
        self._s.setValue("win/state", state)

    def geometry(self) -> QByteArray | None:
        return self._s.value("win/geometry")

    def window_state(self) -> QByteArray | None:
        return self._s.value("win/state")

    # -- tema ----------------------------------------------------------------
    def theme_preference(self) -> str:
        return self._s.value("ui/theme", "system")

    def set_theme_preference(self, value: str) -> None:
        self._s.setValue("ui/theme", value)

    # -- modo de visualizacion ----------------------------------------------
    def scale_mode(self) -> str:
        return self._s.value("ui/scale_mode", "fit")

    def set_scale_mode(self, value: str) -> None:
        self._s.setValue("ui/scale_mode", value)

    # -- pestaña activa del panel -------------------------------------------
    def active_tab(self) -> int:
        return int(self._s.value("panel/active_tab", 0))

    def set_active_tab(self, index: int) -> None:
        self._s.setValue("panel/active_tab", index)

    # -- dispositivo ---------------------------------------------------------
    def device(self) -> str:
        return self._s.value("input/device", "Keyboard")

    def set_device(self, name: str) -> None:
        self._s.setValue("input/device", name)

    # -- asignaciones --------------------------------------------------------
    def mappings(self) -> dict[str, str] | None:
        raw = self._s.value("input/mappings")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

    def set_mappings(self, mappings: dict[str, str]) -> None:
        self._s.setValue("input/mappings", json.dumps(mappings))
