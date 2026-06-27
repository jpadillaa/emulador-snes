"""Barra de acciones inferior.

Contenedor anclado bajo el escenario, altura fija 88 px, que centra un grupo
de cinco botones de accion (icono arriba, etiqueta principal y secundaria)
separados por divisores verticales. Reutilizable: tambien alimenta la barra
superpuesta de pantalla completa.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QToolButton,
)

from ..theme import ACTION_BAR_HEIGHT
from .icons import glyph_icon


@dataclass(frozen=True)
class ActionSpec:
    key: str
    glyph: str
    label: str                   # etiqueta unica, corta y puntual
    needs_session: bool          # se deshabilita en estado vacio


ACTIONS = [
    ActionSpec("load_game", "📂", "Cargar juego", False),
    ActionSpec("save_state", "💾", "Guardar partida", True),
    ActionSpec("load_state", "📥", "Cargar partida", True),
    ActionSpec("quit_game", "🚪", "Salir", True),
    ActionSpec("fullscreen", "⛶", "Pantalla completa", False),
]


def _make_button(spec: ActionSpec) -> QToolButton:
    btn = QToolButton()
    btn.setObjectName("AccionBarra")
    btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
    btn.setIcon(glyph_icon(spec.glyph, 24))
    btn.setText(spec.label)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setAutoRaise(True)
    btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
    return btn


class ActionBar(QFrame):
    triggered = Signal(str)         # emite la key de la accion

    def __init__(self, fixed_height: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("BarraAcciones")
        if fixed_height:
            self.setFixedHeight(ACTION_BAR_HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)
        layout.addStretch()

        self._buttons: dict[str, QToolButton] = {}
        for i, spec in enumerate(ACTIONS):
            btn = _make_button(spec)
            btn.clicked.connect(lambda _=False, k=spec.key: self.triggered.emit(k))
            self._buttons[spec.key] = btn
            layout.addWidget(btn)
            if i < len(ACTIONS) - 1:
                layout.addWidget(self._separator())
        layout.addStretch()

    def _separator(self) -> QFrame:
        sep = QFrame()
        sep.setObjectName("Separador")
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedHeight(40)
        sep.setFixedWidth(1)
        return sep

    def set_session_active(self, active: bool) -> None:
        """Habilita/deshabilita las acciones dependientes de sesion."""
        for spec in ACTIONS:
            if spec.needs_session:
                self._buttons[spec.key].setEnabled(active)

    def button(self, key: str) -> QToolButton:
        return self._buttons[key]
