# Soporte real de gamepad — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir jugar con un mando físico remapeable (perfiles por dispositivo), combinado con el teclado, sin tocar el núcleo ni el `SessionController`.

**Architecture:** Un `GamepadService` aislado encapsula todo pygame (QTimer ~60 Hz en el hilo principal, enumeración, hot-plug). Los bindings se generalizan a un tipo `Binding` (tecla/botón/hat/eje) y se guardan en perfiles por dispositivo (`MappingProfiles`). `MainWindow` combina (OR) las entradas de teclado y mando y las envía al núcleo.

**Tech Stack:** Python 3.14, PySide6 6.11, pygame 2.6.1 (ya dependencia), pytest (nuevo, solo desarrollo).

## Global Constraints

- Python 3.14; PySide6 6.11; pygame 2.6.1. **Sin nuevas dependencias de runtime** (pygame ya está).
- Todo el código de pygame/Qt corre en el **hilo principal** (SDL en macOS lo exige).
- Backend: `pygame.joystick` **crudo** (no `pygame._sdl2.controller`).
- **Un solo jugador** (puerto 0). Sin multijugador, sin rumble.
- Enrutamiento **OR-combine**: el teclado siempre alimenta el juego; el mando activo se suma.
- Zona muerta de ejes: **0.5** (constante).
- `device_key`: `"keyboard"` para teclado; **GUID SDL** para mandos.
- Textos de UI en **español** (consistencia con el resto).
- No tocar `snes_ui/core/session.py`.

---

## File Structure

- **Crear** `snes_ui/services/gamepad_service.py` — `PadInfo`, `PadState`, funciones puras `pack`/`translate`/`detect_binding`, `_PygamePadBackend`, `GamepadService`.
- **Modificar** `snes_ui/services/input_service.py` — añadir `Binding`, `MappingProfiles`, defaults de teclado/mando; conservar `SNES_INPUTS`, `RETRO_ID`, `InputService`.
- **Modificar** `snes_ui/settings.py` — persistencia anidada por dispositivo + migración del formato plano.
- **Modificar** `snes_ui/widgets/control_panel.py` — mostrar/editar el perfil del dispositivo activo vía `MappingProfiles`.
- **Modificar** `snes_ui/main_window.py` — `GamepadService`, enrutamiento OR (`_recompute_inputs`), captura por mando, indicador de conexión.
- **Crear** `tests/` — `conftest.py`, `test_binding.py`, `test_mapping_profiles.py`, `test_gamepad_translate.py`, `test_gamepad_service.py`, `test_input_routing.py`.
- **Crear** `requirements-dev.txt` — `pytest`.

---

## Task 1: Infraestructura de pruebas

**Files:**
- Create: `requirements-dev.txt`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Interfaces:**
- Produces: fixture pytest `qapp` (sesión) que crea una única `QApplication` offscreen; permite instanciar `QObject`/widgets en tests.

- [ ] **Step 1: Crear `requirements-dev.txt`**

```
pytest==8.3.4
```

- [ ] **Step 2: Instalar pytest**

Run: `source .venv/bin/activate && pip install -r requirements-dev.txt`
Expected: `Successfully installed pytest-8.3.4 ...`

- [ ] **Step 3: Crear `tests/__init__.py`** (vacío)

```python
```

- [ ] **Step 4: Crear `tests/conftest.py`**

```python
"""Configuración de pytest: QApplication única en modo offscreen."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
```

- [ ] **Step 5: Verificar que pytest descubre la suite vacía**

Run: `source .venv/bin/activate && python -m pytest -q`
Expected: `no tests ran` (sin errores de import).

- [ ] **Step 6: Commit**

```bash
git add requirements-dev.txt tests/__init__.py tests/conftest.py
git commit -m "test: configurar pytest con QApplication offscreen"
```

---

## Task 2: Tipo `Binding`

**Files:**
- Modify: `snes_ui/services/input_service.py`
- Test: `tests/test_binding.py`

**Interfaces:**
- Produces:
  - `pack_hat(x: int, y: int) -> int` — empaqueta dirección de hat (0–8).
  - `Binding(kind: str, code: int, value: int = 0)` (frozen dataclass) con:
    - `label() -> str`
    - `to_dict() -> dict`
    - `Binding.from_dict(d: dict) -> Binding | None`
  - `key_binding(code: int) -> Binding` — atajo para `Binding("key", code)`.
  - `_HAT_ARROWS: dict[int, str]`.

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_binding.py
from snes_ui.services.input_service import Binding, pack_hat, key_binding


def test_pack_hat_directions():
    assert pack_hat(0, 1) == 5    # arriba
    assert pack_hat(0, -1) == 3   # abajo
    assert pack_hat(-1, 0) == 1   # izquierda
    assert pack_hat(1, 0) == 7    # derecha


def test_label_per_kind(qapp):
    assert key_binding(0x58).label() == "Tecla: X"
    assert Binding("button", 0).label() == "Botón 0"
    assert Binding("hat", 0, pack_hat(0, 1)).label() == "D-Pad ↑"
    assert Binding("axis", 1, 1).label() == "Eje 1 +"
    assert Binding("axis", 1, -1).label() == "Eje 1 −"


def test_to_from_dict_roundtrip():
    b = Binding("hat", 0, 5)
    assert Binding.from_dict(b.to_dict()) == b
    assert Binding.from_dict({"bad": 1}) is None
    assert Binding.from_dict({"kind": "button", "code": "x"}) is None
```

- [ ] **Step 2: Ejecutar y verificar fallo**

Run: `source .venv/bin/activate && python -m pytest tests/test_binding.py -q`
Expected: FAIL con `ImportError: cannot import name 'Binding'`.

- [ ] **Step 3: Implementar en `input_service.py`**

Añadir cerca del inicio (tras los imports existentes; `QKeySequence` ya se importa de `PySide6.QtGui`):

```python
# Direcciones de hat empaquetadas (x,y in {-1,0,1}) -> 0..8.
def pack_hat(x: int, y: int) -> int:
    return (x + 1) * 3 + (y + 1)


_HAT_ARROWS = {5: "↑", 3: "↓", 1: "←", 7: "→", 8: "↗", 2: "↘", 0: "↙", 6: "↖"}


@dataclass(frozen=True)
class Binding:
    """Asignación física: tecla o entrada de mando."""
    kind: str          # "key" | "button" | "hat" | "axis"
    code: int
    value: int = 0     # hat: dirección empaquetada; axis: signo (+1/-1)

    def label(self) -> str:
        if self.kind == "key":
            name = QKeySequence(self.code).toString()
            return f"Tecla: {name}" if name else "Sin asignar"
        if self.kind == "button":
            return f"Botón {self.code}"
        if self.kind == "hat":
            return f"D-Pad {_HAT_ARROWS.get(self.value, '·')}"
        if self.kind == "axis":
            return f"Eje {self.code} {'+' if self.value >= 0 else '−'}"
        return "Sin asignar"

    def to_dict(self) -> dict:
        return {"kind": self.kind, "code": self.code, "value": self.value}

    @classmethod
    def from_dict(cls, d: dict) -> "Binding | None":
        try:
            return cls(str(d["kind"]), int(d["code"]), int(d.get("value", 0)))
        except (KeyError, TypeError, ValueError):
            return None


def key_binding(code: int) -> Binding:
    return Binding("key", code)
```

- [ ] **Step 4: Ejecutar y verificar éxito**

Run: `source .venv/bin/activate && python -m pytest tests/test_binding.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add snes_ui/services/input_service.py tests/test_binding.py
git commit -m "feat(input): tipo Binding generalizado (tecla/botón/hat/eje)"
```

---

## Task 3: `MappingProfiles` y perfiles por defecto

**Files:**
- Modify: `snes_ui/services/input_service.py`
- Test: `tests/test_mapping_profiles.py`

**Interfaces:**
- Consumes: `Binding`, `key_binding`, `pack_hat`, `DEFAULT_KEYBOARD`, `SNES_INPUTS`.
- Produces:
  - `KEYBOARD_KEY = "keyboard"`.
  - `default_keyboard_profile() -> dict[str, Binding]`.
  - `DEFAULT_GAMEPAD: dict[str, Binding]`.
  - `MappingProfiles` con:
    - `ensure(device_key: str, *, gamepad: bool) -> None`
    - `profile(device_key: str) -> dict[str, Binding]`
    - `binding(device_key: str, input_key: str) -> Binding | None`
    - `label_for(device_key: str, input_key: str) -> str`
    - `assign(device_key: str, input_key: str, binding: Binding) -> None`
    - `reset(device_key: str, *, gamepad: bool) -> None`
    - `input_for_key(device_key: str, code: int) -> str | None`
    - `to_json() -> str`
    - `MappingProfiles.from_json(raw: str | None) -> MappingProfiles`

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_mapping_profiles.py
import json
from snes_ui.services.input_service import (
    Binding, MappingProfiles, KEYBOARD_KEY, DEFAULT_KEYBOARD, key_binding,
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
    assert p.binding("GUID1", "a").code == 0   # vuelve al default


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
```

- [ ] **Step 2: Ejecutar y verificar fallo**

Run: `source .venv/bin/activate && python -m pytest tests/test_mapping_profiles.py -q`
Expected: FAIL con `ImportError: cannot import name 'MappingProfiles'`.

- [ ] **Step 3: Implementar en `input_service.py`**

Añadir (tras `DEFAULT_KEYBOARD` y `Binding`). Requiere `import json` al inicio del archivo:

```python
KEYBOARD_KEY = "keyboard"


def default_keyboard_profile() -> dict[str, Binding]:
    return {k: key_binding(c) for k, c in DEFAULT_KEYBOARD.items()}


# Layout estándar (estilo Xbox): índices de botón/hat de pygame.
DEFAULT_GAMEPAD: dict[str, Binding] = {
    "b": Binding("button", 0),
    "a": Binding("button", 1),
    "y": Binding("button", 2),
    "x": Binding("button", 3),
    "l": Binding("button", 4),
    "r": Binding("button", 5),
    "select": Binding("button", 6),
    "start": Binding("button", 7),
    "up": Binding("hat", 0, pack_hat(0, 1)),
    "down": Binding("hat", 0, pack_hat(0, -1)),
    "left": Binding("hat", 0, pack_hat(-1, 0)),
    "right": Binding("hat", 0, pack_hat(1, 0)),
}


class MappingProfiles:
    """Perfiles de asignación por dispositivo (teclado y mandos)."""

    def __init__(self) -> None:
        self._profiles: dict[str, dict[str, Binding]] = {}

    def _defaults(self, *, gamepad: bool) -> dict[str, Binding]:
        return dict(DEFAULT_GAMEPAD) if gamepad else default_keyboard_profile()

    def ensure(self, device_key: str, *, gamepad: bool) -> None:
        if device_key not in self._profiles:
            self._profiles[device_key] = self._defaults(gamepad=gamepad)

    def profile(self, device_key: str) -> dict[str, Binding]:
        return self._profiles.get(device_key, {})

    def binding(self, device_key: str, input_key: str) -> "Binding | None":
        return self._profiles.get(device_key, {}).get(input_key)

    def label_for(self, device_key: str, input_key: str) -> str:
        b = self.binding(device_key, input_key)
        return b.label() if b else "Sin asignar"

    def assign(self, device_key: str, input_key: str, binding: Binding) -> None:
        self._profiles.setdefault(device_key, {})[input_key] = binding

    def reset(self, device_key: str, *, gamepad: bool) -> None:
        self._profiles[device_key] = self._defaults(gamepad=gamepad)

    def input_for_key(self, device_key: str, code: int) -> "str | None":
        for input_key, b in self._profiles.get(device_key, {}).items():
            if b.kind == "key" and b.code == code:
                return input_key
        return None

    def to_json(self) -> str:
        data = {
            dk: {ik: b.to_dict() for ik, b in prof.items()}
            for dk, prof in self._profiles.items()
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, raw: "str | None") -> "MappingProfiles":
        out = cls()
        if not raw:
            return out
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return out
        if not isinstance(data, dict):
            return out
        # Formato heredado (plano): {input_key: int} -> perfil de teclado.
        if data and all(isinstance(v, int) for v in data.values()):
            out._profiles[KEYBOARD_KEY] = {
                ik: key_binding(code) for ik, code in data.items()
            }
            return out
        # Formato anidado por dispositivo.
        for dk, prof in data.items():
            if not isinstance(prof, dict):
                continue
            built: dict[str, Binding] = {}
            for ik, bd in prof.items():
                b = Binding.from_dict(bd) if isinstance(bd, dict) else None
                if b is not None:
                    built[ik] = b
            out._profiles[dk] = built
        return out
```

- [ ] **Step 4: Ejecutar y verificar éxito**

Run: `source .venv/bin/activate && python -m pytest tests/test_mapping_profiles.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add snes_ui/services/input_service.py tests/test_mapping_profiles.py
git commit -m "feat(input): perfiles de mapeo por dispositivo con defaults y migración"
```

---

## Task 4: Migrar el camino de teclado a `MappingProfiles`

Refactor sin cambio de comportamiento: el teclado sigue funcionando, ahora vía
perfiles. Introduce el patrón `_recompute_inputs` (solo teclado por ahora).
Elimina el antiguo `MappingModel`.

**Files:**
- Modify: `snes_ui/services/input_service.py` (eliminar `MappingModel`)
- Modify: `snes_ui/settings.py`
- Modify: `snes_ui/widgets/control_panel.py`
- Modify: `snes_ui/main_window.py`
- Test: `tests/test_input_routing.py`

**Interfaces:**
- Consumes: `MappingProfiles`, `KEYBOARD_KEY`, `Binding`, `key_binding`.
- Produces (settings): `AppSettings.profiles_json() -> str | None`,
  `AppSettings.set_profiles_json(raw: str) -> None`.
- Produces (panel): `ControlPanel(input_service, profiles, device_key, palette, parent=None)`;
  métodos `set_active_device_key(device_key, *, gamepad)`, `refresh_assignments_from_model()`,
  `assign_captured(binding: Binding)`.
- Produces (main_window): `MainWindow._recompute_inputs()`,
  `MainWindow._kbd_pressed: set[str]`, `MainWindow._pad_pressed: set[str]`,
  `MainWindow._active_device_key: str`.

- [ ] **Step 1: Escribir el test que falla (enrutamiento de teclado por perfiles)**

```python
# tests/test_input_routing.py
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
```

- [ ] **Step 2: Ejecutar y verificar fallo**

Run: `source .venv/bin/activate && python -m pytest tests/test_input_routing.py -q`
Expected: FAIL (la firma de `ControlPanel`/atributos aún no existen → error al construir `MainWindow`).

- [ ] **Step 3: `input_service.py` — eliminar `MappingModel`**

Borrar por completo la clase `MappingModel` (ya reemplazada por `MappingProfiles`).
`RETRO_ID` debe seguir disponible en `InputService` (sin cambios).

- [ ] **Step 4: `settings.py` — persistencia por perfiles**

Reemplazar los métodos `mappings()`/`set_mappings()` por:

```python
    # -- perfiles de asignación ---------------------------------------------
    def profiles_json(self) -> str | None:
        raw = self._s.value("input/mappings")
        return raw if isinstance(raw, str) else None

    def set_profiles_json(self, raw: str) -> None:
        self._s.setValue("input/mappings", raw)
```

(Se conserva la clave `"input/mappings"`, de modo que el valor heredado se
migra al cargarse vía `MappingProfiles.from_json`.)

- [ ] **Step 5: `control_panel.py` — usar perfiles del dispositivo activo**

Cambiar el constructor y los puntos que usaban `MappingModel`:

```python
# Firma:
def __init__(self, input_service, profiles, device_key, palette, parent=None):
    ...
    self._profiles = profiles
    self._device_key = device_key
    ...

# Construcción de filas (en _build_config_view):
for spec in SNES_INPUTS:
    row = MappingRow(spec.key, spec.icon, spec.name,
                     self._profiles.label_for(self._device_key, spec.key))
    ...

# Selección de dispositivo activo (nuevo método):
def set_active_device_key(self, device_key: str, *, gamepad: bool) -> None:
    self._profiles.ensure(device_key, gamepad=gamepad)
    self._device_key = device_key
    self.refresh_assignments_from_model()

# Asignación capturada (reemplaza assign_physical):
def assign_captured(self, binding) -> None:
    if not self._listening_key:
        return
    key = self._listening_key
    self._profiles.assign(self._device_key, key, binding)
    self._rows[key].set_assignment(self._profiles.label_for(self._device_key, key))
    self._listening_key = None
    self.listening_changed.emit(False)

# refresh_assignments_from_model:
def refresh_assignments_from_model(self) -> None:
    for key, row in self._rows.items():
        row.set_assignment(self._profiles.label_for(self._device_key, key))
```

Eliminar el antiguo `assign_physical(code)`. El import pasa a
`from ..services.input_service import SNES_INPUTS, InputService, MappingProfiles`.

- [ ] **Step 6: `main_window.py` — perfiles + `_recompute_inputs` (solo teclado)**

Cambios:

```python
# import:
from .services.input_service import InputService, MappingProfiles, KEYBOARD_KEY, key_binding

# en __init__ (reemplazo de self._mapping):
self._profiles = MappingProfiles.from_json(self._settings.profiles_json())
self._profiles.ensure(KEYBOARD_KEY, gamepad=False)
self._active_device_key = KEYBOARD_KEY
self._kbd_pressed: set[str] = set()
self._pad_pressed: set[str] = set()

# construcción del panel:
self._panel = ControlPanel(self._input, self._profiles, KEYBOARD_KEY, palette_for(self._theme))

# nuevo método central de enrutamiento:
def _recompute_inputs(self) -> None:
    union = self._kbd_pressed | self._pad_pressed
    self._panel.set_live_pressed(union)
    for spec in SNES_INPUTS:
        self._core.set_input(spec.retro_id, spec.key in union)

# _handle_key_press (rama de juego):
if self._panel.is_listening:
    self._panel.assign_captured(key_binding(key))
    return True
if not event.isAutoRepeat():
    input_key = self._profiles.input_for_key(KEYBOARD_KEY, key)
    if input_key:
        self._kbd_pressed.add(input_key)
        self._recompute_inputs()
return False

# _handle_key_release:
input_key = self._profiles.input_for_key(KEYBOARD_KEY, event.key())
if input_key:
    self._kbd_pressed.discard(input_key)
    self._recompute_inputs()

# _flow_reset_mappings:
self._profiles.reset(self._active_device_key, gamepad=(self._active_device_key != KEYBOARD_KEY))
self._panel.refresh_assignments_from_model()

# closeEvent (persistencia):
self._settings.set_profiles_json(self._profiles.to_json())
```

Necesario importar `SNES_INPUTS` en `main_window.py`
(`from .services.input_service import ..., SNES_INPUTS`). Eliminar referencias a
`self._mapping`, `assign_physical`, `set_live_pressed(self._pressed_inputs)` y el
antiguo `self._pressed_inputs`.

- [ ] **Step 7: Ejecutar el test de enrutamiento**

Run: `source .venv/bin/activate && python -m pytest tests/test_input_routing.py -q`
Expected: PASS (1 passed).

- [ ] **Step 8: Smoke headless de la app + remapeo de teclado**

Run:
```bash
source .venv/bin/activate && QT_QPA_PLATFORM=offscreen python - <<'PY'
import sys
from PySide6.QtWidgets import QApplication
from snes_ui.main_window import MainWindow
from snes_ui.services.input_service import KEYBOARD_KEY, Binding
app = QApplication(sys.argv)
w = MainWindow()
w._panel._on_listen_requested("a")
w._panel.assign_captured(Binding("key", 0x4A))  # reasignar 'a' a J
assert w._profiles.binding(KEYBOARD_KEY, "a") == Binding("key", 0x4A)
assert w._profiles.input_for_key(KEYBOARD_KEY, 0x4A) == "a"
print("OK teclado por perfiles")
w.close()
PY
```
Expected: `OK teclado por perfiles`.

- [ ] **Step 9: Commit**

```bash
git add snes_ui/services/input_service.py snes_ui/settings.py snes_ui/widgets/control_panel.py snes_ui/main_window.py tests/test_input_routing.py
git commit -m "refactor(input): migrar teclado a MappingProfiles y enrutamiento OR-ready"
```

---

## Task 5: Funciones puras de traducción y captura

**Files:**
- Create: `snes_ui/services/gamepad_service.py`
- Test: `tests/test_gamepad_translate.py`

**Interfaces:**
- Consumes: `Binding`, `pack_hat` (de `input_service`).
- Produces:
  - `PadState(buttons: tuple[int,...], hats: tuple[tuple[int,int],...], axes: tuple[float,...])` (dataclass).
  - `PadInfo(instance_id: int, guid: str, name: str)` (dataclass).
  - `DEADZONE = 0.5`.
  - `translate(state: PadState, profile: dict[str, Binding], deadzone: float = DEADZONE) -> set[str]`.
  - `detect_binding(prev: PadState, cur: PadState, deadzone: float = DEADZONE) -> Binding | None`.

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_gamepad_translate.py
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
```

- [ ] **Step 2: Ejecutar y verificar fallo**

Run: `source .venv/bin/activate && python -m pytest tests/test_gamepad_translate.py -q`
Expected: FAIL con `ModuleNotFoundError: ... gamepad_service`.

- [ ] **Step 3: Crear `gamepad_service.py` (solo lo puro por ahora)**

```python
"""Servicio de gamepad: lectura de mandos vía pygame.joystick.

Las funciones puras de traducción/captura no dependen de pygame y se prueban
con estados sintéticos. El servicio (clase QObject) se añade en una tarea
posterior.
"""
from __future__ import annotations

from dataclasses import dataclass

from .input_service import Binding, pack_hat

DEADZONE = 0.5


@dataclass(frozen=True)
class PadInfo:
    instance_id: int
    guid: str
    name: str


@dataclass(frozen=True)
class PadState:
    buttons: tuple = ()
    hats: tuple = ()
    axes: tuple = ()


def _binding_active(b: Binding, state: PadState, deadzone: float) -> bool:
    if b.kind == "button":
        return b.code < len(state.buttons) and bool(state.buttons[b.code])
    if b.kind == "hat":
        if b.code < len(state.hats):
            x, y = state.hats[b.code]
            return pack_hat(x, y) == b.value
        return False
    if b.kind == "axis":
        if b.code < len(state.axes):
            v = state.axes[b.code]
            return v >= deadzone if b.value >= 0 else v <= -deadzone
        return False
    return False


def translate(state: PadState, profile: dict, deadzone: float = DEADZONE) -> set:
    pressed = {ik for ik, b in profile.items() if _binding_active(b, state, deadzone)}
    # Stick izquierdo (ejes 0/1) espeja el D-Pad.
    if len(state.axes) >= 2:
        x, y = state.axes[0], state.axes[1]
        if x <= -deadzone:
            pressed.add("left")
        elif x >= deadzone:
            pressed.add("right")
        if y <= -deadzone:
            pressed.add("up")
        elif y >= deadzone:
            pressed.add("down")
    return pressed


def detect_binding(prev: PadState, cur: PadState, deadzone: float = DEADZONE) -> "Binding | None":
    for i in range(len(cur.buttons)):
        was = i < len(prev.buttons) and prev.buttons[i]
        if cur.buttons[i] and not was:
            return Binding("button", i)
    for i in range(len(cur.hats)):
        x, y = cur.hats[i]
        if (x, y) != (0, 0):
            return Binding("hat", i, pack_hat(x, y))
    for i in range(len(cur.axes)):
        v = cur.axes[i]
        pv = prev.axes[i] if i < len(prev.axes) else 0.0
        if abs(v) >= deadzone and abs(pv) < deadzone:
            return Binding("axis", i, 1 if v >= 0 else -1)
    return None
```

- [ ] **Step 4: Ejecutar y verificar éxito**

Run: `source .venv/bin/activate && python -m pytest tests/test_gamepad_translate.py -q`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add snes_ui/services/gamepad_service.py tests/test_gamepad_translate.py
git commit -m "feat(gamepad): funciones puras de traducción y captura de entradas"
```

---

## Task 6: `GamepadService` con costura de backend

**Files:**
- Modify: `snes_ui/services/gamepad_service.py`
- Test: `tests/test_gamepad_service.py`

**Interfaces:**
- Consumes: `PadState`, `PadInfo`, `translate`, `detect_binding`, `ConnectionState` (de `..state`).
- Produces:
  - Protocolo de backend (duck-typed): `init() -> bool`, `pump() -> None`,
    `devices() -> list[PadInfo]`, `read(instance_id: int) -> PadState | None`.
  - `GamepadService(QObject, backend=None, parent=None)` con:
    - señales `devices_changed(list)`, `connection_changed(object)`,
      `pressed_changed(set)`, `binding_captured(object)`.
    - `start()`, `stop()`.
    - `set_active(instance_id: int | None, profile: dict) -> None`.
    - `set_capture(enabled: bool) -> None`.
    - `poll_once()` (un tick; usado por el QTimer y por tests).
    - propiedades `available: bool`, `devices: list[PadInfo]`.

- [ ] **Step 1: Escribir el test que falla (con backend falso)**

```python
# tests/test_gamepad_service.py
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
```

- [ ] **Step 2: Ejecutar y verificar fallo**

Run: `source .venv/bin/activate && python -m pytest tests/test_gamepad_service.py -q`
Expected: FAIL con `ImportError: cannot import name 'GamepadService'`.

- [ ] **Step 3: Añadir `_PygamePadBackend` y `GamepadService` a `gamepad_service.py`**

Añadir imports al inicio del archivo:

```python
import os

from PySide6.QtCore import Qt, QObject, QTimer, Signal

from ..state import ConnectionState
```

Añadir al final del archivo:

```python
class _PygamePadBackend:
    """Backend real sobre pygame.joystick (hilo principal, video dummy)."""

    def __init__(self) -> None:
        self._pg = None
        self._sticks: dict[int, object] = {}

    def init(self) -> bool:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        try:
            import pygame
            pygame.init()
            pygame.joystick.init()
        except Exception:
            return False
        self._pg = pygame
        return True

    def pump(self) -> None:
        if self._pg is None:
            return
        self._pg.event.pump()
        # Mantener objetos Joystick vivos para lectura.
        count = self._pg.joystick.get_count()
        live: dict[int, object] = {}
        for i in range(count):
            js = self._pg.joystick.Joystick(i)
            try:
                js.init()
            except Exception:
                continue
            live[js.get_instance_id()] = js
        self._sticks = live

    def devices(self) -> list:
        out = []
        for iid, js in self._sticks.items():
            try:
                out.append(PadInfo(iid, js.get_guid(), js.get_name()))
            except Exception:
                continue
        return out

    def read(self, instance_id: int):
        js = self._sticks.get(instance_id)
        if js is None:
            return None
        try:
            buttons = tuple(js.get_button(i) for i in range(js.get_numbuttons()))
            hats = tuple(js.get_hat(i) for i in range(js.get_numhats()))
            axes = tuple(js.get_axis(i) for i in range(js.get_numaxes()))
            return PadState(buttons, hats, axes)
        except Exception:
            return None


class GamepadService(QObject):
    """Detecta mandos, traduce su estado a entradas SNES y captura bindings."""

    devices_changed = Signal(list)
    connection_changed = Signal(object)
    pressed_changed = Signal(set)
    binding_captured = Signal(object)

    def __init__(self, backend=None, parent=None) -> None:
        super().__init__(parent)
        self._backend = backend if backend is not None else _PygamePadBackend()
        self._available = bool(self._backend.init())
        self._devices: list = []
        self._active_iid = None
        self._profile: dict = {}
        self._capture = False
        self._prev_state = None
        self._pressed: set = set()
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self.poll_once)

    @property
    def available(self) -> bool:
        return self._available

    @property
    def devices(self) -> list:
        return list(self._devices)

    def start(self) -> None:
        if self._available:
            self._timer.start(16)

    def stop(self) -> None:
        self._timer.stop()

    def set_active(self, instance_id, profile: dict) -> None:
        self._active_iid = instance_id
        self._profile = profile
        self._prev_state = None
        if self._pressed:
            self._pressed = set()
            self.pressed_changed.emit(set())

    def set_capture(self, enabled: bool) -> None:
        self._capture = enabled
        self._prev_state = None

    def poll_once(self) -> None:
        if not self._available:
            return
        self._backend.pump()
        self._refresh_devices()
        state = self._backend.read(self._active_iid) if self._active_iid is not None else None
        if self._capture:
            self._do_capture(state)
        else:
            self._do_feed(state)

    def _refresh_devices(self) -> None:
        devices = self._backend.devices()
        ids = {d.instance_id for d in devices}
        prev_ids = {d.instance_id for d in self._devices}
        if ids != prev_ids:
            self._devices = devices
            self.devices_changed.emit(list(devices))
            if self._active_iid is not None and self._active_iid not in ids:
                self.connection_changed.emit(ConnectionState.DISCONNECTED)
            elif devices:
                self.connection_changed.emit(ConnectionState.CONNECTED)

    def _do_feed(self, state) -> None:
        pressed = translate(state, self._profile) if state is not None else set()
        if pressed != self._pressed:
            self._pressed = pressed
            self.pressed_changed.emit(set(pressed))

    def _do_capture(self, state) -> None:
        if state is None:
            return
        if self._prev_state is None:
            self._prev_state = state
            return
        b = detect_binding(self._prev_state, state)
        self._prev_state = state
        if b is not None:
            self.binding_captured.emit(b)
```

- [ ] **Step 4: Ejecutar y verificar éxito**

Run: `source .venv/bin/activate && python -m pytest tests/test_gamepad_service.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Smoke headless del backend real (0 mandos)**

Run:
```bash
source .venv/bin/activate && python - <<'PY'
import sys
from PySide6.QtWidgets import QApplication
from snes_ui.services.gamepad_service import GamepadService
app = QApplication(sys.argv)
svc = GamepadService()
print("available:", svc.available)
svc.poll_once()
print("devices:", svc.devices)
svc.stop()
print("OK backend real sin mandos")
PY
```
Expected: imprime `available: True`, `devices: []`, `OK backend real sin mandos` (sin excepciones).

- [ ] **Step 6: Commit**

```bash
git add snes_ui/services/gamepad_service.py tests/test_gamepad_service.py
git commit -m "feat(gamepad): GamepadService con enumeración, hot-plug, feed y captura"
```

---

## Task 7: Integrar `GamepadService` en `MainWindow`

**Files:**
- Modify: `snes_ui/main_window.py`
- Modify: `snes_ui/widgets/control_panel.py`
- Test: `tests/test_input_routing.py` (añadir casos)

**Interfaces:**
- Consumes: `GamepadService`, `MappingProfiles`, `KEYBOARD_KEY`, `Binding`,
  `ControlPanel.set_active_device_key`, `ControlPanel.assign_captured`.
- Produces: `MainWindow._on_pad_pressed(set)`, `MainWindow._on_device_changed(name)`
  (re-implementado para mando), `MainWindow._gamepad: GamepadService`.

- [ ] **Step 1: Escribir el test que falla (OR-combine teclado + mando)**

Añadir a `tests/test_input_routing.py`:

```python
from snes_ui.services.input_service import KEYBOARD_KEY


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
```

- [ ] **Step 2: Ejecutar y verificar fallo**

Run: `source .venv/bin/activate && python -m pytest tests/test_input_routing.py::test_or_combine_keyboard_and_pad -q`
Expected: FAIL con `AttributeError: 'MainWindow' object has no attribute '_on_pad_pressed'`.

- [ ] **Step 3: `control_panel.py` — exponer dispositivos de mando en el combo**

Añadir método para poblar el combo con teclado + mandos detectados:

```python
def set_gamepad_devices(self, names: list[str]) -> None:
    self._combo.blockSignals(True)
    current = self._combo.currentText()
    self._combo.clear()
    self._combo.addItems(["Keyboard", *names])
    idx = self._combo.findText(current)
    self._combo.setCurrentIndex(idx if idx >= 0 else 0)
    self._combo.blockSignals(False)
```

- [ ] **Step 4: `main_window.py` — instanciar y cablear `GamepadService`**

```python
# import:
from .services.gamepad_service import GamepadService

# en __init__ (tras crear self._panel y self._input):
self._gamepad = GamepadService(parent=self)
self._pad_by_name: dict[str, object] = {}   # nombre -> PadInfo

# en _connect_signals:
self._gamepad.pressed_changed.connect(self._on_pad_pressed)
self._gamepad.binding_captured.connect(self._on_pad_binding_captured)
self._gamepad.devices_changed.connect(self._on_pad_devices_changed)
self._gamepad.connection_changed.connect(self._panel.update_connection)

# IMPORTANTE: el combo de dispositivos lo gobierna ahora el gamepad. Eliminar
# la conexión existente que lo repoblaba solo con teclado (la borraría los
# mandos):
#   QUITAR  self._input.devices_changed.connect(self._panel.update_devices)
# y repuntar el botón ⟳ para re-enumerar mandos en lugar de InputService:
#   self._panel.refresh_requested.connect(self._gamepad.poll_once)
# (deja conectado self._input.connection_changed -> update_connection: el
# gamepad lo sobrescribe cuando hay mando activo).

# arrancar el servicio (al final de __init__):
self._gamepad.start()

# manejadores nuevos:
def _on_pad_pressed(self, pressed: set) -> None:
    self._pad_pressed = set(pressed)
    self._recompute_inputs()

def _on_pad_devices_changed(self, devices: list) -> None:
    self._pad_by_name = {d.name: d for d in devices}
    self._panel.set_gamepad_devices([d.name for d in devices])
    # Auto-seleccionar el primer mando si seguimos en teclado.
    if self._active_device_key == KEYBOARD_KEY and devices:
        self._panel.set_current_device(devices[0].name)

def _on_pad_binding_captured(self, binding) -> None:
    if self._panel.is_listening:
        self._panel.assign_captured(binding)
    self._gamepad.set_capture(False)
```

- [ ] **Step 5: `main_window.py` — reescribir `_on_device_changed` para mando/teclado**

```python
def _on_device_changed(self, name: str) -> None:
    # El teclado siempre alimenta el juego; este selector elige el mando activo
    # y qué perfil edita el panel.
    if name == "Keyboard" or name not in self._pad_by_name:
        self._active_device_key = KEYBOARD_KEY
        self._panel.set_active_device_key(KEYBOARD_KEY, gamepad=False)
        self._gamepad.set_active(None, {})
        self._pad_pressed = set()
        self._recompute_inputs()
        return
    info = self._pad_by_name[name]
    self._active_device_key = info.guid
    self._profiles.ensure(info.guid, gamepad=True)
    self._panel.set_active_device_key(info.guid, gamepad=True)
    self._gamepad.set_active(info.instance_id, self._profiles.profile(info.guid))
```

- [ ] **Step 6: `main_window.py` — captura por mando al escuchar una fila**

En `_handle_key_press`, la rama de escucha de teclado ya asigna teclas. Para que
el mando capture cuando el dispositivo activo es un mando, activar el modo
captura cuando una fila empieza a escuchar. Conectar la señal del panel:

```python
# en _connect_signals:
self._panel.listening_changed.connect(self._on_listening_changed)

# manejador:
def _on_listening_changed(self, listening: bool) -> None:
    # Captura por mando solo si el dispositivo activo es un mando.
    self._gamepad.set_capture(listening and self._active_device_key != KEYBOARD_KEY)
```

(Si el dispositivo activo es un mando, las teclas no deben asignarse: en
`_handle_key_press`, la rama `if self._panel.is_listening:` debe ignorarse para
mando. Cambiar a:)

```python
if self._panel.is_listening:
    if self._active_device_key == KEYBOARD_KEY:
        self._panel.assign_captured(key_binding(key))
    return True
```

- [ ] **Step 7: `main_window.py` — detener el servicio al cerrar**

En `closeEvent`, antes de `super().closeEvent(event)`:

```python
self._gamepad.stop()
```

- [ ] **Step 8: Ejecutar los tests de enrutamiento**

Run: `source .venv/bin/activate && python -m pytest tests/test_input_routing.py -q`
Expected: PASS (2 passed).

- [ ] **Step 9: Suite completa + smoke headless de arranque**

Run: `source .venv/bin/activate && python -m pytest -q`
Expected: todos los tests PASS.

Run:
```bash
source .venv/bin/activate && QT_QPA_PLATFORM=offscreen python - <<'PY'
import sys
from PySide6.QtWidgets import QApplication
from snes_ui.main_window import MainWindow
app = QApplication(sys.argv)
w = MainWindow()
print("gamepad available:", w._gamepad.available, "| devices:", w._gamepad.devices)
w.close()
print("OK arranque con GamepadService")
PY
```
Expected: `OK arranque con GamepadService` sin excepciones.

- [ ] **Step 10: Commit**

```bash
git add snes_ui/main_window.py snes_ui/widgets/control_panel.py tests/test_input_routing.py
git commit -m "feat(gamepad): integrar mando en MainWindow (OR-combine, captura, conexión)"
```

---

## Notas de verificación final (con mando físico, manual)

Estas comprobaciones requieren un mando real y las hace la persona usuaria:
- Conectar un mando → aparece en el combo y el indicador pasa a "Conectado".
- Jugar con el mando y con el teclado simultáneamente (ambos mueven).
- Reasignar un botón del mando desde el panel y verificar que surte efecto.
- Desconectar el mando a media partida → "Desconectado" y el teclado sigue.
- Reiniciar la app → el perfil del mando (por GUID) se conserva.
