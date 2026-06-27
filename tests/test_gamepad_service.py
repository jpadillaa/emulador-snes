from snes_ui.services.gamepad_service import GamepadService, PadInfo, PadState
from snes_ui.services.input_service import Binding, pack_hat
from snes_ui.state import ConnectionState


class FakeBackend:
    def __init__(self):
        self._devices = []
        self._states = {}
    def init(self): return True
    def pump(self): pass
    def devices(self): return list(self._devices)
    def read(self, iid): return self._states.get(iid)
    # helpers de test
    def plug(self, iid, guid, name, state):
        self._devices.append(PadInfo(iid, guid, name)); self._states[iid] = state
    def unplug(self, iid):
        self._devices = [d for d in self._devices if d.instance_id != iid]
        self._states.pop(iid, None)


def test_no_pads_is_safe(qapp):
    svc = GamepadService(backend=FakeBackend())
    seen = []
    svc.devices_changed.connect(seen.append)
    svc.poll_once()
    assert svc.devices == []


def test_hotplug_emits_devices_and_connection(qapp):
    be = FakeBackend()
    svc = GamepadService(backend=be)
    names, conns = [], []
    svc.devices_changed.connect(lambda d: names.append([p.name for p in d]))
    svc.connection_changed.connect(conns.append)
    be.plug(3, "GUID1", "Mando X", PadState((0, 0), ((0, 0),), (0.0, 0.0)))
    svc.poll_once()
    assert names and names[-1] == ["Mando X"]
    assert conns and conns[-1] == ConnectionState.CONNECTED


def test_active_pad_emits_pressed(qapp):
    be = FakeBackend()
    be.plug(3, "GUID1", "Mando X", PadState((0, 1), ((0, 0),), (0.0, 0.0)))
    svc = GamepadService(backend=be)
    svc.poll_once()  # registra dispositivo
    svc.set_active(3, {"a": Binding("button", 1)})
    out = []
    svc.pressed_changed.connect(out.append)
    svc.poll_once()
    assert out and "a" in out[-1]


def test_capture_mode_emits_binding(qapp):
    be = FakeBackend()
    be.plug(3, "GUID1", "Mando X", PadState((0, 0), ((0, 0),), (0.0, 0.0)))
    svc = GamepadService(backend=be)
    svc.poll_once()
    svc.set_active(3, {})
    svc.set_capture(True)
    svc.poll_once()  # estado base (sin pulsar)
    captured = []
    svc.binding_captured.connect(captured.append)
    be._states[3] = PadState((0, 1), ((0, 0),), (0.0, 0.0))  # pulsa botón 1
    svc.poll_once()
    assert captured and captured[-1] == Binding("button", 1)


def test_unplug_active_sets_disconnected(qapp):
    be = FakeBackend()
    be.plug(3, "GUID1", "Mando X", PadState((0, 0), ((0, 0),), (0.0, 0.0)))
    svc = GamepadService(backend=be)
    svc.poll_once()
    svc.set_active(3, {})
    conns = []
    svc.connection_changed.connect(conns.append)
    be.unplug(3)
    svc.poll_once()
    assert conns and conns[-1] == ConnectionState.DISCONNECTED
