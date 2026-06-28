from pathlib import Path

from snes_ui.services.sram_service import SramStore


def test_write_then_read_roundtrip(tmp_path):
    store = SramStore(tmp_path)
    store.write("Super Mario Kart.sfc", b"\x01\x02\x03")
    assert store.read("Super Mario Kart.sfc") == b"\x01\x02\x03"


def test_read_missing_returns_empty(tmp_path):
    store = SramStore(tmp_path)
    assert store.read("nope.sfc") == b""


def test_write_empty_creates_no_file(tmp_path):
    store = SramStore(tmp_path)
    store.write("game.sfc", b"")
    assert not store.path_for("game.sfc").exists()


def test_write_is_atomic_no_tmp_residue(tmp_path):
    store = SramStore(tmp_path)
    store.write("game.sfc", b"abcd")
    p = store.path_for("game.sfc")
    assert p.read_bytes() == b"abcd"
    # no debe quedar el temporal
    assert not list(p.parent.glob("*.tmp"))


def test_overwrite_replaces_content(tmp_path):
    store = SramStore(tmp_path)
    store.write("game.sfc", b"old")
    store.write("game.sfc", b"newer")
    assert store.read("game.sfc") == b"newer"


def test_filename_is_sanitized(tmp_path):
    store = SramStore(tmp_path)
    p = store.path_for("Legend/of:Zelda.sfc")
    assert p.suffix == ".srm"
    assert "/" not in p.name and ":" not in p.name
