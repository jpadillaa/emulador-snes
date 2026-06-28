# Diseño: persistencia de SRAM (pila del cartucho)

Fecha: 2026-06-28

## Contexto

El emulador hoy ofrece **save states** manuales (`SaveService` +
`retro_serialize`/`unserialize`), pero **no persiste el SRAM** —la RAM de
batería del cartucho donde los juegos guardan su progreso interno (las partidas
de Zelda, los RPG, marcas de tiempo, etc.)—. No aparece ningún uso de
`retro_get_memory_data` / `RETRO_MEMORY_SAVE_RAM` en el código. Resultado: el
guardado *dentro del juego* se pierde al cerrar la sesión o la app. Esto no es
una característica extra, es comportamiento esperado de un emulador.

La forma correcta y fiable en libretro es la que usa RetroArch: el **frontend**
lee `retro_get_memory_data(RETRO_MEMORY_SAVE_RAM)` y lo persiste en un archivo
`.srm`. El core de snes9x **no** escribe ese archivo por su cuenta; delega en el
frontend. Se evaluó la ruta de `RETRO_ENVIRONMENT_SET_SAVE_DIRECTORY` y se
descarta: para SRAM no es fiable (los cores no hacen IO de SRAM ellos mismos).

## Decisiones de alcance (acordadas)

1. **Ubicación del `.srm`**: datos de la app —`AppDataLocation/sram/<rom>.srm`—,
   consistente con `SaveService`. **No** se escribe dentro de las carpetas de
   ROMs (pueden ser compartidas o de solo lectura).
2. **Cadencia de volcado**: **solo en momentos clave** (cerrar sesión, cambiar
   de juego, cerrar la app). Sin timers ni autoguardado periódico. Riesgo
   aceptado: un cierre forzado/crash pierde lo no volcado de esa partida.
3. Se mantiene la simplicidad del emulador: sin UI nueva. El SRAM se carga y
   vuelca de forma transparente.

## Arquitectura

Mantiene la separación estricta UI ↔ core. El core expone el SRAM como bytes; un
servicio se encarga del IO de archivos; el `SessionController` orquesta cuándo
cargar y volcar.

### 1. Contrato del core (`EmulatorCore` ABC)

Dos métodos nuevos:

- `get_sram() -> bytes`: copia de la RAM de batería del cartucho, o `b""` si el
  juego no tiene (o no hay juego cargado).
- `load_sram(blob: bytes) -> None`: vuelca `blob` en el buffer SAVE_RAM del core.
  Solo tiene efecto si el tamaño es compatible; `b""` o sin juego → no-op.

Se declaran abstractos en `EmulatorCore` y los implementa cada subclase.

**`MockEmulatorCore`**: `get_sram() → b""`, `load_sram(...) → pass`. En modo demo
y en tests no se escribe ningún archivo.

**`LibretroCore`**:
- Constante `RETRO_MEMORY_SAVE_RAM = 0`.
- Firmas ctypes: `retro_get_memory_data(unsigned) -> c_void_p`,
  `retro_get_memory_size(unsigned) -> c_size_t`.
- `get_sram()`: `size = retro_get_memory_size(0)`; si `size <= 0` o el puntero es
  nulo → `b""`; si no → `ctypes.string_at(data, size)`. Requiere juego cargado.
- `load_sram(blob)`: si no hay blob, juego o buffer → return; copia
  `min(len(blob), size)` bytes con `ctypes.memmove`. Si los tamaños no coinciden,
  copia el mínimo y registra un aviso (no rompe).

### 2. Servicio `SramStore` (`snes_ui/services/sram_service.py`)

Espejo minimalista de `SaveService`:

- `__init__(base_dir: Path | str | None = None)`: por defecto
  `AppDataLocation/sram`. Inyectable para tests.
- `path_for(rom_name) -> Path`: `<base>/<rom saneado>.srm`.
- `read(rom_name) -> bytes`: bytes del archivo, o `b""` si no existe o falla la
  lectura (registra y sigue).
- `write(rom_name, blob: bytes) -> None`: si `blob` está vacío, **no escribe**
  (no crea archivos vacíos ni pisa uno existente con vacío). Si no, crea la
  carpeta y escribe de forma **atómica**: `<file>.tmp` + `os.replace`, para no
  corromper el `.srm` ante un corte a mitad de escritura. Nunca lanza.
- Saneo de nombre propio (servicio autocontenido; no depende de `SaveService`).

### 3. Orquestación (`SessionController`)

Recibe un `SramStore` inyectado (parámetro opcional con valor por defecto, como
el core). Helper privado `_flush_sram()` centraliza
`store.write(self._rom_name, self._core.get_sram())` (solo si hay rom actual).

Puntos de enganche:

- **Cargar** — en `finish_loading`, tras `core.load_game()` correcto y antes de
  arrancar el bucle: `blob = store.read(rom)`; si hay bytes → `core.load_sram(blob)`.
- **Cambiar de juego** — en `begin_loading`, **antes** de reasignar
  `_rom_path`/`_rom_name` y mientras el juego anterior sigue cargado en el core:
  `_flush_sram()` del juego saliente. (Cambiar de juego no pasa por
  `quit_session`; `core.load_game` descarga el anterior internamente, así que hay
  que volcar aquí.)
- **Cerrar sesión** — en `quit_session`, **antes** de `core.unload()`: `_flush_sram()`.
- **Cerrar app** — en `MainWindow.closeEvent`, antes de `core.shutdown()`: volcar
  si hay sesión activa (vía un método público del controller, p. ej.
  `flush_sram()`).
- `reset_to_empty` (salida desde error): no hay juego cargado → nada que volcar.

Cableado en `MainWindow`: crear `self._sram = SramStore()` y pasarlo a
`SessionController(self._core, self, sram_store=self._sram)`.

## Flujo de datos

```
Iniciar juego:   store.read(rom)  ->  core.load_sram(blob)
Durante el juego: el core mantiene el SRAM en su buffer (el juego lo escribe)
Parar/cambiar/cerrar: core.get_sram()  ->  store.write(rom, blob)
```

## Relación con los save states

Independientes. El save state ya captura todo el estado de la máquina (incluido
el SRAM); el `.srm` es el guardado nativo del propio juego. Conviven sin
conflicto y se guardan por caminos distintos.

## Manejo de errores

- `load_sram` con tamaño incompatible → copia el mínimo y registra; nunca
  desborda el buffer.
- `read`/`write` con fallo de IO → registran en stderr y continúan; **nunca**
  bloquean el cierre de la app ni rompen la sesión.
- Escritura atómica para evitar `.srm` corruptos.

## Testing

- **`SramStore`** (sin hardware): round-trip write→read; `read` de archivo
  inexistente → `b""`; `write` de `b""` → no crea archivo; reemplazo atómico
  (el archivo final contiene el contenido nuevo, sin `.tmp` residual).
- **Orquestación de `SessionController`** con un core falso que expone
  `get_sram`/`load_sram`:
  - `finish_loading` llama `load_sram` con los bytes almacenados;
  - tras `quit_session`, el store contiene el SRAM del core;
  - al cambiar de juego (`begin_loading` con juego cargado), se vuelca el SRAM
    del juego anterior con su nombre.
- **`LibretroCore.get_sram`/`load_sram`**: validación manual (requiere el
  `.dylib` real); no se cubre con tests unitarios.

## Fuera de alcance

- Autoguardado periódico / por timer.
- UI para gestionar o ver archivos `.srm`.
- Compatibilidad de `.srm` con otros emuladores (ubicación en datos de la app).
