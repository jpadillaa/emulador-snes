from snes_ui.services.input_service import Binding, pack_hat, key_binding


def test_pack_hat_directions():
    assert pack_hat(0, 1) == 5    # arriba
    assert pack_hat(0, -1) == 3   # abajo
    assert pack_hat(-1, 0) == 1   # izquierda
    assert pack_hat(1, 0) == 7    # derecha


def test_label_per_kind(qapp):
    assert key_binding(0x58).label() == "X"                    # letra: nombre tal cual
    assert key_binding(0x01000013).label() == "↑"             # flecha: glifo macOS
    assert key_binding(0x01000004).label() == "↩"             # Return: glifo
    assert Binding("button", 0).label() == "Botón 0"
    assert Binding("hat", 0, pack_hat(0, 1)).label() == "D-Pad ↑"
    assert Binding("axis", 1, 1).label() == "Eje 1 +"
    assert Binding("axis", 1, -1).label() == "Eje 1 −"


def test_to_from_dict_roundtrip():
    b = Binding("hat", 0, 5)
    assert Binding.from_dict(b.to_dict()) == b
    assert Binding.from_dict({"bad": 1}) is None
    assert Binding.from_dict({"kind": "button", "code": "x"}) is None
