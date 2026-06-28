# Biblioteca de ROMs — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir una biblioteca de ROMs que se muestra en el escenario vacío como una cuadrícula de juegos escaneados desde carpetas configurables, y desde la que se lanza un juego.

**Architecture:** Un `LibraryService` (lógica pura) escanea carpetas (persistidas en `AppSettings`) de forma síncrona y devuelve `GameEntry`s; un `LibraryView` (QWidget con un `QListWidget` en modo icono) los presenta en el estado `EMPTY` del `GameStage`; `MainWindow` cablea la selección a `SessionController.begin_loading`. Sin DB, sin hashes, sin caché en disco de la lista.

**Tech Stack:** Python 3.14, PySide6 (QtWidgets, QListWidget IconMode), pytest (headless con `QT_QPA_PLATFORM=offscreen`, QSettings redirigido por `tests/conftest.py`).

## Global Constraints

- Idioma de strings de usuario y comentarios: **español** (convención del repo).
- Nada de dependencias nuevas: solo stdlib + PySide6 ya presentes.
- Colores siempre desde `theme.py` (la paleta); ningún color hardcodeado en widgets.
- Persistencia vía el `AppSettings` existente (QSettings); no se crean archivos nuevos en disco.
- Extensiones de ROM soportadas: `.sfc` y `.smc` (insensible a mayúsculas).
- Tests herméticos: `conftest.py` ya fuerza offscreen y redirige QSettings a un temporal.

---

### Task 1: Persistencia de carpetas en AppSettings

**Files:**
- Modify: `snes_ui/settings.py`
- Test: `tests/test_settings.py` (crear)

**Interfaces:**
- Consumes: nada.
- Produces:
  - `AppSettings.library_folders() -> list[str]` (por defecto `["ROMS"]`)
  - `AppSettings.set_library_folders(folders: list[str]) -> None`
  Se serializa como JSON string en la clave `library/folders` (robusto entre formatos NativeFormat/IniFormat, igual que `input/mappings`).

- [ ] **Step 1: Write the failing test**

Crear `tests/test_settings.py`:

```python
from snes_ui.settings import AppSettings


def test_library_folders_default(qapp):
    s = AppSettings()
    # Sin valor previo (QSettings redirigido a temp por conftest).
    assert s.library_folders() == ["ROMS"]


def test_library_folders_roundtrip(qapp):
    s = AppSettings()
    s.set_library_folders(["ROMS", "/tmp/juegos"])
    assert AppSettings().library_folders() == ["ROMS", "/tmp/juegos"]


def test_library_folders_ignores_corrupt(qapp):
    s = AppSettings()
    s._s.setValue("library/folders", "no-es-json")
    assert s.library_folders() == ["ROMS"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_settings.py -v`
Expected: FAIL con `AttributeError: 'AppSettings' object has no attribute 'library_folders'`.

- [ ] **Step 3: Write minimal implementation**

En `snes_ui/settings.py`, añadir `import json` al inicio (junto a los imports) y añadir estos métodos dentro de la clase `AppSettings` (tras `set_profiles_json`):

```python
    # -- biblioteca de ROMs --------------------------------------------------
    def library_folders(self) -> list[str]:
        raw = self._s.value("library/folders")
        if isinstance(raw, str):
            try:
                val = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                val = None
            if isinstance(val, list):
                return [str(x) for x in val]
        return ["ROMS"]

    def set_library_folders(self, folders: list[str]) -> None:
        self._s.setValue("library/folders", json.dumps(list(folders)))
```

El import al inicio del archivo:

```python
import json

from PySide6.QtCore import QSettings, QByteArray
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_settings.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add snes_ui/settings.py tests/test_settings.py
git commit -m "feat(library): persistencia de carpetas en AppSettings"
```

---

### Task 2: LibraryService y modelo GameEntry

**Files:**
- Create: `snes_ui/services/library_service.py`
- Test: `tests/test_library_service.py` (crear)

**Interfaces:**
- Consumes: `AppSettings.library_folders()` / `set_library_folders()` (Task 1).
- Produces:
  - `clean_name(filename: str) -> str` (función de módulo)
  - `@dataclass(frozen=True) GameEntry` con campos `path: Path`, `display_name: str`, `folder: str`
  - `LibraryService(settings: AppSettings)` con:
    - `folders() -> list[str]`
    - `add_folder(path: str) -> None`
    - `remove_folder(path: str) -> None`
    - `scan() -> list[GameEntry]` (ordenada por `display_name`, sin duplicados por ruta absoluta)

- [ ] **Step 1: Write the failing test**

Crear `tests/test_library_service.py`:

```python
from pathlib import Path

import pytest

from snes_ui.settings import AppSettings
from snes_ui.services.library_service import (
    LibraryService,
    GameEntry,
    clean_name,
)


def test_clean_name():
    assert clean_name("Super_Mario_Kart.sfc") == "Super Mario Kart"
    assert clean_name("TopGear.smc") == "TopGear"
    assert clean_name("Donkey.Kong.Country.sfc") == "Donkey Kong Country"


@pytest.fixture
def service(qapp, tmp_path):
    s = AppSettings()
    s.set_library_folders([])           # parte de cero, sin la carpeta ROMS por defecto
    return LibraryService(s)


def test_scan_finds_roms_and_ignores_others(service, tmp_path):
    (tmp_path / "Zelda.sfc").write_bytes(b"x")
    (tmp_path / "Metroid.smc").write_bytes(b"x")
    (tmp_path / "leeme.txt").write_text("hola")
    service.add_folder(str(tmp_path))

    games = service.scan()
    names = [g.display_name for g in games]
    assert names == ["Metroid", "Zelda"]            # orden alfabético
    assert all(isinstance(g, GameEntry) for g in games)
    assert all(g.path.suffix.lower() in (".sfc", ".smc") for g in games)


def test_scan_is_recursive_and_sets_folder(service, tmp_path):
    sub = tmp_path / "snes"
    sub.mkdir()
    (sub / "Earthbound.sfc").write_bytes(b"x")
    service.add_folder(str(tmp_path))

    games = service.scan()
    assert len(games) == 1
    assert games[0].folder == "snes"


def test_scan_dedups_overlapping_folders(service, tmp_path):
    (tmp_path / "Contra.sfc").write_bytes(b"x")
    service.add_folder(str(tmp_path))
    service.add_folder(str(tmp_path))            # duplicada
    assert len(service.scan()) == 1


def test_scan_ignores_missing_folder(service, tmp_path):
    service.add_folder(str(tmp_path / "no-existe"))
    assert service.scan() == []


def test_add_remove_folder_persists(service, tmp_path):
    service.add_folder(str(tmp_path))
    assert str(tmp_path) in service.folders()
    service.remove_folder(str(tmp_path))
    assert str(tmp_path) not in service.folders()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_library_service.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'snes_ui.services.library_service'`.

- [ ] **Step 3: Write minimal implementation**

Crear `snes_ui/services/library_service.py`:

```python
"""Gestor de biblioteca: escaneo síncrono de ROMs en carpetas configurables.

Sin base de datos ni caché en disco: la lista de carpetas se persiste vía
``AppSettings`` y la lista de juegos se escanea fresca bajo demanda. Lógica
pura (sin widgets) para poder probarse en aislamiento.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..settings import AppSettings

_EXTENSIONS = ("*.sfc", "*.smc", "*.SFC", "*.SMC")


def clean_name(filename: str) -> str:
    """Nombre legible a partir del archivo: sin extensión, '_'/'.' → espacios."""
    stem = Path(filename).stem
    name = " ".join(stem.replace("_", " ").replace(".", " ").split())
    return name or filename


@dataclass(frozen=True)
class GameEntry:
    path: Path           # ruta absoluta a la ROM
    display_name: str    # nombre limpio para mostrar
    folder: str          # nombre de la carpeta contenedora (desambigua)


class LibraryService:
    """Escanea carpetas (persistidas) en busca de ROMs SNES."""

    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings

    def folders(self) -> list[str]:
        return self._settings.library_folders()

    def add_folder(self, path: str) -> None:
        folders = self.folders()
        if path not in folders:
            folders.append(path)
            self._settings.set_library_folders(folders)

    def remove_folder(self, path: str) -> None:
        folders = [f for f in self.folders() if f != path]
        self._settings.set_library_folders(folders)

    def scan(self) -> list[GameEntry]:
        seen: set[Path] = set()
        entries: list[GameEntry] = []
        for folder in self.folders():
            root = Path(folder)
            if not root.is_dir():
                continue
            for pattern in _EXTENSIONS:
                for path in root.rglob(pattern):
                    rp = path.resolve()
                    if rp in seen or not rp.is_file():
                        continue
                    seen.add(rp)
                    entries.append(
                        GameEntry(rp, clean_name(rp.name), rp.parent.name)
                    )
        entries.sort(key=lambda e: e.display_name.lower())
        return entries
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_library_service.py -v`
Expected: 6 passed. (En macOS el FS es insensible a mayúsculas y los patrones `*.SFC`/`*.SMC` pueden duplicar; el `seen` set lo evita — verificado por `test_scan_dedups_overlapping_folders` y los conteos exactos.)

- [ ] **Step 5: Commit**

```bash
git add snes_ui/services/library_service.py tests/test_library_service.py
git commit -m "feat(library): LibraryService con escaneo síncrono de ROMs"
```

---

### Task 3: Widget LibraryView

**Files:**
- Create: `snes_ui/widgets/library_view.py`
- Modify: `snes_ui/theme.py` (QSS de la lista)
- Test: `tests/test_library_view.py` (crear)

**Interfaces:**
- Consumes: `GameEntry` (Task 2).
- Produces:
  - `LibraryView(QWidget)` con:
    - `set_games(games: list[GameEntry]) -> None`
    - señales: `game_selected = Signal(str)` (ruta), `rescan_requested = Signal()`, `manage_folders_requested = Signal()`, `open_file_requested = Signal()`
    - método `_apply_filter(text: str)` interno (búsqueda)

- [ ] **Step 1: Write the failing test**

Crear `tests/test_library_view.py`:

```python
from pathlib import Path

from snes_ui.widgets.library_view import LibraryView
from snes_ui.services.library_service import GameEntry


def _entries():
    return [
        GameEntry(Path("/roms/Zelda.sfc"), "Zelda", "roms"),
        GameEntry(Path("/roms/Metroid.smc"), "Metroid", "roms"),
    ]


def test_set_games_populates_list(qapp):
    v = LibraryView()
    v.set_games(_entries())
    assert v._list.count() == 2


def test_search_hides_non_matching(qapp):
    v = LibraryView()
    v.set_games(_entries())
    v._search.setText("zel")
    visible = [i for i in range(v._list.count())
               if not v._list.item(i).isHidden()]
    assert len(visible) == 1
    assert v._list.item(visible[0]).text() == "Zelda"


def test_activating_item_emits_game_selected(qapp):
    v = LibraryView()
    v.set_games(_entries())
    captured = []
    v.game_selected.connect(captured.append)
    v._list.setCurrentRow(0)
    v._on_item_activated(v._list.currentItem())
    assert captured == [str(Path("/roms/Metroid.smc"))]   # row 0 = Metroid (orden de _entries)


def test_empty_shows_guide(qapp):
    v = LibraryView()
    v.set_games([])
    assert v._stack.currentWidget() is v._empty_page
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_library_view.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'snes_ui.widgets.library_view'`.

- [ ] **Step 3: Write minimal implementation**

Crear `snes_ui/widgets/library_view.py`:

```python
"""Vista de biblioteca: cuadrícula de juegos en el escenario vacío.

Cabecera con búsqueda y acciones (re-escanear, gestionar carpetas) sobre un
``QListWidget`` en modo icono (cuadrícula que ajusta columnas, navegación con
flechas, doble-clic/Enter para lanzar). Si no hay juegos, muestra una guía con
las acciones para añadir una carpeta o abrir un archivo suelto.
"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..services.library_service import GameEntry
from .icons import line_icon
from .state_card import StateCard

_PATH_ROLE = Qt.ItemDataRole.UserRole


class LibraryView(QWidget):
    game_selected = Signal(str)          # ruta de la ROM a cargar
    rescan_requested = Signal()
    manage_folders_requested = Signal()
    open_file_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # --- Cabecera ---
        header = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Buscar juego…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._apply_filter)
        header.addWidget(self._search, stretch=1)

        self._folders_btn = QPushButton("Carpetas…")
        self._folders_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._folders_btn.clicked.connect(self.manage_folders_requested.emit)
        header.addWidget(self._folders_btn)

        self._rescan_btn = QToolButton()
        self._rescan_btn.setObjectName("BotonRefrescar")
        self._rescan_btn.setIcon(line_icon("refresh", 18))
        self._rescan_btn.setToolTip("Re-escanear carpetas")
        self._rescan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rescan_btn.clicked.connect(self.rescan_requested.emit)
        header.addWidget(self._rescan_btn)
        root.addLayout(header)

        # --- Cuerpo: lista o guía vacía ---
        self._stack = QStackedWidget()

        self._list = QListWidget()
        self._list.setObjectName("Biblioteca")
        self._list.setViewMode(QListWidget.ViewMode.IconMode)
        self._list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._list.setMovement(QListWidget.Movement.Static)
        self._list.setWrapping(True)
        self._list.setUniformItemSizes(True)
        self._list.setWordWrap(True)
        self._list.setSpacing(0)
        self._list.setGridSize(QSize(168, 84))
        self._list.setIconSize(QSize(0, 0))
        self._list.itemActivated.connect(self._on_item_activated)
        self._stack.addWidget(self._list)            # índice 0

        self._empty_page = self._build_empty_page()
        self._stack.addWidget(self._empty_page)      # índice 1

        root.addWidget(self._stack, stretch=1)

    def _build_empty_page(self) -> QWidget:
        card = StateCard(
            "controller",
            "No hay juegos en la biblioteca",
            "Añade una carpeta con ROMs de SNES o abre un archivo suelto.",
        )
        card.add_action("Añadir carpeta", self.manage_folders_requested.emit, primary=True)
        card.add_action("Abrir archivo…", self.open_file_requested.emit)
        return card

    # -- API -----------------------------------------------------------------
    def set_games(self, games: list[GameEntry]) -> None:
        self._list.clear()
        for g in games:
            item = QListWidgetItem(g.display_name)
            item.setData(_PATH_ROLE, str(g.path))
            item.setToolTip(f"{g.display_name}\n{g.folder} · {g.path}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._list.addItem(item)
        self._apply_filter(self._search.text())
        self._stack.setCurrentWidget(
            self._list if games else self._empty_page
        )

    # -- internos ------------------------------------------------------------
    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self._list.count()):
            item = self._list.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def _on_item_activated(self, item: QListWidgetItem | None) -> None:
        if item is not None:
            self.game_selected.emit(item.data(_PATH_ROLE))
```

Añadir el QSS de la lista en `snes_ui/theme.py`, dentro de `build_stylesheet`, justo antes del cierre (después de la regla `QFrame#ContenedorIlustracion`):

```python
    /* --- Biblioteca de ROMs (cuadrícula en el escenario) --- */
    QListWidget#Biblioteca {{
        background: transparent;
        border: none;
        outline: none;
    }}
    QListWidget#Biblioteca::item {{
        background-color: {p.elevated};
        border: 1px solid {p.border_subtle};
        border-radius: {RADIUS_GROUP}px;
        margin: 6px;
        padding: 10px 6px;
        color: {p.text_primary};
        font-size: 13px;
        font-weight: 600;
    }}
    QListWidget#Biblioteca::item:hover {{
        background-color: {p.control_hover};
    }}
    QListWidget#Biblioteca::item:selected {{
        background-color: {accent_tint};
        border: 1px solid {p.accent};
        color: {p.text_primary};
    }}
```

(`accent_tint` ya está definido en `build_stylesheet`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_library_view.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add snes_ui/widgets/library_view.py snes_ui/theme.py tests/test_library_view.py
git commit -m "feat(library): widget LibraryView (cuadrícula + búsqueda)"
```

---

### Task 4: GameStage aloja la biblioteca

**Files:**
- Modify: `snes_ui/widgets/game_stage.py`
- Test: `tests/test_game_stage_library.py` (crear)

**Interfaces:**
- Consumes: `LibraryService` (Task 2), `LibraryView` (Task 3).
- Produces (en `GameStage`):
  - constructor `GameStage(library_service, parent=None)`
  - señales nuevas: `game_selected = Signal(str)`, `library_manage_folders = Signal()`
  - método `refresh_library() -> None` (escanea y repuebla la vista)
  - se conserva la señal existente `request_load` (para "Abrir archivo…").

- [ ] **Step 1: Write the failing test**

Crear `tests/test_game_stage_library.py`:

```python
from snes_ui.settings import AppSettings
from snes_ui.services.library_service import LibraryService
from snes_ui.widgets.game_stage import GameStage


def _stage(tmp_path):
    s = AppSettings()
    s.set_library_folders([str(tmp_path)])
    return GameStage(LibraryService(s))


def test_refresh_library_populates(qapp, tmp_path):
    (tmp_path / "Pilotwings.sfc").write_bytes(b"x")
    stage = _stage(tmp_path)
    stage.refresh_library()
    assert stage._library._list.count() == 1


def test_game_selected_reemitted(qapp, tmp_path):
    stage = _stage(tmp_path)
    captured = []
    stage.game_selected.connect(captured.append)
    stage._library.game_selected.emit("/roms/X.sfc")
    assert captured == ["/roms/X.sfc"]


def test_manage_folders_reemitted(qapp, tmp_path):
    stage = _stage(tmp_path)
    captured = []
    stage.library_manage_folders.connect(lambda: captured.append(True))
    stage._library.manage_folders_requested.emit()
    assert captured == [True]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_game_stage_library.py -v`
Expected: FAIL con `TypeError: GameStage.__init__() missing 1 required positional argument: 'library_service'`.

- [ ] **Step 3: Write minimal implementation**

En `snes_ui/widgets/game_stage.py`:

1. Añadir imports al inicio (junto a los existentes):

```python
from ..services.library_service import LibraryService
from .library_view import LibraryView
```

2. Cambiar la firma de las señales de `GameStage` (tras las señales existentes `request_load`, `retry_requested`, etc.) añadiendo:

```python
    game_selected = Signal(str)        # ruta de ROM elegida en la biblioteca
    library_manage_folders = Signal()  # solicitud de gestionar carpetas
```

3. Cambiar el constructor a `def __init__(self, library_service: LibraryService, parent: QWidget | None = None) -> None:` y guardar el servicio: tras `super().__init__(parent)` y `self.setObjectName("EscenarioJuego")`, añadir `self._service = library_service`.

4. Reemplazar el bloque del estado vacío (la creación de `self._empty` como `StateCard` y su `add_action`/`addWidget`) por la biblioteca:

```python
        # 0 - Vacio: biblioteca de ROMs
        self._library = LibraryView()
        self._library.game_selected.connect(self.game_selected.emit)
        self._library.manage_folders_requested.connect(self.library_manage_folders.emit)
        self._library.open_file_requested.connect(self.request_load.emit)
        self._library.rescan_requested.connect(self.refresh_library)
        self._stack.addWidget(self._library)
```

5. Añadir el método `refresh_library` (en la sección de API, p. ej. tras `show_state`):

```python
    def refresh_library(self) -> None:
        self._library.set_games(self._service.scan())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_game_stage_library.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add snes_ui/widgets/game_stage.py tests/test_game_stage_library.py
git commit -m "feat(library): GameStage aloja la biblioteca en el estado vacío"
```

---

### Task 5: Cableado en MainWindow

**Files:**
- Modify: `snes_ui/main_window.py`
- Test: `tests/test_main_window_library.py` (crear)

**Interfaces:**
- Consumes: `GameStage(library_service)` (Task 4), `LibraryService` (Task 2), `SessionController.begin_loading` + `finish_loading` (existentes).
- Produces:
  - `MainWindow._flow_load_game_path(path: str) -> None` (carga directa por ruta, sin diálogo)
  - `MainWindow._flow_manage_folders() -> None` (abre el diálogo de carpetas + re-escaneo al cerrar)
  - `_FoldersDialog(service, parent)` (gestiona añadir/quitar carpetas)
  - refresco de la biblioteca al entrar al estado `EMPTY`.

- [ ] **Step 1: Write the failing test**

Crear `tests/test_main_window_library.py`:

```python
from snes_ui.main_window import MainWindow, _FoldersDialog
from snes_ui.state import SessionState
from snes_ui.settings import AppSettings
from snes_ui.services.library_service import LibraryService


def test_library_populated_on_start(qapp, tmp_path):
    (tmp_path / "FZero.sfc").write_bytes(b"x")
    AppSettings().set_library_folders([str(tmp_path)])
    w = MainWindow()
    # En el arranque el estado es EMPTY → la biblioteca se refrescó.
    assert w._stage._library._list.count() == 1


def test_selecting_game_begins_loading(qapp, tmp_path):
    AppSettings().set_library_folders([str(tmp_path)])
    w = MainWindow()
    w._flow_load_game_path(str(tmp_path / "FZero.sfc"))
    # begin_loading transiciona a LOADING (finish_loading va en un singleShot
    # que no se dispara sin procesar el event loop).
    assert w._session.state == SessionState.LOADING


def test_folders_dialog_remove(qapp, tmp_path):
    AppSettings().set_library_folders([str(tmp_path), "ROMS"])
    svc = LibraryService(AppSettings())
    dlg = _FoldersDialog(svc, None)
    dlg._list.setCurrentRow(0)            # str(tmp_path)
    dlg._on_remove()
    assert str(tmp_path) not in svc.folders()
    assert "ROMS" in svc.folders()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_main_window_library.py -v`
Expected: FAIL con `AttributeError: 'MainWindow' object has no attribute '_flow_load_game_path'` (o el `assert count == 1` falla porque aún no se refresca).

- [ ] **Step 3: Write minimal implementation**

En `snes_ui/main_window.py`:

1. Añadir el import del servicio (junto a los otros imports de servicios) y `QPushButton` a los imports de `PySide6.QtWidgets` (la lista actual no lo incluye y `_FoldersDialog` lo usa):

```python
from .services.library_service import LibraryService
```

En el bloque `from PySide6.QtWidgets import (...)`, añadir `QPushButton` (orden alfabético, tras `QMessageBox`).

2. En `__init__`, crear el servicio antes de construir la UI (tras `self._saves = SaveService()`):

```python
        self._library = LibraryService(self._settings)
```

3. En `_build_ui`, cambiar `self._stage = GameStage()` por:

```python
        self._stage = GameStage(self._library)
```

4. En `_connect_signals`, añadir (junto a las otras conexiones de `self._stage`):

```python
        self._stage.game_selected.connect(self._flow_load_game_path)
        self._stage.library_manage_folders.connect(self._flow_manage_folders)
```

5. Refactorizar el flujo de carga para reutilizar la ruta. Reemplazar el cuerpo de `_flow_load_game` por una variante que delega en `_flow_load_game_path`, y añadir los dos métodos nuevos:

```python
    def _flow_load_game(self) -> None:
        start_dir = "ROMS" if os.path.isdir("ROMS") else os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, "Cargar juego", start_dir, "ROMs SNES (*.sfc *.smc)"
        )
        if not path:
            return  # cancelado: sin cambios
        self._flow_load_game_path(path)

    def _flow_load_game_path(self, path: str) -> None:
        self._session.begin_loading(path)
        # Cede el control al event loop una vez (sin retraso artificial) para
        # que la vista CARGANDO se pinte antes de la carga sincrona del nucleo.
        QTimer.singleShot(0, self._session.finish_loading)

    def _flow_manage_folders(self) -> None:
        dlg = _FoldersDialog(self._library, self)
        dlg.exec()
        self._stage.refresh_library()
```

7. Añadir la clase `_FoldersDialog` al final del archivo (junto a `_SaveStateDialog`):

```python
class _FoldersDialog(QDialog):
    """Gestiona las carpetas que escanea la biblioteca (añadir/quitar)."""

    def __init__(self, service, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Carpetas de la biblioteca")
        self.setMinimumWidth(420)
        self._service = service

        layout = QVBoxLayout(self)
        self._list = QListWidget()
        layout.addWidget(self._list)

        row = QHBoxLayout()
        add_btn = QPushButton("Añadir…")
        add_btn.clicked.connect(self._on_add)
        remove_btn = QPushButton("Quitar")
        remove_btn.clicked.connect(self._on_remove)
        row.addWidget(add_btn)
        row.addWidget(remove_btn)
        row.addStretch()
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        row.addWidget(close_btn)
        layout.addLayout(row)

        self._reload()

    def _reload(self) -> None:
        self._list.clear()
        self._list.addItems(self._service.folders())

    def _on_add(self) -> None:
        start = "ROMS" if os.path.isdir("ROMS") else os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(
            self, "Añadir carpeta de ROMs", start
        )
        if folder:
            self._service.add_folder(folder)
            self._reload()

    def _on_remove(self) -> None:
        item = self._list.currentItem()
        if item is not None:
            self._service.remove_folder(item.text())
            self._reload()
```

6. En `_on_state_changed`, refrescar la biblioteca al entrar a `EMPTY`. Añadir al inicio del método (tras `self._stage.show_state(state)`):

```python
        if state == SessionState.EMPTY:
            self._stage.refresh_library()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_main_window_library.py -v`
Expected: 2 passed.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: toda la suite en verde (los tests previos siguen pasando; el estado `EMPTY` ya no usa el `StateCard` "Ningún juego cargado").

- [ ] **Step 6: Commit**

```bash
git add snes_ui/main_window.py tests/test_main_window_library.py
git commit -m "feat(library): cableado de la biblioteca en MainWindow"
```

---

### Task 6: Verificación visual headless

**Files:**
- (Sin cambios de código; verificación manual.)

- [ ] **Step 1: Capturar el escenario con la biblioteca**

Con la carpeta `ROMS/` conteniendo al menos una ROM (`.sfc`/`.smc`), renderizar headless:

```bash
QT_QPA_PLATFORM=offscreen python -c "
import os, sys
os.environ['QT_QPA_PLATFORM']='offscreen'; os.environ['SDL_VIDEODRIVER']='dummy'
sys.path.insert(0,'.')
from PySide6.QtWidgets import QApplication
app=QApplication([])
from snes_ui.main_window import MainWindow
w=MainWindow(); w.resize(1360,860)
w._set_theme_pref('light'); app.processEvents()
w.grab().save('/tmp/biblioteca_light.png')
w._set_theme_pref('dark'); app.processEvents()
w.grab().save('/tmp/biblioteca_dark.png')
print('ok', w._stage._library._list.count(), 'juegos')
"
```

Expected: imprime el número de juegos; revisar `/tmp/biblioteca_light.png` y `_dark.png` — la cuadrícula aparece en el escenario, con búsqueda y botones de cabecera, en ambos temas.

- [ ] **Step 2: Commit (si se ajustó algo visual)**

```bash
git add -A && git commit -m "chore(library): ajustes visuales tras verificación"
```

(Si no hubo cambios, omitir.)

---

## Notas de diseño aplicadas

- **Carpeta en el ítem**: se muestra como **tooltip** (`nombre · carpeta · ruta`) en lugar de una segunda línea gris bajo el nombre. Es la opción mínima y robusta con `QListWidget` (que aporta gratis la cuadrícula que ajusta columnas, navegación con flechas y doble-clic/Enter para lanzar). Una segunda línea gris visible requeriría un `QStyledItemDelegate` y se deja como mejora futura.
- **Lanzar**: `itemActivated` (doble-clic o Enter) emite `game_selected`; un clic solo selecciona — exactamente la interacción acordada.
- **Sin "recientes"/orden múltiple/hash/portadas**: fuera de alcance (ver no-objetivos del spec).
