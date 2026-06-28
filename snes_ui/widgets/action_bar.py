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
from .icons import line_icon

# Color de respaldo hasta que MainWindow aplica el tema y re-tiñe los iconos.
_DEFAULT_ICON_COLOR = "#86868B"


@dataclass(frozen=True)
class ActionSpec:
    key: str
    icon: str                    # nombre de icono en widgets.icons
    label: str                   # etiqueta unica, corta y puntual
    needs_session: bool          # se deshabilita en estado vacio


ACTIONS = [
    ActionSpec("load_game", "folder", "Cargar juego", False),
    ActionSpec("save_state", "save", "Guardar partida", True),
    ActionSpec("load_state", "restore", "Cargar partida", True),
    ActionSpec("quit_game", "exit", "Salir", True),
    ActionSpec("fullscreen", "fullscreen", "Pantalla completa", False),
]


def _make_button(spec: ActionSpec, color: str) -> QToolButton:
    btn = QToolButton()
    btn.setObjectName("AccionBarra")
    btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
    btn.setIcon(line_icon(spec.icon, 24, color))
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

        self._icon_color = _DEFAULT_ICON_COLOR
        self._buttons: dict[str, QToolButton] = {}
        for i, spec in enumerate(ACTIONS):
            btn = _make_button(spec, self._icon_color)
            btn.clicked.connect(lambda _=False, k=spec.key: self.triggered.emit(k))
            self._buttons[spec.key] = btn
            layout.addWidget(btn)
            if i < len(ACTIONS) - 1:
                layout.addWidget(self._separator())
        layout.addStretch()

    def set_icon_color(self, color: str) -> None:
        """Re-tiñe los iconos al color del tema vigente."""
        self._icon_color = color
        for spec in ACTIONS:
            self._buttons[spec.key].setIcon(line_icon(spec.icon, 24, color))

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
