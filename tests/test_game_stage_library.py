from snes_ui.settings import AppSettings
from snes_ui.services.library_service import LibraryService
from snes_ui.widgets.game_stage import GameStage


def _stage(tmp_path):
    s = AppSettings()
    s.set_library_folders([str(tmp_path)])
    return GameStage(LibraryService(s))


def test_refresh_library_populates(qapp, tmp_path):
    (tmp_path / "Pilotwings.sfc").write_bytes(b"x")
    stage = _stage(tmp_path)
    stage.refresh_library()
    assert stage._library._list.count() == 1


def test_game_selected_reemitted(qapp, tmp_path):
    stage = _stage(tmp_path)
    captured = []
    stage.game_selected.connect(captured.append)
    stage._library.game_selected.emit("/roms/X.sfc")
    assert captured == ["/roms/X.sfc"]


def test_manage_folders_reemitted(qapp, tmp_path):
    stage = _stage(tmp_path)
    captured = []
    stage.library_manage_folders.connect(lambda: captured.append(True))
    stage._library.manage_folders_requested.emit()
    assert captured == [True]
