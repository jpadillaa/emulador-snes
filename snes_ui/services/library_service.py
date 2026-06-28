"""Gestor de biblioteca: escaneo síncrono de ROMs en carpetas configurables.

Sin base de datos ni caché en disco: la lista de carpetas se persiste vía
``AppSettings`` y la lista de juegos se escanea fresca bajo demanda. Lógica
pura (sin widgets) para poder probarse en aislamiento.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..settings import AppSettings

_EXTENSIONS = ("*.sfc", "*.smc", "*.SFC", "*.SMC")


def clean_name(filename: str) -> str:
    """Nombre legible a partir del archivo: sin extensión, '_'/'.' → espacios."""
    stem = Path(filename).stem
    name = " ".join(stem.replace("_", " ").replace(".", " ").split())
    return name or filename


@dataclass(frozen=True)
class GameEntry:
    path: Path           # ruta absoluta a la ROM
    display_name: str    # nombre limpio para mostrar
    folder: str          # nombre de la carpeta contenedora (desambigua)


class LibraryService:
    """Escanea carpetas (persistidas) en busca de ROMs SNES."""

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def folders(self) -> list[str]:
        return self._settings.library_folders()

    def add_folder(self, path: str) -> None:
        folders = self.folders()
        if path not in folders:
            folders.append(path)
            self._settings.set_library_folders(folders)

    def remove_folder(self, path: str) -> None:
        folders = [f for f in self.folders() if f != path]
        self._settings.set_library_folders(folders)

    def scan(self) -> list[GameEntry]:
        seen: set[Path] = set()
        entries: list[GameEntry] = []
        for folder in self.folders():
            root = Path(folder)
            if not root.is_dir():
                continue
            for pattern in _EXTENSIONS:
                for path in root.rglob(pattern):
                    rp = path.resolve()
                    if rp in seen or not rp.is_file():
                        continue
                    seen.add(rp)
                    entries.append(
                        GameEntry(rp, clean_name(rp.name), rp.parent.name)
                    )
        entries.sort(key=lambda e: e.display_name.lower())
        return entries
