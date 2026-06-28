"""Componente de retroalimentacion no bloqueante (toast).

Muestra una confirmacion breve superpuesta sobre el widget padre y se
autooculta. Reutilizable para guardado, carga y otros avisos efimeros.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QWidget

from ..theme import LIGHT, Palette


class Toast(QLabel):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setVisible(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._palette = LIGHT
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette

    def show_message(self, text: str, kind: str = "ok", msec: int = 2000) -> None:
        p = self._palette
        bg = {
            "ok": p.connected,
            "error": p.error,
            "info": p.accent,
        }.get(kind, p.connected)
        self.setStyleSheet(
            f"background-color: {bg}; color: {p.on_accent}; border-radius: 8px;"
            "padding: 10px 18px; font-size: 13px; font-weight: 600;"
        )
        self.setText(text)
        self.adjustSize()
        self._reposition()
        self.setVisible(True)
        self.raise_()
        self._timer.start(msec)

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if not parent:
            return
        x = (parent.width() - self.width()) // 2
        y = parent.height() - self.height() - 110
        self.move(max(0, x), max(0, y))
