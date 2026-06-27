from PySide6.QtGui import QKeyEvent
from PySide6.QtCore import QEvent, Qt
from snes_ui.main_window import MainWindow
from snes_ui.services.input_service import DEFAULT_KEYBOARD


def _press(win, qt_key, press=True):
    ev = QKeyEvent(
        QEvent.Type.KeyPress if press else QEvent.Type.KeyRelease,
        qt_key, Qt.KeyboardModifier.NoModifier,
    )
    if press:
        win._handle_key_press(ev)
    else:
        win._handle_key_release(ev)


def test_keyboard_drives_core_via_profiles(qapp):
    win = MainWindow()
    pressed = {}
    win._core.set_input = lambda rid, val: pressed.__setitem__(rid, val)
    # Tecla por defecto de 'a' (X = 0x58) -> retro_id 8
    _press(win, DEFAULT_KEYBOARD["a"], True)
    assert pressed.get(8) is True
    _press(win, DEFAULT_KEYBOARD["a"], False)
    assert pressed.get(8) is False
    win.close()


def test_or_combine_keyboard_and_pad(qapp):
    win = MainWindow()
    pressed = {}
    win._core.set_input = lambda rid, val: pressed.__setitem__(rid, val)
    # mando marca 'a' (retro_id 8)
    win._on_pad_pressed({"a"})
    assert pressed.get(8) is True
    # teclado marca 'b' (retro_id 0); 'a' sigue activo por el mando
    _press(win, DEFAULT_KEYBOARD["b"], True)
    assert pressed.get(0) is True and pressed.get(8) is True
    # soltar 'a' en el mando lo apaga; 'b' del teclado sigue
    win._on_pad_pressed(set())
    assert pressed.get(8) is False and pressed.get(0) is True
    win.close()
