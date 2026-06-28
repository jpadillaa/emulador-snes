from pathlib import Path

from snes_ui.widgets.library_view import LibraryView
from snes_ui.services.library_service import GameEntry


def _entries():
    return [
        GameEntry(Path("/roms/Zelda.sfc"), "Zelda", "roms"),
        GameEntry(Path("/roms/Metroid.smc"), "Metroid", "roms"),
    ]


def test_set_games_populates_list(qapp):
    v = LibraryView()
    v.set_games(_entries())
    assert v._list.count() == 2


def test_search_hides_non_matching(qapp):
    v = LibraryView()
    v.set_games(_entries())
    v._search.setText("zel")
    visible = [i for i in range(v._list.count())
               if not v._list.item(i).isHidden()]
    assert len(visible) == 1
    assert v._list.item(visible[0]).text() == "Zelda"


def test_activating_item_emits_game_selected(qapp):
    v = LibraryView()
    v.set_games(_entries())
    captured = []
    v.game_selected.connect(captured.append)
    v._list.setCurrentRow(0)
    v._on_item_activated(v._list.currentItem())
    assert captured == [str(Path("/roms/Zelda.sfc"))]   # row 0 = Zelda (orden de _entries)


def test_empty_shows_guide(qapp):
    v = LibraryView()
    v.set_games([])
    assert v._stack.currentWidget() is v._empty_page
