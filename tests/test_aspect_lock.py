from PySide6.QtCore import Qt
from snes_ui.main_window import MainWindow
from snes_ui.state import ScaleMode


def _surface_mode(win):
    return win._stage._video._mode


def test_normal_window_uses_user_mode(qapp):
    win = MainWindow()
    win._set_scale_mode(ScaleMode.STRETCH)
    assert not win._aspect_locked
    assert _surface_mode(win) == ScaleMode.STRETCH
    win.close()


def test_maximize_forces_4_3_and_restores(qapp):
    win = MainWindow()
    win.show()
    win._set_scale_mode(ScaleMode.STRETCH)

    win.setWindowState(win.windowState() | Qt.WindowState.WindowMaximized)
    qapp.processEvents()
    assert win._aspect_locked
    assert _surface_mode(win) == ScaleMode.FIT_WINDOW  # 4:3 forzado

    win.setWindowState(Qt.WindowState.WindowNoState)
    qapp.processEvents()
    assert not win._aspect_locked
    assert _surface_mode(win) == ScaleMode.STRETCH  # preferencia restaurada
    win.close()


def test_fullscreen_forces_4_3(qapp):
    win = MainWindow()
    win.show()
    win._set_scale_mode(ScaleMode.INTEGER)

    win.setWindowState(Qt.WindowState.WindowFullScreen)
    qapp.processEvents()
    assert win._aspect_locked
    assert _surface_mode(win) == ScaleMode.FIT_WINDOW
    win.close()


def test_mode_change_while_locked_keeps_4_3_but_persists_pref(qapp):
    win = MainWindow()
    win.show()
    win.setWindowState(Qt.WindowState.WindowFullScreen)
    qapp.processEvents()

    win._set_scale_mode(ScaleMode.STRETCH)  # cambia preferencia durante bloqueo
    assert win._scale_mode == ScaleMode.STRETCH
    assert _surface_mode(win) == ScaleMode.FIT_WINDOW  # pantalla sigue 4:3

    win.setWindowState(Qt.WindowState.WindowNoState)
    qapp.processEvents()
    assert _surface_mode(win) == ScaleMode.STRETCH  # se aplica al salir
    win.close()
