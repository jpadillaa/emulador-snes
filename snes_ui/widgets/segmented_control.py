"""Control segmentado.

Dos opciones mutuamente exclusivas con apariencia de control segmentado
nativo (pista hundida, pulgar activo). Se modela con un QButtonGroup
exclusivo sobre dos QPushButton checkable, segun la especificacion.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QPushButton,
)


class SegmentedControl(QFrame):
    changed = Signal(int)           # indice seleccionado

    def __init__(self, options: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ControlSegmentado")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(3)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[QPushButton] = []

        for i, text in enumerate(options):
            btn = QPushButton(text)
            btn.setObjectName("SegmentoPestana")
            btn.setCheckable(True)
            btn.setCursor(btn.cursor())
            self._group.addButton(btn, i)
            self._buttons.append(btn)
            layout.addWidget(btn)

        self._group.idClicked.connect(self.changed.emit)
        if self._buttons:
            self._buttons[0].setChecked(True)

    def set_current(self, index: int) -> None:
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)
            self.changed.emit(index)

    def current(self) -> int:
        return self._group.checkedId()
