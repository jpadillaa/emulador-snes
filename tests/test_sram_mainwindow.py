from snes_ui.main_window import MainWindow
from snes_ui.services.sram_service import SramStore


def test_mainwindow_shares_sram_store(qapp):
    mw = MainWindow()
    try:
        assert isinstance(mw._sram, SramStore)
        assert mw._session._sram is mw._sram
    finally:
        mw.close()


def test_close_flushes_without_crashing(qapp):
    # Con el core mock (get_sram → b"") no se escribe nada, pero el camino de
    # volcado en closeEvent debe ejecutarse sin lanzar.
    mw = MainWindow()
    mw.close()  # dispara closeEvent → flush_sram + shutdown
