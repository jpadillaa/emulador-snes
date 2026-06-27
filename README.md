# SNES Emulator

Emulador de SNES para escritorio, escritoen Python, que envuelve un núcleo de emulación libretro de terceros (`snes9x_libretro`). La capa en Python se encarga únicamente de la presentación y la gestión; la emulación ocurre dentro del núcleo compilado en C/C++, al que se accede mediante el ABI C de libretro a través de `ctypes`.

## Características

- **Núcleo real de emulación** (`snes9x_libretro`) integrado mediante `ctypes`, con fallback automático a un núcleo simulado (`MockEmulatorCore`) que permite ejecutar la interfaz en modo demo cuando el `.dylib` no está disponible.
- **Interfaz gráfica PySide6** nativa de macOS, con escalado de video en cuatro modos (ajustar a ventana, escalamiento entero, original y estirado), soporte HiDPI/Retina y modo pantalla completa con barra de acciones auto-ocultable.
- **Soporte de gamepad** vía `pygame.joystick` (SDL), con enumeración, conexión en caliente, perfiles de mapeo por dispositivo (teclado o GUID del gamepad), captura de entradas para reconfiguración y el stick izquierdo replicando el D-Pad.
- **Enrutamiento de entrada OR-combinado**: el teclado alimenta siempre el juego y el gamepad activo se suma, de modo que soltar una tecla nunca cancela un botón que el pad aún mantiene pulsado.
- **Audio en tiempo real** mediante `QAudioSink` (QtMultimedia) en modo push, sin dependencias adicionales.
- **Guardado de estados** persistente en disco con miniatura PNG y marca de tiempo; soporte de carga perezosa y eliminación.
- **Pruebas headless** aisladas con `pytest`.

## Estructura del proyecto

```
.
├── CLAUDE.md                # Guía para Claude Code
├── README.md
├── main.py                  # Punto de entrada de la GUI PySide6
├── poc.py                   # Prueba de concepto (pygame) que conduce el núcleo libretro
├── requirements.txt         # Dependencias de producción (PySide6, pygame)
├── requirements-dev.txt     # Dependencias de desarrollo (pytest)
├── docs/                    # Especificaciones y documentación de diseño
├── kernel/                  # Núcleo libretro precompilado (snes9x_libretro.dylib)
├── ROMS/                    # Directorio de ROMs (.sfc / .smc)
├── snes_ui/                 # Paquete de la interfaz gráfica
│   ├── main_window.py       # MainWindow: ensambla la ventana y enruta entradas
│   ├── state.py             # Enums compartidos (SessionState, ScaleMode, ConnectionState)
│   ├── theme.py             # Tokens de diseño + QSS claro/oscuro
│   ├── settings.py          # Persistencia con QSettings
│   ├── core/                # Adaptador del núcleo y control de sesión
│   │   ├── adapter.py        # EmulatorCore (ABC), LibretroCore, MockEmulatorCore
│   │   ├── audio.py          # AudioPlayer (QAudioSink push)
│   │   └── session.py        # SessionController (máquina de estados + bucle de frames)
│   ├── services/            # Servicios de entrada, gamepad y guardado
│   │   ├── input_service.py
│   │   ├── gamepad_service.py
│   │   └── save_service.py
│   └── widgets/             # Componentes reutilizables de la UI
│       ├── game_stage.py
│       ├── video_surface.py
│       ├── control_panel.py
│       ├── mapping_row.py
│       ├── controller_diagram.py
│       ├── action_bar.py
│       ├── overlay_action_bar.py
│       ├── segmented_control.py
│       ├── state_card.py
│       ├── toast.py
│       └── icons.py
└── tests/                   # Suite de pruebas con pytest
```

## Requisitos

- Python 3.14
- Dependencias listadas en `requirements.txt` (PySide6 6.11, pygame 2.6.1)
- Dependencias de desarrollo en `requirements-dev.txt` (pytest)

## Instalación

```bash
# Crear y activar un entorno virtual
python3.14 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
pip install -r requirements-dev.txt   # opcional, solo para desarrollo
```

## Uso

```bash
source .venv/bin/activate

# Ejecutar la GUI PySide6 (núcleo libretro real, con fallback a simulado)
python main.py

# Ejecutar la prueba de concepto (pygame, carga ./ROMS/SuperMarioKart.sfc)
python poc.py
```

Las ROMs se colocan en el directorio `ROMS/` con extensión `.sfc` o `.smc`. La GUI abre las ROMs mediante un `QFileDialog` que por defecto apunta a `ROMS/`.

## Pruebas

```bash
python -m pytest
```

Las pruebas son headless y herméticas: `tests/conftest.py` fuerza `QT_QPA_PLATFORM=offscreen` y `SDL_VIDEODRIVER=dummy`, y redirige `QSettings` a un directorio temporal. Las funciones puras de traducción de entradas (`translate`/`detect_binding`) se prueban sin hardware.

## Arquitectura

El proyecto sigue una arquitectura MVC por capas con **aislamiento estricto entre la interfaz y el núcleo de emulación mediante un adaptador**, de modo que el núcleo puede sustituirse sin reescribir la aplicación.

- **Adaptador del núcleo** (`snes_ui/core/adapter.py`): define `EmulatorCore`, el único contrato que la interfaz conoce. `LibretroCore` es el enlace real con `ctypes` al núcleo `snes9x_libretro`; `MockEmulatorCore` es el respaldo con frames sintéticos animados. La factoría `create_core()` selecciona el backend y lo etiqueta en `core.backend` (`"libretro"` o `"mock"`).
- **Controlador de sesión** (`snes_ui/core/session.py`): máquina de estados única para los cinco estados de la UI (`EMPTY`/`LOADING`/`RUNNING`/`PAUSED`/`ERROR`) y el bucle de frames mediante `QTimer`.
- **Servicios** (`snes_ui/services/`): gestionan la entrada (teclado + perfiles de mapeo), el gamepad (pygame/SDL) y el guardado de estados.
- **Interfaz** (`snes_ui/widgets/` y `main_window.py`): componentes reutilizables que consumen los tokens de `theme.py` y los enums de `state.py`.

### Integración con el núcleo libretro

La integración con el ABI C de libretro es la parte más delicada del proyecto:

1. Se carga el núcleo con `ctypes.CDLL` y se registran seis callbacks **antes** de `retro_init()`: entorno, video, audio (simple y batch), input poll e input state.
2. **Se mantienen referencias vivas a cada callback** durante toda la vida del proceso; si un `CFUNCTYPE` se recolecta, el núcleo invoca memoria liberada y falla.
3. El formato de píxel se negocia, no se asume; los frames de video llegan con un `pitch` (stride de fila en bytes) que **no** es `width * bytes_per_pixel` y debe respetarse.
4. La entrada es *pull*: el núcleo llama a `cb_input_state` cada frame; se devuelve `1`/`0`.
5. Ciclo de vida: `retro_init()` → construir `retro_game_info` → `retro_load_game` → bucle `retro_run()` → `retro_unload_game()` → `retro_deinit()`.

## Documentación

- `docs/description.md` — Especificación de arquitectura y capas.
- `docs/descripcion_interfaz.md` — Especificación exhaustiva de la interfaz (jerarquía de widgets, estados, tema, tipografía, flujos de interacción).
- `docs/IMPLEMENTACION.md` — Decisiones de implementación y arquitectura.

## Licencia

Núcleo `snes9x_libretro` incluido como binario precompilado; no se compila en este repositorio.