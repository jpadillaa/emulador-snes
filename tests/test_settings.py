from snes_ui.settings import AppSettings


def test_library_folders_default(qapp):
    s = AppSettings()
    # Sin valor previo (QSettings redirigido a temp por conftest).
    assert s.library_folders() == ["ROMS"]


def test_library_folders_roundtrip(qapp):
    s = AppSettings()
    s.set_library_folders(["ROMS", "/tmp/juegos"])
    assert AppSettings().library_folders() == ["ROMS", "/tmp/juegos"]


def test_library_folders_ignores_corrupt(qapp):
    s = AppSettings()
    s._s.setValue("library/folders", "no-es-json")
    assert s.library_folders() == ["ROMS"]
