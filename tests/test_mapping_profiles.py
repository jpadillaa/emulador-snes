import json
from snes_ui.services.input_service import (
    Binding, MappingProfiles, KEYBOARD_KEY, DEFAULT_KEYBOARD, DEFAULT_GAMEPAD,
    key_binding,
)


def test_keyboard_defaults_present():
    p = MappingProfiles()
    p.ensure(KEYBOARD_KEY, gamepad=False)
    assert p.binding(KEYBOARD_KEY, "a") == key_binding(DEFAULT_KEYBOARD["a"])
    assert p.input_for_key(KEYBOARD_KEY, DEFAULT_KEYBOARD["a"]) == "a"


def test_gamepad_default_profile():
    p = MappingProfiles()
    p.ensure("GUID1", gamepad=True)
    assert p.binding("GUID1", "a").kind == "button"
    assert p.binding("GUID1", "up").kind == "hat"


def test_assign_and_reset():
    p = MappingProfiles()
    p.ensure("GUID1", gamepad=True)
    p.assign("GUID1", "a", Binding("button", 9))
    assert p.binding("GUID1", "a") == Binding("button", 9)
    p.reset("GUID1", gamepad=True)
    assert p.binding("GUID1", "a") == DEFAULT_GAMEPAD["a"]   # vuelve al default


def test_json_roundtrip():
    p = MappingProfiles()
    p.ensure(KEYBOARD_KEY, gamepad=False)
    p.ensure("GUID1", gamepad=True)
    p.assign("GUID1", "a", Binding("button", 3))
    restored = MappingProfiles.from_json(p.to_json())
    assert restored.binding("GUID1", "a") == Binding("button", 3)
    assert restored.binding(KEYBOARD_KEY, "a") == p.binding(KEYBOARD_KEY, "a")


def test_legacy_flat_format_migrates_to_keyboard():
    legacy = json.dumps({"a": DEFAULT_KEYBOARD["a"], "b": DEFAULT_KEYBOARD["b"]})
    p = MappingProfiles.from_json(legacy)
    assert p.binding(KEYBOARD_KEY, "a") == key_binding(DEFAULT_KEYBOARD["a"])


def test_from_json_none_is_empty():
    assert MappingProfiles.from_json(None).profile(KEYBOARD_KEY) == {}
