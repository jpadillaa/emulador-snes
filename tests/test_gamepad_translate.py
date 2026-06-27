from snes_ui.services.input_service import Binding, pack_hat
from snes_ui.services.gamepad_service import (
    PadState, translate, detect_binding,
)

PROFILE = {
    "a": Binding("button", 1),
    "up": Binding("hat", 0, pack_hat(0, 1)),
    "r": Binding("axis", 5, 1),
}


def _state(buttons=(), hats=(), axes=()):
    return PadState(tuple(buttons), tuple(hats), tuple(axes))


def test_translate_button():
    s = _state(buttons=(0, 1), hats=((0, 0),), axes=(0.0,) * 6)
    assert "a" in translate(s, PROFILE)


def test_translate_hat_direction():
    s = _state(buttons=(0, 0), hats=((0, 1),), axes=(0.0,) * 6)
    assert "up" in translate(s, PROFILE)


def test_translate_axis_past_deadzone():
    s = _state(buttons=(0, 0), hats=((0, 0),), axes=(0, 0, 0, 0, 0, 0.9))
    assert "r" in translate(s, PROFILE)
    s2 = _state(buttons=(0, 0), hats=((0, 0),), axes=(0, 0, 0, 0, 0, 0.2))
    assert "r" not in translate(s2, PROFILE)


def test_left_stick_drives_dpad():
    s = _state(buttons=(), hats=(), axes=(-0.9, 0.0))
    out = translate(s, {})
    assert "left" in out
    s2 = _state(buttons=(), hats=(), axes=(0.0, 0.9))
    assert "down" in translate(s2, {})


def test_detect_button_press():
    prev = _state(buttons=(0, 0))
    cur = _state(buttons=(0, 1))
    assert detect_binding(prev, cur) == Binding("button", 1)


def test_detect_hat_direction():
    prev = _state(hats=((0, 0),))
    cur = _state(hats=((1, 0),))
    assert detect_binding(prev, cur) == Binding("hat", 0, pack_hat(1, 0))


def test_detect_axis_push():
    prev = _state(axes=(0.0, 0.0))
    cur = _state(axes=(0.0, -0.9))
    assert detect_binding(prev, cur) == Binding("axis", 1, -1)


def test_detect_none_when_idle():
    s = _state(buttons=(0, 0), hats=((0, 0),), axes=(0.0, 0.0))
    assert detect_binding(s, s) is None
