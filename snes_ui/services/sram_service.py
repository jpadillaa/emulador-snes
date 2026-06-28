"""Persistencia del SRAM (RAM de batería del cartucho) en archivos .srm.

Espejo minimalista de SaveService: un archivo por ROM bajo
``AppDataLocation/sram/``. En libretro el *frontend* es responsable de volcar y
cargar el SRAM (el core de snes9x delega en él), igual que hace RetroArch.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths


def _sanitize(name: str) -> str:
    """Nombre de archivo seguro a partir del nombre de la ROM (sin extensión)."""
    stem = Path(name).stem
    cleaned = re.sub(r"[^\w.\- ]+", "_", stem).strip()
    return cleaned or "rom"


class SramStore:
    """Lee/escribe el .srm de cada ROM bajo ``AppDataLocation/sram/``."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        if base_dir is None:
            root = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppDataLocation
            )
            base_dir = Path(root) / "sram"
        self._base = Path(base_dir)

    def path_for(self, rom_name: str) -> Path:
        return self._base / f"{_sanitize(rom_name)}.srm"

    def read(self, rom_name: str) -> bytes:
        path = self.path_for(rom_name)
        try:
            return path.read_bytes()
        except FileNotFoundError:
            return b""
        except OSError as exc:
            print(f"[sram] no se pudo leer {path}: {exc}", file=sys.stderr)
            return b""

    def write(self, rom_name: str, blob: bytes) -> None:
        if not blob:
            return
        path = self.path_for(rom_name)
        tmp = path.with_name(path.name + ".tmp")
        try:
            self._base.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(blob)
            os.replace(tmp, path)
        except OSError as exc:
            print(f"[sram] no se pudo escribir {path}: {exc}", file=sys.stderr)
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
