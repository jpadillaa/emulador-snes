from snes_ui.core.adapter import MockEmulatorCore


def test_mock_get_sram_is_empty():
    assert MockEmulatorCore().get_sram() == b""


def test_mock_load_sram_is_noop():
    core = MockEmulatorCore()
    # No debe lanzar ni tener efecto observable.
    assert core.load_sram(b"\x00\x01") is None
