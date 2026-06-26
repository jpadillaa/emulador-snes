"""Servicio de estados de guardado (simulado).

Mantiene en memoria una lista de estados guardados por ROM. No escribe a
disco; una integracion real persistiria los blobs y miniaturas. Suficiente
para demostrar los flujos de guardar y cargar partida.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SaveState:
    rom_name: str
    timestamp: str       # marca temporal legible
    blob: bytes

    @property
    def label(self) -> str:
        return f"{self.rom_name} — {self.timestamp}"


class SaveService:
    def __init__(self) -> None:
        self._states: dict[str, list[SaveState]] = {}
        self._counter = 0

    def _now(self) -> str:
        # Marca temporal incremental simulada (evita dependencias de reloj que
        # complican la reproducibilidad de la demo).
        self._counter += 1
        return f"Ranura {self._counter:02d}"

    def create(self, rom_name: str, blob: bytes) -> SaveState:
        state = SaveState(rom_name, self._now(), blob)
        self._states.setdefault(rom_name, []).append(state)
        return state

    def list_for(self, rom_name: str) -> list[SaveState]:
        return list(self._states.get(rom_name, []))

    def has_states(self, rom_name: str) -> bool:
        return bool(self._states.get(rom_name))
