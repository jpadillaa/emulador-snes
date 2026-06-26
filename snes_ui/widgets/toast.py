"""Componente de retroalimentacion no bloqueante (toast).

Muestra una confirmacion breve superpuesta sobre el widget padre y se
autooculta. Reutilizable para guardado, carga y otros avisos efimeros.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QWidget


class Toast(QLabel):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setVisible(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text: str, kind: str = "ok", msec: int = 2000) -> None:
        bg = {
            "ok": "#34C759",
            "error": "#FF3B30",
            "info": "#007AFF",
        }.get(kind, "#34C759")
        self.setStyleSheet(
            f"background-color: {bg}; color: white; border-radius: 8px;"
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
