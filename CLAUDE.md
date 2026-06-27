# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A SNES emulator desktop app built in Python that wraps a third-party libretro emulation core (`snes9x_libretro`). The Python layer is purely presentation + management; emulation happens inside the compiled C/C++ core, reached over the libretro C ABI via `ctypes`.

Two parts coexist:
- **`poc.py`** — a single-file proof-of-concept (pygame window) that drives the real libretro core (hardcoded to `./ROMS/SuperMarioKart.sfc`). The original reference for the core integration.
- **`snes_ui/` + `main.py`** — the PySide6 desktop GUI implementing `docs/descripcion_interfaz.md`. **It drives the real libretro core** (`LibretroCore` in `snes_ui/core/adapter.py`, ported from `poc.py`), selected by the `create_core()` factory; if the `.dylib` can't load it falls back to `MockEmulatorCore` so the UI still runs in demo mode. Video, input, save states, and **audio** are all wired through the adapter. The chosen backend is recorded on `core.backend` (`"libretro"` or `"mock"`).

When building UI features, treat `docs/descripcion_interfaz.md` as the authoritative spec; `docs/IMPLEMENTACION.md` records the architecture and the decisions taken for spec ambiguities.

## Commands

```bash
source .venv/bin/activate        # Python 3.14; deps in requirements.txt (PySide6 6.11, pygame)
pip install -r requirements-dev.txt  # dev-only deps (pytest)
python main.py                   # run the PySide6 GUI (real libretro core, mock fallback)
python poc.py                    # run the libretro PoC (loads ./ROMS/SuperMarioKart.sfc, pygame window)
python -m pytest                 # run the test suite (headless; conftest forces offscreen + isolated QSettings)
```

Render the GUI headless for verification (offscreen): set `QT_QPA_PLATFORM=offscreen`, build `MainWindow`, drive `SessionController`, and `widget.grab().save(path)` to capture state screenshots.

Tests live in `tests/` (pytest); run `python -m pytest`. `tests/conftest.py` forces a headless `QApplication` (`QT_QPA_PLATFORM=offscreen`, `SDL_VIDEODRIVER=dummy`) and redirects `QSettings` to a temp dir so tests are hermetic — hence `AppSettings` builds `QSettings` with `defaultFormat()` (NativeFormat in production, redirectable in tests). No linter is configured. The libretro core (`kernel/snes9x_libretro.dylib`) is a prebuilt binary checked into the repo, not built here.

## GUI architecture (snes_ui/)

Strict UI ↔ core isolation via an adapter so the core can be replaced without touching the UI:
- `main_window.py` — `MainWindow`: top-level window that wires everything together (creates the core via `create_core()`, the `SessionController`, services incl. `GamepadService`, the action bars, the `ControlPanel`, the `GameStage`), opens ROMs through a `QFileDialog` (defaults to `ROMS/`, filter `*.sfc *.smc`), and manages full-screen presentation mode with the auto-hiding overlay bar. **Input routing is OR-combine**: keyboard always feeds the game and the selected gamepad adds to it — `_recompute_inputs()` unions `_kbd_pressed | _pad_pressed` and pushes the result to the core, so releasing a key never cancels a button the pad still holds. The device selector chooses the active gamepad and which profile the panel edits; remapping a row captures a key (keyboard active) or the next physical pad input (gamepad active).
- `state.py` — shared enums: `SessionState` (the five stage views), `ScaleMode` (FIT_WINDOW / INTEGER / ORIGINAL / STRETCH video scaling), `ConnectionState` (controller connection). Import states from here; don't redefine them in widgets.
- `core/adapter.py` — `EmulatorCore` ABC (the only contract the UI knows); `LibretroCore` (real ctypes binding to `snes9x_libretro`, video as `QImage` honoring pixel format + pitch, pull-model input, real serialize/unserialize save states, real-time audio); `MockEmulatorCore` (animated synthetic frames, fallback); `create_core()` picks one and tags it with `core.backend`. **Critical**: `LibretroCore` keeps its `CFUNCTYPE` callbacks as instance attrs — letting them be GC'd crashes the core. See `docs/IMPLEMENTACION.md` for the integration decisions.
- `core/audio.py` — `AudioPlayer` wraps `QAudioSink` (QtMultimedia, no new dep) in push mode. The libretro audio-batch callback enqueues S16 stereo samples; `LibretroCore.run_frame` flushes them after `retro_run`. Audio lifecycle (`start/pause/resume/stop_audio`) lives on the `EmulatorCore` ABC (no-op default) and is driven by `SessionController` on state transitions. All on the main thread — `QAudioSink` plays on its own backend thread, writes never block.
- `core/session.py` — `SessionController`: the single state machine for the five UI states (EMPTY/LOADING/RUNNING/PAUSED/ERROR) and a `QTimer` frame loop. Emits signals; `MainWindow` observes them to switch stage views and enable/disable session-dependent actions. **All session-state logic lives here** — don't scatter it into widgets.
- `services/`:
  - `input_service.py` — `InputService` (keyboard device + connection state), plus the input data model: `Binding` (a `kind`/`code`/`value` tuple covering keyboard keys and gamepad button/hat/axis) and `MappingProfiles` (per-device profiles keyed by `"keyboard"` or a gamepad's SDL GUID). `MappingProfiles` is the **single source of truth** for input mapping — used both to render the panel and to resolve gameplay input. Persisted as nested JSON with migration from the old flat `{input_key: keycode}` format.
  - `gamepad_service.py` — `GamepadService(QObject)`: real gamepad support via `pygame.joystick` (SDL `dummy` video driver, polled by its own ~60 Hz `QTimer` on the main thread — SDL requires it). Reads through a `_PadBackend` seam (`_PygamePadBackend` in production, a fake in tests). Handles enumeration, hot-plug, a feed mode (`translate()` state→SNES inputs, with the left stick mirroring the D-Pad) and a capture mode (`detect_binding()` for remapping). Degrades to no-op if pygame is unavailable. Pure `translate`/`detect_binding` functions are tested without hardware.
  - `save_service.py` — `SaveService`: save states persisted to disk under `AppDataLocation/saves/<rom>/` with a real timestamp and a PNG thumbnail; lazy blob reads, delete support.
- `widgets/` — reusable components:
  - `game_stage.py` — `GameStage`, a `QStackedWidget` of the 5 stage views, each (except RUNNING) built from `StateCard`.
  - `video_surface.py` — `VideoSurface` presents the core's `QImage`, applying the four `ScaleMode`s with letterboxing and respecting `devicePixelRatio`.
  - `control_panel.py` — `ControlPanel`, the right-hand 320px panel: segmented control over two scrollable views (Configuración / Visualización del control) plus a reset footer.
  - `mapping_row.py` — `MappingRow`, instantiated ×12 from `SNES_INPUTS`.
  - `controller_diagram.py` — `ControllerDiagram`, painted, doubling as static illustration and live input view.
  - `action_bar.py` / `overlay_action_bar.py` — the fixed bottom 88px action bar (five buttons) and its full-screen auto-hiding overlay variant, which reuses `ActionBar`.
  - `segmented_control.py`, `state_card.py`, `toast.py`, `icons.py` — segmented control widget, reusable state-card scaffold, non-blocking toast feedback, and glyph→`QIcon` helper.
- `theme.py` — all design tokens + light/dark QSS; `settings.py` — `QSettings` persistence. Never hardcode colors in widgets; derive from `theme.py`.

## Core integration (the part that requires care)

The whole emulator depends on correctly speaking the **libretro C ABI** to the `.dylib`. `poc.py` is the reference for how this works:

- Load the core with `ctypes.CDLL`, then register six callbacks **before** `retro_init()`: `retro_set_environment`, `retro_set_video_refresh`, `retro_set_audio_sample`, `retro_set_audio_sample_batch`, `retro_set_input_poll`, `retro_set_input_state`. Callback signatures must match the C ABI exactly (`ctypes.CFUNCTYPE`) — a mismatch crashes silently or corrupts memory.
- **Keep Python references to every callback alive** for the process lifetime. If a `CFUNCTYPE` object is garbage-collected the core calls into freed memory.
- Pixel format is negotiated, not assumed: the core calls `cb_environment` with `RETRO_ENVIRONMENT_SET_PIXEL_FORMAT` (cmd `10`). 0/2 → 16-bit (2 bytes/px), else 32-bit. Video frames arrive with a `pitch` (row stride in bytes) that is **not** `width * bytes_per_pixel`; you must honor `pitch` and crop to the visible `width × height`.
- Input is pulled: the core calls `cb_input_state(port, device, index, id)` each frame. Device `1` = `RETRO_DEVICE_JOYPAD`; `id` is a libretro button constant (see `MAPEO_TECLADO` in `poc.py` for the SNES button → key mapping). Return `1`/`0`.
- Lifecycle: `retro_init()` → build a `retro_game_info` struct (`path`, `data` pointer, `size`, `meta`) → `retro_load_game(byref(info))` → loop `retro_run()` once per frame → `retro_unload_game()` → `retro_deinit()`.

ROMs live in `ROMS/` (`.sfc`/`.smc`; currently `SuperMarioKart.sfc` and `TopGear.sfc`). The PoC hardcodes the path; the GUI opens ROMs via a `QFileDialog` defaulting to `ROMS/`. Filesystem scanning into a metadata DB (the "Library Manager" below) is target architecture, not yet implemented.

## Target architecture (per docs/)

Layered MVC. The key design constraint: **strict isolation between UI and the emulation core via an adapter**, so the core can be swapped without rewriting the app. Planned modules:

- **Presentation** — PySide6 GUI (native macOS look, hardware-accelerated video surface).
- **Main Controller** — orchestrates the other managers; owns session state.
- **Library Manager** — scans the filesystem for ROMs, computes hashes, stores metadata in a local DB.
- **Config Manager** — reads/writes preferences as JSON (controls, video, audio, paths).
- **Input Manager** — detects devices (incl. Bluetooth controllers), maps physical inputs to virtual SNES buttons.
- **Core Adapter** — the only code that touches the `.dylib`; translates Python ↔ C, feeds input, receives video/audio buffers and save-state blobs. This is where `poc.py`'s ctypes logic belongs.

Stack chosen in the spec: PySide6 (GUI), JSON (config), ctypes/cffi (core integration).

## docs/

- `description.md` — backend/architecture spec (layers, modules, responsibilities, recommended tech).
- `descripcion_interfaz.md` — exhaustive, deterministic UI spec for the PySide6 frontend: widget hierarchy, layouts, the five game-stage states (empty/loading/running/paused/error), the 12-row controller mapping panel, light/dark theme tokens, typography, spacing, and interaction flows. Follow it precisely when building UI; it is written as direct input for coding agents.

Documentation and UI strings are in **Spanish** — match that language in user-facing text and keep it consistent with existing docs.
