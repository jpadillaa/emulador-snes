"""Fila de mapeo reutilizable.

Representa una asignacion de una entrada logica del SNES a una entrada
fisica. Parametrizable por icono, nombre y asignacion inicial; se instancia
doce veces a partir de la tabla de asignacion. Al pulsar el boton entra en
estado de escucha mostrando "Presiona un botón"; el coordinador externo
asigna la siguiente entrada detectada o cancela con Escape.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy


class MappingRow(QFrame):
    listen_requested = Signal(str)      # input_key

    LISTEN_TEXT = "Presiona un botón"

    def __init__(self, input_key: str, icon: str, name: str, assignment: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("FilaMapeo")
        self._key = input_key
        self._assignment = assignment
        self._listening = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 12, 10)
        layout.setSpacing(10)

        icon_lbl = QLabel(icon)
        icon_lbl.setObjectName("IconoEntrada")
        icon_lbl.setFixedWidth(18)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_lbl)

        name_lbl = QLabel(name)
        name_lbl.setProperty("role", "body-lg")
        # Permite que el nombre se encoja antes que desbordar el panel fijo.
        name_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(name_lbl, stretch=1)

        self._btn = QPushButton(assignment)
        self._btn.setObjectName("BotonAsignacion")
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.clicked.connect(self._on_click)
        layout.addWidget(self._btn)

    @property
    def input_key(self) -> str:
        return self._key

    def _on_click(self) -> None:
        if self._listening:
            return
        self.listen_requested.emit(self._key)

    def set_listening(self, value: bool) -> None:
        self._listening = value
        self._btn.setText(self.LISTEN_TEXT if value else self._assignment)
        self._btn.setProperty("listening", "true" if value else "false")
        # Forzar re-evaluacion del QSS dependiente de la propiedad.
        self._btn.style().unpolish(self._btn)
        self._btn.style().polish(self._btn)

    def set_assignment(self, physical: str) -> None:
        self._assignment = physical
        self._listening = False
        self._btn.setText(physical)
        self._btn.setProperty("listening", "false")
        self._btn.style().unpolish(self._btn)
        self._btn.style().polish(self._btn)
