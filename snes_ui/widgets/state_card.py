"""Tarjeta de estado reutilizable.

Las vistas vacio, cargando, pausa y error comparten la misma estructura:
icono superior, titulo, linea descriptiva y, opcionalmente, una pildora con
el sistema y/o acciones primarias. Este widget parametriza esa estructura.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class StateCard(QWidget):
    def __init__(
        self,
        icon: str,
        title: str,
        description: str = "",
        pill: str | None = None,
        indeterminate: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("TarjetaEstado")

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QVBoxLayout()
        card.setSpacing(12)
        card.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon = QLabel(icon)
        self._icon.setObjectName("IconoTarjeta")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card.addWidget(self._icon)

        self._title = QLabel(title)
        self._title.setProperty("role", "card-title")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card.addWidget(self._title)

        self._desc = QLabel(description)
        self._desc.setProperty("role", "card-desc")
        self._desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._desc.setWordWrap(True)
        self._desc.setVisible(bool(description))
        card.addWidget(self._desc)

        if indeterminate:
            bar = QProgressBar()
            bar.setRange(0, 0)          # indeterminado
            bar.setFixedWidth(220)
            bar.setTextVisible(False)
            wrap = QHBoxLayout()
            wrap.addStretch()
            wrap.addWidget(bar)
            wrap.addStretch()
            card.addLayout(wrap)

        if pill:
            self._pill_wrap = QHBoxLayout()
            self._pill_wrap.addStretch()
            pill_frame = QFrame()
            pill_frame.setObjectName("Pildora")
            pl = QHBoxLayout(pill_frame)
            pl.setContentsMargins(10, 2, 10, 2)
            lbl = QLabel(pill)
            lbl.setProperty("role", "pildora")
            pl.addWidget(lbl)
            self._pill_wrap.addWidget(pill_frame)
            self._pill_wrap.addStretch()
            card.addLayout(self._pill_wrap)

        self._actions_row = QHBoxLayout()
        self._actions_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._actions_row.setSpacing(8)
        card.addLayout(self._actions_row)

        outer.addLayout(card)

    def set_description(self, text: str) -> None:
        self._desc.setText(text)
        self._desc.setVisible(bool(text))

    def add_action(self, text: str, on_click: Callable[[], None], primary: bool = False) -> QPushButton:
        btn = QPushButton(text)
        if primary:
            btn.setObjectName("Primario")
        btn.clicked.connect(on_click)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._actions_row.addWidget(btn)
        return btn
