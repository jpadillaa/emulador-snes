from snes_ui.core.adapter import MockEmulatorCore
from snes_ui.core.session import SessionController
from snes_ui.services.sram_service import SramStore


class _FakeCore(MockEmulatorCore):
    """Core falso que registra el SRAM cargado y expone uno a guardar."""

    def __init__(self) -> None:
        super().__init__()
        self.loaded_sram: bytes | None = None
        self.current_sram = b""

    def get_sram(self) -> bytes:
        return self.current_sram

    def load_sram(self, blob: bytes) -> None:
        self.loaded_sram = blob


def _rom(tmp_path, name: str) -> str:
    p = tmp_path / name
    p.write_bytes(b"\x00" * 1024)  # ROM no vacía con extensión válida
    return str(p)


def test_loads_sram_into_core_on_start(qapp, tmp_path):
    store = SramStore(tmp_path / "sram")
    store.write("game.sfc", b"SAVED")
    core = _FakeCore()
    sc = SessionController(core, sram_store=store)
    path = _rom(tmp_path, "game.sfc")

    sc.begin_loading(path)
    sc.finish_loading()

    assert core.loaded_sram == b"SAVED"


def test_no_load_when_no_sram_file(qapp, tmp_path):
    store = SramStore(tmp_path / "sram")
    core = _FakeCore()
    sc = SessionController(core, sram_store=store)

    sc.begin_loading(_rom(tmp_path, "fresh.sfc"))
    sc.finish_loading()

    assert core.loaded_sram is None  # no se llama load_sram con b""


def test_flush_on_quit_writes_core_sram(qapp, tmp_path):
    store = SramStore(tmp_path / "sram")
    core = _FakeCore()
    sc = SessionController(core, sram_store=store)
    sc.begin_loading(_rom(tmp_path, "game.sfc"))
    sc.finish_loading()

    core.current_sram = b"PROGRESS"
    sc.quit_session()

    assert store.read("game.sfc") == b"PROGRESS"


def test_switching_games_flushes_previous(qapp, tmp_path):
    store = SramStore(tmp_path / "sram")
    core = _FakeCore()
    sc = SessionController(core, sram_store=store)
    sc.begin_loading(_rom(tmp_path, "first.sfc"))
    sc.finish_loading()

    # El juego en curso tiene progreso; cambiamos a otro juego.
    core.current_sram = b"FIRSTSAVE"
    sc.begin_loading(_rom(tmp_path, "second.sfc"))

    assert store.read("first.sfc") == b"FIRSTSAVE"


def test_flush_sram_public_method(qapp, tmp_path):
    store = SramStore(tmp_path / "sram")
    core = _FakeCore()
    sc = SessionController(core, sram_store=store)
    sc.begin_loading(_rom(tmp_path, "game.sfc"))
    sc.finish_loading()

    core.current_sram = b"ATEXIT"
    sc.flush_sram()

    assert store.read("game.sfc") == b"ATEXIT"
