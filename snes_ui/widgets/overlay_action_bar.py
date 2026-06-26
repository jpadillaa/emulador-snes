"""Barra de acciones superpuesta para el modo de pantalla completa.

Aparece cuando el cursor se acerca al borde inferior y se autooculta tras
2,5 segundos de inactividad. Reutiliza ActionBar para mantener identica la
disposicion de botones.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from .action_bar import ActionBar

AUTOHIDE_MS = 2500
EDGE_THRESHOLD = 120        # px desde el borde inferior que revelan la barra


class OverlayActionBar(QWidget):
    triggered = Signal(str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._bar = ActionBar(fixed_height=True)
        self._bar.triggered.connect(self.triggered.emit)
        layout.addWidget(self._bar)
        self.setVisible(False)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def set_session_active(self, active: bool) -> None:
        self._bar.set_session_active(active)

    def reveal(self) -> None:
        self._reposition()
        self.setVisible(True)
        self.raise_()
        self._timer.start(AUTOHIDE_MS)

    def handle_mouse_y(self, y: int) -> None:
        """Revela la barra si el cursor esta cerca del borde inferior."""
        parent = self.parentWidget()
        if not parent:
            return
        if y >= parent.height() - EDGE_THRESHOLD:
            self.reveal()

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if not parent:
            return
        margin = 24
        w = min(parent.width() - 2 * margin, 760)
        self.setFixedWidth(w)
        self.adjustSize()
        x = (parent.width() - self.width()) // 2
        y = parent.height() - self.height() - margin
        self.move(x, y)
