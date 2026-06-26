"""Utilidad para construir iconos a partir de glifos.

La especificacion recomienda iconografia sistemica (SF Symbols en macOS,
iconos de linea en Windows). Para mantener la demo autocontenida y sin
dependencias de recursos externos, se renderizan glifos emoji/unicode a un
QIcon con el tamano y color adecuados.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap


def glyph_icon(glyph: str, size: int = 24, color: str | None = None) -> QIcon:
    pm = QPixmap(QSize(size, size))
    pm.setDevicePixelRatio(2.0)
    pm = QPixmap(QSize(size * 2, size * 2))
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    font = QFont()
    font.setPixelSize(int(size * 2 * 0.82))
    painter.setFont(font)
    if color:
        painter.setPen(QColor(color))
    painter.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, glyph)
    painter.end()
    pm.setDevicePixelRatio(2.0)
    return QIcon(pm)
