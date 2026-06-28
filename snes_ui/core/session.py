"""Controlador de sesion: maquina de estados central de la aplicacion.

Centraliza las transiciones entre los cinco estados de la interfaz y conduce
el bucle de fotogramas del nucleo mediante un QTimer. La ventana principal
observa sus senales para conmutar vistas y habilitar/deshabilitar acciones,
de modo que la logica de estado vive en un unico lugar.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from .adapter import EmulatorCore
from ..services.sram_service import SramStore
from ..state import SessionState


class SessionController(QObject):
    state_changed = Signal(SessionState)          # nuevo estado
    frame_ready = Signal()                         # hay un nuevo fotograma
    error_raised = Signal(str)                     # mensaje de error
    rom_changed = Signal(str)                      # nombre legible de la ROM
    dirty_changed = Signal(bool)                   # hay progreso sin guardar

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

    # -- propiedades ---------------------------------------------------------
    @property
    def core(self) -> EmulatorCore:
        return self._core

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def rom_name(self) -> str:
        return self._rom_name

    @property
    def has_session(self) -> bool:
        return self._state in (SessionState.RUNNING, SessionState.PAUSED)

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    # -- transiciones --------------------------------------------------------
    def _set_state(self, state: SessionState) -> None:
        if state != self._state:
            self._state = state
            self.state_changed.emit(state)

    def _set_dirty(self, value: bool) -> None:
        if value != self._dirty:
            self._dirty = value
            self.dirty_changed.emit(value)

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

    def fail(self, message: str) -> None:
        self._timer.stop()
        self._core.stop_audio()
        self.error_raised.emit(message)
        self._set_state(SessionState.ERROR)

    def pause(self) -> None:
        if self._state == SessionState.RUNNING:
            self._timer.stop()
            self._core.pause_audio()
            self._set_state(SessionState.PAUSED)

    def resume(self) -> None:
        if self._state == SessionState.PAUSED:
            fps = self._core.av_info().fps or 60.0
            self._timer.start(int(1000 / fps))
            self._core.resume_audio()
            self._set_state(SessionState.RUNNING)

    def toggle_pause(self) -> None:
        if self._state == SessionState.RUNNING:
            self.pause()
        elif self._state == SessionState.PAUSED:
            self.resume()

    def _flush_sram(self) -> None:
        """Vuelca el SRAM del juego actual al disco (si hay ROM)."""
        if self._rom_name:
            self._sram.write(self._rom_name, self._core.get_sram())

    def flush_sram(self) -> None:
        """Punto de volcado público (lo usa el cierre de la app)."""
        self._flush_sram()

    def quit_session(self) -> None:
        """Cierra la sesion activa y vuelve al estado vacio."""
        self._timer.stop()
        self._flush_sram()
        self._core.unload()
        self._rom_path = None
        self._rom_name = ""
        self._set_dirty(False)
        self._set_state(SessionState.EMPTY)

    def reset_to_empty(self) -> None:
        """Salida limpia desde el estado de error hacia vacio."""
        self._timer.stop()
        self._rom_path = None
        self._rom_name = ""
        self._set_state(SessionState.EMPTY)

    # -- guardado / carga (simulados a nivel de nucleo) ----------------------
    def save_state(self) -> bytes:
        blob = self._core.save_state()
        self._set_dirty(False)
        return blob

    def load_state(self, blob: bytes) -> bool:
        ok = self._core.load_state(blob)
        if ok and self._state == SessionState.PAUSED:
            self.resume()
        return ok

    def mark_dirty(self) -> None:
        if self.has_session:
            self._set_dirty(True)

    # -- bucle de fotogramas -------------------------------------------------
    def _on_tick(self) -> None:
        self._core.run_frame()
        # El avance de juego genera progreso sin guardar.
        if not self._dirty:
            self._set_dirty(True)
        self.frame_ready.emit()
