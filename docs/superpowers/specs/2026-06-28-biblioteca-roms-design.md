# Diseño: Biblioteca de ROMs (Library Manager)

Fecha: 2026-06-28

## Contexto

El emulador hoy abre una sola ROM a la vez mediante `QFileDialog` (filtro
`*.sfc *.smc`, por defecto en `ROMS/`). El spec contempla un **Gestor de
Biblioteca** ([docs/description.md](../../description.md)) que:

- escanea el sistema de archivos en busca de ROMs,
- mantiene un inventario y lo presenta como **vista de cuadrícula**,
- con un **modelo asíncrono** para no congelar la UI.

Restricción de layout ([docs/descripcion_interfaz.md](../../descripcion_interfaz.md),
fila 13): el cuerpo tiene **solo dos regiones** (escenario + panel de control);
**no** hay barra lateral izquierda de navegación.

## Decisiones de alcance (acordadas)

1. **Ubicación**: la biblioteca vive en el **estado `EMPTY` del escenario**. Al
   no haber juego cargado, el escenario muestra la cuadrícula de ROMs en vez de
   la tarjeta "Ningún juego cargado". Al elegir un juego se carga y el escenario
   pasa a `RUNNING`; al salir del juego, vuelve a `EMPTY` → reaparece la
   biblioteca. No se añaden estados nuevos a la máquina de sesión.
2. **Contenido de las tarjetas**: **solo nombre** (sin carátulas ni miniaturas).
   La carpeta contenedora se muestra como texto secundario pequeño para
   desambiguar ROMs con el mismo nombre.
3. **Carpetas escaneadas**: `ROMS/` por defecto **+** carpetas que el usuario
   añada/quite (persistidas). Re-escaneo manual.
4. **Implementación (Opción 1)**: **escaneo síncrono**, sin DB y **sin hash**.
   La lista de juegos **no se cachea**: se escanea fresca al abrir la biblioteca
   y al re-escanear (evita bugs de caché obsoleta). Lo único persistido es la
   **lista de carpetas**, vía el `AppSettings` (QSettings) existente — no se crea
   un archivo nuevo.

### No-objetivos (fuera de esta versión)

- Carátulas/portadas (placeholder o descarga online).
- Base de datos (SQLite) e índice cacheado en disco.
- Firmas digitales / hashes de ROMs y deduplicación por contenido.
- Metadatos enriquecidos (año, región, género), "recientes"/last-played,
  favoritos, ordenamientos múltiples.
- Escaneo en segundo plano (hilo). Se asume escaneo local rápido; si una carpeta
  tardara, basta un estado transitorio "Escaneando…".

Todos estos son extensiones naturales sobre este diseño cuando exista un
consumidor real.

## Arquitectura y componentes

```
LibraryView (widget, en GameStage[EMPTY])
   │  game_selected(path: str)
   ▼
MainWindow  ──►  SessionController.begin_loading(path)
   ▲
   │ usa
LibraryService (lógica pura, sin widgets)
   • folders()  /  add_folder(path)  /  remove_folder(path)   (persisten en AppSettings)
   • scan() -> list[GameEntry]
```

- **`snes_ui/services/library_service.py` → `LibraryService`**
  Lógica pura, testeable sin Qt-widgets. Responsabilidades:
  - Gestionar la lista de carpetas raíz (leer/escribir vía `AppSettings`).
  - `scan()`: recorrer las carpetas y devolver `list[GameEntry]` ordenada.
  - Recibe el `AppSettings` por inyección (o un `base`/lista inicial) para poder
    testear de forma hermética, igual que `SaveService` acepta `base_dir`.

- **`snes_ui/widgets/library_view.py` → `LibraryView(QWidget)`**
  La cuadrícula dentro del escenario. Composición:
  - Cabecera: campo de **búsqueda** (filtra en vivo por nombre), botón
    **Re-escanear** (↻) y botón **Carpetas…**.
  - Cuerpo: `QScrollArea` con un grid de tarjetas (`LibraryCard` o reutilizando
    un botón estilizado) — orden alfabético.
  - Estado vacío embebido: si no hay ROMs, muestra una guía con
    "Añadir carpeta" y "Abrir archivo…".
  - Señales: `game_selected(str)`, `add_folder_requested()`,
    `rescan_requested()`.

- **Integración en `GameStage`**: el índice `EMPTY` del `QStackedWidget` aloja
  `LibraryView` en lugar del `StateCard` actual. `GameStage` expone la vista
  (o reenvía sus señales) para que `MainWindow` las cablee.

- **Integración en `MainWindow`**:
  - Crea `LibraryService` y lo pasa a `GameStage`/`LibraryView`.
  - `library.game_selected → _flow_load_game_path(path)` (variante del flujo de
    carga actual que recibe la ruta directamente, sin diálogo).
  - `add_folder_requested → QFileDialog.getExistingDirectory → service.add_folder
    → refrescar la vista`.
  - `rescan_requested → refrescar la vista`.
  - Refrescar la biblioteca al volver al estado `EMPTY`.

## Modelo de datos

```python
@dataclass(frozen=True)
class GameEntry:
    path: Path           # ruta absoluta a la ROM
    display_name: str    # nombre limpio para mostrar
    folder: str          # nombre de la carpeta contenedora (desambigua)
```

- **Limpieza de nombre**: quitar la extensión, sustituir `_` y `.` por espacios,
  colapsar espacios múltiples y recortar. **No** se eliminan etiquetas como
  `(USA)` o `[!]` (pueden ser informativas).
- **Persistencia**: clave `library/folders` en `AppSettings` (lista de rutas;
  por defecto `["ROMS"]`). Nada más se escribe a disco.

## UI / UX

- **Dónde**: estado `EMPTY` del escenario (a pantalla del escenario, respetando
  el layout de dos regiones).
- **Cabecera**: búsqueda (izquierda, expansible), y a la derecha los botones
  **Carpetas…** y **Re-escanear** (↻, icono de línea ya disponible).
- **Tarjetas**: nombre del juego como texto principal y la carpeta en pequeño y
  gris debajo. Mismos tokens de tema (superficie, hover, anillo de foco) que el
  resto de la app. Sin imágenes.
- **Interacción**:
  - **Doble-clic** o **Enter** sobre una tarjeta → carga el juego.
  - **Un clic** → selecciona/resalta.
  - **Flechas** → navegación entre tarjetas; **Escape** limpia la búsqueda.
- **Búsqueda**: filtra la cuadrícula por subcadena (case-insensitive) del nombre
  en vivo; si no hay coincidencias, mensaje "Sin resultados".
- **Estados vacíos**:
  - Sin carpetas / sin ROMs → tarjeta guía con "Añadir carpeta" y
    "Abrir archivo…" (reusa el `QFileDialog` actual para una ROM suelta).
- **Diálogo "Carpetas…"**: lista las carpetas configuradas con opción de
  **añadir** (selector de directorio) y **quitar**; al cerrar, re-escanea.
- La acción existente **"Cargar juego"** (barra/menú) se conserva como vía
  alternativa para abrir una ROM puntual por diálogo.

## Flujo de escaneo (síncrono)

1. Para cada carpeta configurada que exista y sea legible:
   `rglob` de `*.sfc` y `*.smc` (insensible a mayúsculas).
2. Deduplicar por ruta absoluta resuelta (carpetas solapadas no duplican).
3. Construir `GameEntry` (con nombre limpio y carpeta contenedora).
4. Ordenar alfabéticamente por `display_name` (insensible a mayúsculas).
5. Devolver la lista. La `LibraryView` la pinta; el filtro de búsqueda se aplica
   sobre esta lista en memoria.

Si el escaneo de alguna carpeta resultara lento, la vista muestra un estado
transitorio "Escaneando…" mientras corre (el escaneo es síncrono pero se cede el
control al event loop una vez para pintar ese estado, como ya se hace en
`_flow_load_game`).

## Manejo de errores y casos límite

- **Carpeta inexistente / sin permiso**: se ignora en el escaneo; en el diálogo
  "Carpetas…" puede marcarse como no disponible.
- **Sin ROMs**: estado vacío guía (no error).
- **ROM borrada/movida entre escaneo y carga**: la carga falla con el flujo de
  error de sesión ya existente (estado `ERROR` del escenario).
- **Carpetas duplicadas o solapadas**: dedup por ruta absoluta.
- **Nombres repetidos** en distintas carpetas: ambas tarjetas aparecen; la línea
  de carpeta las distingue.

## Pruebas

- **`LibraryService`** (hermético, sin hardware; directorio temporal):
  - escanea `.sfc`/`.smc` (mayúsc./minúsc.) e ignora otros archivos;
  - lista ordenada alfabéticamente;
  - limpieza de nombres (`Super_Mario_Kart.sfc` → "Super Mario Kart");
  - `add_folder`/`remove_folder` persisten y afectan el escaneo;
  - dedup por ruta con carpetas solapadas;
  - carpeta inexistente se ignora sin error.
- **`LibraryView`** (headless, `QT_QPA_PLATFORM=offscreen`):
  - construir y poblar con entradas fake;
  - el filtro de búsqueda reduce las tarjetas visibles;
  - activar una tarjeta emite `game_selected` con la ruta correcta.

## Archivos afectados

- Nuevo: `snes_ui/services/library_service.py`
- Nuevo: `snes_ui/widgets/library_view.py`
- Modificado: `snes_ui/widgets/game_stage.py` (alojar `LibraryView` en `EMPTY`)
- Modificado: `snes_ui/main_window.py` (crear servicio, cablear señales, flujo de
  carga por ruta, refresco al volver a `EMPTY`)
- Modificado: `snes_ui/settings.py` (`AppSettings`: getters/setters de
  `library/folders`)
- Nuevos tests: `tests/test_library_service.py`, `tests/test_library_view.py`
