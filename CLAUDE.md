# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A SNES emulator desktop app built in Python that wraps a third-party libretro emulation core (`snes9x_libretro`). The Python layer is purely presentation + management; emulation happens inside the compiled C/C++ core, reached over the libretro C ABI via `ctypes`.

Two parts coexist:
- **`poc.py`** — a single-file proof-of-concept (pygame window) that drives the real libretro core. The original reference for the core integration.
- **`snes_ui/` + `main.py`** — the PySide6 desktop GUI implementing `docs/descripcion_interfaz.md`. **It now drives the real libretro core** (`LibretroCore` in `snes_ui/core/adapter.py`, ported from `poc.py`), selected by the `create_core()` factory; if the `.dylib` can't load it falls back to `MockEmulatorCore` so the UI still runs in demo mode. Audio output is the one piece intentionally left unwired (matching `poc.py`).

When building UI features, treat `docs/descripcion_interfaz.md` as the authoritative spec; `docs/IMPLEMENTACION.md` records the architecture and the decisions taken for spec ambiguities.

## Commands

```bash
source .venv/bin/activate        # Python 3.14; deps in requirements.txt (PySide6 6.11, pygame)
python main.py                   # run the PySide6 GUI (mock core)
python poc.py                    # run the libretro PoC (loads ./ROMS/SuperMarioKart.sfc, pygame window)
```

Render the GUI headless for verification (offscreen): set `QT_QPA_PLATFORM=offscreen`, build `MainWindow`, drive `SessionController`, and `widget.grab().save(path)` to capture state screenshots.

There is no test suite or linter configured. The libretro core (`kernel/snes9x_libretro.dylib`) is a prebuilt binary checked into the repo, not built here.

## GUI architecture (snes_ui/)

Strict UI ↔ core isolation via an adapter so the core can be replaced without touching the UI:
- `core/adapter.py` — `EmulatorCore` ABC (the only contract the UI knows); `LibretroCore` (real ctypes binding to `snes9x_libretro`, video as `QImage` honoring pixel format + pitch, pull-model input, real serialize/unserialize save states, real-time audio); `MockEmulatorCore` (animated synthetic frames, fallback); `create_core()` picks one. **Critical**: `LibretroCore` keeps its `CFUNCTYPE` callbacks as instance attrs — letting them be GC'd crashes the core. See `docs/IMPLEMENTACION.md` for the integration decisions.
- `core/audio.py` — `AudioPlayer` wraps `QAudioSink` (QtMultimedia, no new dep) in push mode. The libretro audio-batch callback enqueues S16 stereo samples; `LibretroCore.run_frame` flushes them after `retro_run`. Audio lifecycle (`start/pause/resume/stop_audio`) lives on the `EmulatorCore` ABC (no-op default) and is driven by `SessionController` on state transitions. All on the main thread — `QAudioSink` plays on its own backend thread, writes never block.
- `core/session.py` — `SessionController`: the single state machine for the five UI states (EMPTY/LOADING/RUNNING/PAUSED/ERROR) and a `QTimer` frame loop. Emits signals; `MainWindow` observes them to switch stage views and enable/disable session-dependent actions. **All session-state logic lives here** — don't scatter it into widgets.
- `services/` — `InputService` (mock device enumeration, connection state, key profile, `MappingModel` of the 12 SNES inputs) and `SaveService` (in-memory save states).
- `widgets/` — reusable components; notably `MappingRow` (instantiated ×12 from `SNES_INPUTS`), `GameStage` (QStackedWidget of the 5 views), `ControllerDiagram` (painted, doubles as static illustration and live input view).
- `theme.py` — all design tokens + light/dark QSS; `settings.py` — `QSettings` persistence. Never hardcode colors in widgets; derive from `theme.py`.

## Core integration (the part that requires care)

The whole emulator depends on correctly speaking the **libretro C ABI** to the `.dylib`. `poc.py` is the reference for how this works:

- Load the core with `ctypes.CDLL`, then register six callbacks **before** `retro_init()`: `retro_set_environment`, `retro_set_video_refresh`, `retro_set_audio_sample`, `retro_set_audio_sample_batch`, `retro_set_input_poll`, `retro_set_input_state`. Callback signatures must match the C ABI exactly (`ctypes.CFUNCTYPE`) — a mismatch crashes silently or corrupts memory.
- **Keep Python references to every callback alive** for the process lifetime. If a `CFUNCTYPE` object is garbage-collected the core calls into freed memory.
- Pixel format is negotiated, not assumed: the core calls `cb_environment` with `RETRO_ENVIRONMENT_SET_PIXEL_FORMAT` (cmd `10`). 0/2 → 16-bit (2 bytes/px), else 32-bit. Video frames arrive with a `pitch` (row stride in bytes) that is **not** `width * bytes_per_pixel`; you must honor `pitch` and crop to the visible `width × height`.
- Input is pulled: the core calls `cb_input_state(port, device, index, id)` each frame. Device `1` = `RETRO_DEVICE_JOYPAD`; `id` is a libretro button constant (see `MAPEO_TECLADO` in `poc.py` for the SNES button → key mapping). Return `1`/`0`.
- Lifecycle: `retro_init()` → build a `retro_game_info` struct (`path`, `data` pointer, `size`, `meta`) → `retro_load_game(byref(info))` → loop `retro_run()` once per frame → `retro_unload_game()` → `retro_deinit()`.

ROMs live in `ROMS/` (`.sfc`/`.smc`). The PoC hardcodes the path; the real app scans directories.

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
