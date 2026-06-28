from snes_ui.main_window import MainWindow, _FoldersDialog
from snes_ui.state import SessionState
from snes_ui.settings import AppSettings
from snes_ui.services.library_service import LibraryService


def test_library_populated_on_start(qapp, tmp_path):
    (tmp_path / "FZero.sfc").write_bytes(b"x")
    AppSettings().set_library_folders([str(tmp_path)])
    w = MainWindow()
    # En el arranque el estado es EMPTY → la biblioteca se refrescó.
    assert w._stage._library._list.count() == 1


def test_selecting_game_begins_loading(qapp, tmp_path):
    AppSettings().set_library_folders([str(tmp_path)])
    w = MainWindow()
    w._flow_load_game_path(str(tmp_path / "FZero.sfc"))
    # begin_loading transiciona a LOADING (finish_loading va en un singleShot
    # que no se dispara sin procesar el event loop).
    assert w._session.state == SessionState.LOADING


def test_folders_dialog_remove(qapp, tmp_path):
    AppSettings().set_library_folders([str(tmp_path), "ROMS"])
    svc = LibraryService(AppSettings())
    dlg = _FoldersDialog(svc, None)
    dlg._list.setCurrentRow(0)            # str(tmp_path)
    dlg._on_remove()
    assert str(tmp_path) not in svc.folders()
    assert "ROMS" in svc.folders()
