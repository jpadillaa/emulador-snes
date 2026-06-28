from pathlib import Path

import pytest

from snes_ui.settings import AppSettings
from snes_ui.services.library_service import (
    LibraryService,
    GameEntry,
    clean_name,
)


def test_clean_name():
    assert clean_name("Super_Mario_Kart.sfc") == "Super Mario Kart"
    assert clean_name("TopGear.smc") == "TopGear"
    assert clean_name("Donkey.Kong.Country.sfc") == "Donkey Kong Country"


@pytest.fixture
def service(qapp, tmp_path):
    s = AppSettings()
    s.set_library_folders([])           # parte de cero, sin la carpeta ROMS por defecto
    return LibraryService(s)


def test_scan_finds_roms_and_ignores_others(service, tmp_path):
    (tmp_path / "Zelda.sfc").write_bytes(b"x")
    (tmp_path / "Metroid.smc").write_bytes(b"x")
    (tmp_path / "leeme.txt").write_text("hola")
    service.add_folder(str(tmp_path))

    games = service.scan()
    names = [g.display_name for g in games]
    assert names == ["Metroid", "Zelda"]            # orden alfabético
    assert all(isinstance(g, GameEntry) for g in games)
    assert all(g.path.suffix.lower() in (".sfc", ".smc") for g in games)


def test_scan_is_recursive_and_sets_folder(service, tmp_path):
    sub = tmp_path / "snes"
    sub.mkdir()
    (sub / "Earthbound.sfc").write_bytes(b"x")
    service.add_folder(str(tmp_path))

    games = service.scan()
    assert len(games) == 1
    assert games[0].folder == "snes"


def test_scan_dedups_overlapping_folders(service, tmp_path):
    (tmp_path / "Contra.sfc").write_bytes(b"x")
    service.add_folder(str(tmp_path))
    service.add_folder(str(tmp_path))            # duplicada
    assert len(service.scan()) == 1


def test_scan_ignores_missing_folder(service, tmp_path):
    service.add_folder(str(tmp_path / "no-existe"))
    assert service.scan() == []


def test_add_remove_folder_persists(service, tmp_path):
    service.add_folder(str(tmp_path))
    assert str(tmp_path) in service.folders()
    service.remove_folder(str(tmp_path))
    assert str(tmp_path) not in service.folders()
