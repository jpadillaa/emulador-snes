"""Escenario de juego.

Contenedor central con un QStackedWidget interno que conmuta entre las cinco
vistas de estado. La vista de ejecucion aloja la superficie de video; el
resto muestran tarjetas de estado. La vista de pausa superpone una capa
oscura traslucida sobre el ultimo fotograma.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..state import ScaleMode, SessionState
from ..theme import STAGE_PADDING
from .state_card import StateCard
from .video_surface import VideoSurface


class _PauseView(QWidget):
    """Muestra el ultimo fotograma atenuado con una tarjeta de pausa encima."""
    resume_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._frame: QImage | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._card = StateCard(
            "⏸", "PAUSA", "Pulsa Reanudar, usa el atajo o haz clic aquí para continuar."
        )
        layout.addWidget(self._card)

    def set_frame(self, image: QImage | None) -> None:
        self._frame = image.copy() if image is not None else None
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        if self._frame is not None and not self._frame.isNull():
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.drawImage(self.rect(), self._frame)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 150))  # capa traslucida
        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.resume_requested.emit()


class GameStage(QFrame):
    request_load = Signal()         # boton de la tarjeta vacia / reintentar carga
    retry_requested = Signal()      # reintentar desde error
    close_error_requested = Signal()  # cerrar error -> estado vacio
    resume_requested = Signal()     # reanudar desde pausa

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("EscenarioJuego")

        root = QVBoxLayout(self)
        root.setContentsMargins(STAGE_PADDING, STAGE_PADDING, STAGE_PADDING, STAGE_PADDING)

        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        # 0 - Vacio
        self._empty = StateCard(
            "🎮",
            "NINGÚN JUEGO CARGADO",
            "Carga una ROM de SNES para comenzar a jugar.",
        )
        self._empty.add_action("Cargar juego", self.request_load.emit, primary=True)
        self._stack.addWidget(self._empty)

        # 1 - Cargando
        self._loading = StateCard("⏳", "CARGANDO", "", indeterminate=True)
        self._stack.addWidget(self._loading)

        # 2 - Ejecucion
        run_wrap = QWidget()
        run_layout = QVBoxLayout(run_wrap)
        run_layout.setContentsMargins(0, 0, 0, 0)
        self._video = VideoSurface()
        run_layout.addWidget(self._video)
        self._stack.addWidget(run_wrap)

        # 3 - Pausa
        self._pause = _PauseView()
        self._pause.resume_requested.connect(self.resume_requested.emit)
        self._stack.addWidget(self._pause)

        # 4 - Error
        self._error = StateCard("⚠️", "ERROR", "")
        self._error.add_action("Reintentar", self.retry_requested.emit, primary=True)
        self._error.add_action("Cerrar", self.close_error_requested.emit)
        self._stack.addWidget(self._error)

        self._index = {
            SessionState.EMPTY: 0,
            SessionState.LOADING: 1,
            SessionState.RUNNING: 2,
            SessionState.PAUSED: 3,
            SessionState.ERROR: 4,
        }

    # -- API -----------------------------------------------------------------
    @property
    def video(self) -> VideoSurface:
        return self._video

    def show_state(self, state: SessionState) -> None:
        if state == SessionState.PAUSED:
            self._pause.set_frame(self._video.grab().toImage())
        self._stack.setCurrentIndex(self._index[state])

    def set_loading_filename(self, name: str) -> None:
        self._loading.set_description(name)

    def set_error_message(self, message: str) -> None:
        self._error.set_description(message)

    def set_scale_mode(self, mode: ScaleMode) -> None:
        self._video.set_mode(mode)

    def update_frame(self, image: QImage) -> None:
        self._video.set_image(image)

    def clear_video(self) -> None:
        self._video.clear()
