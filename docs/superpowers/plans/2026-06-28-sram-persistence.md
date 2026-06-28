# SRAM Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persistir el SRAM (RAM de batería del cartucho) de cada juego en un `.srm`, de modo que el guardado interno de los juegos sobreviva entre sesiones.

**Architecture:** El core expone el SRAM como `bytes` (`get_sram`/`load_sram`); un servicio `SramStore` hace el IO de archivos bajo `AppDataLocation/sram/`; `SessionController` orquesta cuándo cargar (al iniciar) y volcar (al salir, cambiar de juego y cerrar la app). Patrón frontend-managed de libretro, como RetroArch.

**Tech Stack:** Python 3.14, PySide6 (`QStandardPaths`), `ctypes` (binding libretro), pytest.

## Global Constraints

- Aislamiento estricto UI ↔ core: la UI solo conoce el ABC `EmulatorCore`; el IO de SRAM vive en un servicio, no en widgets.
- Strings de cara al usuario y comentarios en **español** (consistencia con el repo).
- Sin dependencias nuevas. Sin timers ni autoguardado periódico.
- Nunca lanzar por errores de IO de SRAM: registrar en `stderr` y continuar; jamás bloquear el cierre de la app.
- Ubicación del `.srm`: `AppDataLocation/sram/<rom saneado>.srm`.
- Tests headless (conftest fuerza offscreen y aísla QSettings).

---

### Task 1: Servicio `SramStore`

**Files:**
- Create: `snes_ui/services/sram_service.py`
- Test: `tests/test_sram_store.py`

**Interfaces:**
- Consumes: nada (servicio autocontenido).
- Produces:
  - `SramStore(base_dir: Path | str | None = None)`
  - `SramStore.path_for(rom_name: str) -> Path`
  - `SramStore.read(rom_name: str) -> bytes`  (falta o error → `b""`)
  - `SramStore.write(rom_name: str, blob: bytes) -> None`  (blob vacío → no escribe; escritura atómica)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sram_store.py
from pathlib import Path

from snes_ui.services.sram_service import SramStore


def test_write_then_read_roundtrip(tmp_path):
    store = SramStore(tmp_path)
    store.write("Super Mario Kart.sfc", b"\x01\x02\x03")
    assert store.read("Super Mario Kart.sfc") == b"\x01\x02\x03"


def test_read_missing_returns_empty(tmp_path):
    store = SramStore(tmp_path)
    assert store.read("nope.sfc") == b""


def test_write_empty_creates_no_file(tmp_path):
    store = SramStore(tmp_path)
    store.write("game.sfc", b"")
    assert not store.path_for("game.sfc").exists()


def test_write_is_atomic_no_tmp_residue(tmp_path):
    store = SramStore(tmp_path)
    store.write("game.sfc", b"abcd")
    p = store.path_for("game.sfc")
    assert p.read_bytes() == b"abcd"
    # no debe quedar el temporal
    assert not list(p.parent.glob("*.tmp"))


def test_overwrite_replaces_content(tmp_path):
    store = SramStore(tmp_path)
    store.write("game.sfc", b"old")
    store.write("game.sfc", b"newer")
    assert store.read("game.sfc") == b"newer"


def test_filename_is_sanitized(tmp_path):
    store = SramStore(tmp_path)
    p = store.path_for("Legend/of:Zelda.sfc")
    assert p.suffix == ".srm"
    assert "/" not in p.name and ":" not in p.name
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sram_store.py -v`
Expected: FAIL (ModuleNotFoundError: `snes_ui.services.sram_service`).

- [ ] **Step 3: Write minimal implementation**

```python
# snes_ui/services/sram_service.py
"""Persistencia del SRAM (RAM de batería del cartucho) en archivos .srm.

Espejo minimalista de SaveService: un archivo por ROM bajo
``AppDataLocation/sram/``. En libretro el *frontend* es responsable de volcar y
cargar el SRAM (el core de snes9x delega en él), igual que hace RetroArch.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths


def _sanitize(name: str) -> str:
    """Nombre de archivo seguro a partir del nombre de la ROM (sin extensión)."""
    stem = Path(name).stem
    cleaned = re.sub(r"[^\w.\- ]+", "_", stem).strip()
    return cleaned or "rom"


class SramStore:
    """Lee/escribe el .srm de cada ROM bajo ``AppDataLocation/sram/``."""

    def __init__(self, base_dir: Path | str | None = None) -> None:
        if base_dir is None:
            root = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppDataLocation
            )
            base_dir = Path(root) / "sram"
        self._base = Path(base_dir)

    def path_for(self, rom_name: str) -> Path:
        return self._base / f"{_sanitize(rom_name)}.srm"

    def read(self, rom_name: str) -> bytes:
        path = self.path_for(rom_name)
        try:
            return path.read_bytes()
        except FileNotFoundError:
            return b""
        except OSError as exc:
            print(f"[sram] no se pudo leer {path}: {exc}", file=sys.stderr)
            return b""

    def write(self, rom_name: str, blob: bytes) -> None:
        if not blob:
            return
        path = self.path_for(rom_name)
        tmp = path.with_name(path.name + ".tmp")
        try:
            self._base.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(blob)
            os.replace(tmp, path)
        except OSError as exc:
            print(f"[sram] no se pudo escribir {path}: {exc}", file=sys.stderr)
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sram_store.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add snes_ui/services/sram_service.py tests/test_sram_store.py
git commit -m "feat(sram): SramStore para persistir .srm bajo AppDataLocation/sram

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Contrato `get_sram`/`load_sram` en el ABC

**Files:**
- Modify: `snes_ui/core/adapter.py` (clase `EmulatorCore`, tras `stop_audio`, ~línea 94)
- Test: `tests/test_sram_core.py`

**Interfaces:**
- Consumes: nada.
- Produces (en `EmulatorCore`, heredado por todas las subclases salvo override):
  - `get_sram(self) -> bytes`  (default `b""`)
  - `load_sram(self, blob: bytes) -> None`  (default no-op)

> **Nota de diseño:** el spec los describía como abstractos, pero se implementan como **no-op por defecto en el ABC**, siguiendo el mismo patrón que los métodos de audio (`start_audio`, etc.). Así `MockEmulatorCore` no necesita cambios y hereda el no-op; solo `LibretroCore` los sobreescribe (Task 3).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sram_core.py
from snes_ui.core.adapter import MockEmulatorCore


def test_mock_get_sram_is_empty():
    assert MockEmulatorCore().get_sram() == b""


def test_mock_load_sram_is_noop():
    core = MockEmulatorCore()
    # No debe lanzar ni tener efecto observable.
    assert core.load_sram(b"\x00\x01") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sram_core.py -v`
Expected: FAIL (`AttributeError: 'MockEmulatorCore' object has no attribute 'get_sram'`).

- [ ] **Step 3: Write minimal implementation**

En `snes_ui/core/adapter.py`, dentro de `class EmulatorCore`, justo después del método `stop_audio` (antes de que termine la clase, ~línea 94):

```python
    # -- SRAM (RAM de batería del cartucho); no-op por defecto --------------
    def get_sram(self) -> bytes:
        """Copia del SRAM del cartucho, o ``b''`` si no hay/aplica."""
        return b""

    def load_sram(self, blob: bytes) -> None:
        """Vuelca un SRAM previamente guardado en el buffer del cartucho."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sram_core.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add snes_ui/core/adapter.py tests/test_sram_core.py
git commit -m "feat(sram): contrato get_sram/load_sram en EmulatorCore (no-op por defecto)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Implementación de SRAM en `LibretroCore`

**Files:**
- Modify: `snes_ui/core/adapter.py` (constante de módulo; `LibretroCore._configure_signatures`; nuevos métodos `get_sram`/`load_sram` en `LibretroCore`)

**Interfaces:**
- Consumes: `EmulatorCore.get_sram`/`load_sram` (Task 2, los sobreescribe).
- Produces: `LibretroCore.get_sram() -> bytes`, `LibretroCore.load_sram(blob: bytes) -> None` reales contra `retro_get_memory_data`/`retro_get_memory_size`.

> **Verificación:** sin test unitario (requiere el `.dylib` real). Se valida manualmente en el Step final.

- [ ] **Step 1: Añadir la constante de módulo**

En `snes_ui/core/adapter.py`, junto al resto de constantes del módulo (cerca de `NATIVE_WIDTH`/`NATIVE_HEIGHT`, parte superior del archivo), añade:

```python
RETRO_MEMORY_SAVE_RAM = 0  # id de RETRO_MEMORY_* para la RAM de batería
```

- [ ] **Step 2: Declarar las firmas ctypes**

En `LibretroCore._configure_signatures` (junto a las demás firmas, ~líneas 289-297), añade:

```python
        self._lib.retro_get_memory_data.argtypes = [ctypes.c_uint]
        self._lib.retro_get_memory_data.restype = ctypes.c_void_p
        self._lib.retro_get_memory_size.argtypes = [ctypes.c_uint]
        self._lib.retro_get_memory_size.restype = ctypes.c_size_t
```

- [ ] **Step 3: Implementar los métodos en `LibretroCore`**

En `class LibretroCore`, junto a `save_state`/`load_state` (~líneas 415-428), añade:

```python
    def get_sram(self) -> bytes:
        if not self._game_loaded:
            return b""
        size = int(self._lib.retro_get_memory_size(RETRO_MEMORY_SAVE_RAM))
        if size <= 0:
            return b""
        ptr = self._lib.retro_get_memory_data(RETRO_MEMORY_SAVE_RAM)
        if not ptr:
            return b""
        return ctypes.string_at(ptr, size)

    def load_sram(self, blob: bytes) -> None:
        if not blob or not self._game_loaded:
            return
        size = int(self._lib.retro_get_memory_size(RETRO_MEMORY_SAVE_RAM))
        ptr = self._lib.retro_get_memory_data(RETRO_MEMORY_SAVE_RAM)
        if size <= 0 or not ptr:
            return
        n = min(len(blob), size)
        if n != size:
            print(
                f"[adapter] tamaño de SRAM no coincide: archivo={len(blob)} "
                f"core={size}; se copian {n} bytes.",
                file=sys.stderr,
            )
        ctypes.memmove(ptr, blob, n)
```

- [ ] **Step 4: Verificar que la suite sigue verde**

Run: `python -m pytest -q`
Expected: PASS (sin regresiones).

- [ ] **Step 5: Verificación manual (con el `.dylib` real)**

1. `python main.py`, abre `ROMS/SuperMarioKart.sfc`.
2. Juega lo suficiente para que el juego guarde en SRAM (p. ej. completa una contrarreloj para grabar un récord, o entra al menú de records).
3. Cierra la sesión (Ctrl+W) o la app.
4. Confirma que existe `<AppDataLocation>/sram/SuperMarioKart.srm` y que no está vacío.
   - macOS típico: `~/Library/Application Support/<App>/sram/SuperMarioKart.srm`.
5. Reabre la ROM y comprueba que el récord/guardado persiste.

- [ ] **Step 6: Commit**

```bash
git add snes_ui/core/adapter.py
git commit -m "feat(sram): LibretroCore lee/escribe SAVE_RAM vía retro_get_memory_*

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Orquestación en `SessionController`

**Files:**
- Modify: `snes_ui/core/session.py` (import; `__init__`; `begin_loading`; `finish_loading`; `quit_session`; nuevos `_flush_sram`/`flush_sram`)
- Test: `tests/test_sram_session.py`

**Interfaces:**
- Consumes: `SramStore` (Task 1); `EmulatorCore.get_sram`/`load_sram` (Tasks 2-3).
- Produces:
  - `SessionController(core, parent=None, sram_store: SramStore | None = None)`
  - `SessionController.flush_sram() -> None` (público, para el cierre de la app)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sram_session.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sram_session.py -v`
Expected: FAIL (`TypeError: __init__() got an unexpected keyword argument 'sram_store'`).

- [ ] **Step 3: Implement — import y `__init__`**

En `snes_ui/core/session.py`, añade el import junto a los demás (arriba del archivo):

```python
from ..services.sram_service import SramStore
```

Y cambia la firma e inicialización de `__init__`:

```python
    def __init__(
        self,
        core: EmulatorCore,
        parent: QObject | None = None,
        sram_store: SramStore | None = None,
    ) -> None:
        super().__init__(parent)
        self._core = core
        self._sram = sram_store if sram_store is not None else SramStore()
        self._state = SessionState.EMPTY
        self._rom_path: str | None = None
        self._rom_name: str = ""
        self._dirty = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
```

- [ ] **Step 4: Implement — helpers de volcado**

Añade estos dos métodos a `SessionController` (p. ej. junto a las transiciones):

```python
    def _flush_sram(self) -> None:
        """Vuelca el SRAM del juego actual al disco (si hay ROM)."""
        if self._rom_name:
            self._sram.write(self._rom_name, self._core.get_sram())

    def flush_sram(self) -> None:
        """Punto de volcado público (lo usa el cierre de la app)."""
        self._flush_sram()
```

- [ ] **Step 5: Implement — enganches de carga y cambio de juego**

En `begin_loading`, vuelca el SRAM del juego anterior **antes** de reasignar la ROM:

```python
    def begin_loading(self, path: str) -> None:
        """Entra al estado cargando mostrando el nombre del archivo."""
        import os
        # Vuelca el SRAM del juego anterior (si lo hay) antes de cambiar de ROM:
        # al cargar otro juego el core descarga el actual y se perdería.
        self._flush_sram()
        self._rom_path = path
        self._rom_name = os.path.basename(path)
        self.rom_changed.emit(self._rom_name)
        self._set_state(SessionState.LOADING)
```

En `finish_loading`, carga el SRAM tras un `load_game` correcto:

```python
    def finish_loading(self) -> bool:
        """Valida la ROM via el nucleo y transiciona a ejecutando o error."""
        if not self._rom_path:
            self.fail("No se especificó ninguna ROM.")
            return False
        ok = self._core.load_game(self._rom_path)
        if not ok:
            self.fail(
                "El núcleo rechazó la ROM. Verifique que el archivo sea "
                "una imagen SNES válida (.sfc o .smc) y no esté dañado."
            )
            return False
        # Carga el SRAM guardado del cartucho (si existe) en el buffer del core.
        saved = self._sram.read(self._rom_name)
        if saved:
            self._core.load_sram(saved)
        self._set_dirty(False)
        self._set_state(SessionState.RUNNING)
        fps = self._core.av_info().fps or 60.0
        self._timer.start(int(1000 / fps))
        self._core.start_audio()
        return True
```

En `quit_session`, vuelca **antes** de `unload`:

```python
    def quit_session(self) -> None:
        """Cierra la sesion activa y vuelve al estado vacio."""
        self._timer.stop()
        self._flush_sram()
        self._core.unload()
        self._rom_path = None
        self._rom_name = ""
        self._set_dirty(False)
        self._set_state(SessionState.EMPTY)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_sram_session.py -v`
Expected: PASS (5 passed).

- [ ] **Step 7: Commit**

```bash
git add snes_ui/core/session.py tests/test_sram_session.py
git commit -m "feat(sram): SessionController carga al iniciar y vuelca al salir/cambiar

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Cableado en `MainWindow` y volcado al cerrar

**Files:**
- Modify: `snes_ui/main_window.py` (import; crear `self._sram`; pasar a `SessionController`; volcar en `closeEvent`)
- Test: `tests/test_sram_mainwindow.py`

**Interfaces:**
- Consumes: `SramStore` (Task 1), `SessionController(..., sram_store=...)` y `flush_sram()` (Task 4).
- Produces: `MainWindow._sram` (instancia compartida), volcado garantizado en `closeEvent`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sram_mainwindow.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sram_mainwindow.py -v`
Expected: FAIL (`AttributeError: 'MainWindow' object has no attribute '_sram'`).

- [ ] **Step 3: Implement — import y construcción**

En `snes_ui/main_window.py`, añade el import junto a los demás de servicios:

```python
from .services.sram_service import SramStore
```

Crea el store **antes** de construir el `SessionController` (línea 72) y pásalo. Sustituye:

```python
        self._session = SessionController(self._core, self)
```

por:

```python
        self._sram = SramStore()
        self._session = SessionController(self._core, self, sram_store=self._sram)
```

- [ ] **Step 4: Implement — volcado en `closeEvent`**

En `closeEvent` (~línea 568), vuelca el SRAM **antes** de `shutdown`. Localiza el bloque:

```python
        shutdown = getattr(self._core, "shutdown", None)
        if callable(shutdown):
            shutdown()
        super().closeEvent(event)
```

y antepón el volcado:

```python
        self._session.flush_sram()
        shutdown = getattr(self._core, "shutdown", None)
        if callable(shutdown):
            shutdown()
        super().closeEvent(event)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_sram_mainwindow.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS (toda la suite, incluidas las nuevas, sin regresiones).

- [ ] **Step 7: Commit**

```bash
git add snes_ui/main_window.py tests/test_sram_mainwindow.py
git commit -m "feat(sram): MainWindow comparte SramStore y vuelca al cerrar

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notas de cobertura del spec

- Contrato del core (`get_sram`/`load_sram`) → Tasks 2 (ABC/Mock) y 3 (LibretroCore).
- `SramStore` (ubicación, read/write, atómico, vacío→no escribe) → Task 1.
- Orquestación (cargar al iniciar; volcar al salir, cambiar de juego, cerrar app) → Tasks 4 y 5.
- Relación con save states (independientes) → sin cambios; no requiere tarea.
- Manejo de errores (IO no lanza, tamaño incompatible copia el mínimo) → Tasks 1 y 3.
- Testing → tests en Tasks 1, 2, 4, 5; `LibretroCore` por verificación manual (Task 3).
