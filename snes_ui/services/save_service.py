"""Servicio de estados de guardado (persistente en disco).

Cada partida guardada se materializa como dos archivos bajo el directorio de
datos de la aplicacion: el blob del estado serializado por el nucleo
(``.state``) y una miniatura PNG del fotograma en el momento de guardar
(``.thumb.png``). La marca temporal real forma el nombre del archivo, de modo
que los estados sobreviven a reinicios y se listan ordenados por fecha.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QStandardPaths
from PySide6.QtGui import QImage

# Resolucion de la miniatura almacenada (4:3, ligera).
_THUMB_W, _THUMB_H = 256, 192
_TS_FORMAT = "%Y%m%d-%H%M%S-%f"


def _sanitize(name: str) -> str:
    """Convierte el nombre de ROM en un nombre de carpeta seguro."""
    safe = "".join(c if (c.isalnum() or c in " -_.") else "_" for c in name).strip()
    return safe or "rom"


@dataclass(frozen=True)
class SaveState:
    rom_name: str
    timestamp: datetime          # marca temporal real
    state_path: Path
    thumb_path: Path | None

    @property
    def label(self) -> str:
        return self.timestamp.strftime("%Y-%m-%d %H:%M:%S")

    def read_blob(self) -> bytes:
        return self.state_path.read_bytes()


class SaveService:
    """Crea, lista y elimina estados de guardado persistidos en disco."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        if base_dir is None:
            root = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppDataLocation
            )
            base_dir = Path(root) / "saves"
        self._base = Path(base_dir)

    def _rom_dir(self, rom_name: str) -> Path:
        return self._base / _sanitize(rom_name)

    # -- creacion ------------------------------------------------------------
    def create(self, rom_name: str, blob: bytes, thumbnail: QImage | None = None) -> SaveState:
        """Persiste un estado y su miniatura; devuelve el SaveState resultante."""
        rom_dir = self._rom_dir(rom_name)
        rom_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now()
        stem = ts.strftime(_TS_FORMAT)
        state_path = rom_dir / f"{stem}.state"
        state_path.write_bytes(blob)

        thumb_path: Path | None = None
        if thumbnail is not None and not thumbnail.isNull():
            scaled = thumbnail.scaled(
                _THUMB_W,
                _THUMB_H,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            candidate = rom_dir / f"{stem}.thumb.png"
            if scaled.save(str(candidate), "PNG"):
                thumb_path = candidate

        return SaveState(rom_name, ts, state_path, thumb_path)

    # -- consulta ------------------------------------------------------------
    def list_for(self, rom_name: str) -> list[SaveState]:
        """Estados guardados de una ROM, del mas reciente al mas antiguo."""
        rom_dir = self._rom_dir(rom_name)
        if not rom_dir.is_dir():
            return []
        states: list[SaveState] = []
        for state_path in rom_dir.glob("*.state"):
            ts = self._timestamp_for(state_path)
            thumb = state_path.with_suffix(".thumb.png")
            states.append(
                SaveState(
                    rom_name,
                    ts,
                    state_path,
                    thumb if thumb.exists() else None,
                )
            )
        states.sort(key=lambda s: s.timestamp, reverse=True)
        return states

    def has_states(self, rom_name: str) -> bool:
        rom_dir = self._rom_dir(rom_name)
        return rom_dir.is_dir() and any(rom_dir.glob("*.state"))

    # -- eliminacion ---------------------------------------------------------
    def delete(self, state: SaveState) -> None:
        state.state_path.unlink(missing_ok=True)
        if state.thumb_path is not None:
            state.thumb_path.unlink(missing_ok=True)

    # -- utilidades ----------------------------------------------------------
    @staticmethod
    def _timestamp_for(state_path: Path) -> datetime:
        """Marca temporal a partir del nombre; cae a la fecha de modificacion."""
        try:
            return datetime.strptime(state_path.stem, _TS_FORMAT)
        except ValueError:
            return datetime.fromtimestamp(state_path.stat().st_mtime)
