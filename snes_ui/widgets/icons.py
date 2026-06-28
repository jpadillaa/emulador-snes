"""Iconografía de línea monocromática (estilo SF Symbols), autocontenida.

La especificación recomienda iconografía sistémica (SF Symbols en macOS).
Para no depender de recursos externos ni del set instalado en el sistema, los
iconos se definen como trazos SVG inline (grid 24×24, trazo redondeado) y se
renderizan con ``QSvgRenderer`` tiñéndolos con el color del tema vigente.

Como un pixmap monocromático no se adapta solo al cambio de tema claro/oscuro
(a diferencia de un emoji multicolor), cada icono se **regenera** con el color
adecuado cuando el tema cambia. Los widgets que muestran iconos exponen un
método para re-teñirlos; ``MainWindow`` lo invoca al aplicar el tema.
"""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt, QSize
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# Cuerpo SVG de cada icono (sin la etiqueta <svg> envolvente). El trazo y los
# remates se fijan en la raíz; los círculos rellenos sobrescriben fill/stroke.
_ICONS: dict[str, str] = {
    # Barra de acciones
    "folder": (
        '<path d="M3.5 7.5A1.5 1.5 0 0 1 5 6h3.6a1.5 1.5 0 0 1 1.2.6L11 8.2'
        'a1.5 1.5 0 0 0 1.2.6H19A1.5 1.5 0 0 1 20.5 10.3V17A1.5 1.5 0 0 1 19 18.5'
        'H5A1.5 1.5 0 0 1 3.5 17Z"/>'
    ),
    "save": (
        '<path d="M5 14.5V17A1.5 1.5 0 0 0 6.5 18.5h11A1.5 1.5 0 0 0 19 17V14.5"/>'
        '<path d="M12 4v9.5"/><path d="M8.25 10 12 13.75 15.75 10"/>'
    ),
    "restore": (
        '<path d="M20 12a8 8 0 1 1-2.34-5.66"/>'
        '<path d="M20 4.5V8h-3.5"/>'
        '<path d="M12 8.5V12l2.5 1.6"/>'
    ),
    "exit": (
        '<path d="M14 6V5.5A1.5 1.5 0 0 0 12.5 4h-6A1.5 1.5 0 0 0 5 5.5v13'
        'A1.5 1.5 0 0 0 6.5 20h6A1.5 1.5 0 0 0 14 18.5V18"/>'
        '<path d="M10 12h10"/><path d="M16.5 8.5 20 12l-3.5 3.5"/>'
    ),
    "fullscreen": (
        '<path d="M9 4H5.5A1.5 1.5 0 0 0 4 5.5V9"/>'
        '<path d="M15 4h3.5A1.5 1.5 0 0 1 20 5.5V9"/>'
        '<path d="M20 15v3.5A1.5 1.5 0 0 1 18.5 20H15"/>'
        '<path d="M4 15v3.5A1.5 1.5 0 0 0 5.5 20H9"/>'
    ),
    "refresh": (
        '<path d="M19.5 12a7.5 7.5 0 1 1-2.05-5.15"/>'
        '<path d="M19.5 4.5V9H15"/>'
    ),
    "reset": (  # flecha circular antihoraria (restablecer)
        '<path d="M4.5 12a7.5 7.5 0 1 0 2.05-5.15"/>'
        '<path d="M4.5 4.5V9H9"/>'
    ),
    # Tarjetas de estado
    "controller": (
        '<path d="M8.2 8.5h7.6a4.5 4.5 0 0 1 4.43 5.32l-.62 3.3A2.4 2.4 0 0 1'
        ' 16.3 18l-1.5-2H9.2L7.7 18a2.4 2.4 0 0 1-4.31-.88l-.62-3.3A4.5 4.5 0'
        ' 0 1 8.2 8.5Z"/>'
        '<path d="M6.2 12.3h2.6"/><path d="M7.5 11v2.6"/>'
        '<circle cx="15.4" cy="11.6" r="1" fill="{color}" stroke="none"/>'
        '<circle cx="17.3" cy="13.4" r="1" fill="{color}" stroke="none"/>'
    ),
    "hourglass": (
        '<path d="M7 4.5h10"/><path d="M7 19.5h10"/>'
        '<path d="M8.25 4.5v2.3L12 11l3.75-4.2V4.5"/>'
        '<path d="M8.25 19.5v-2.3L12 13l3.75 4.2v2.3"/>'
    ),
    "pause": (
        '<path d="M9 5.5v13"/><path d="M15 5.5v13"/>'
    ),
    "warning": (
        '<path d="M12 4.5 21 19.5H3Z"/>'
        '<path d="M12 10v4.2"/>'
        '<circle cx="12" cy="17.3" r="0.9" fill="{color}" stroke="none"/>'
    ),
}


def icon_names() -> tuple[str, ...]:
    return tuple(_ICONS)


def _render(name: str, size: int, color: str, stroke: float) -> QPixmap:
    body = _ICONS[name].replace("{color}", color)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="{stroke}" '
        f'stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    dpr = 2.0
    pm = QPixmap(QSize(int(size * dpr), int(size * dpr)))
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size * dpr, size * dpr))
    painter.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def line_pixmap(name: str, size: int = 24, color: str = "#000000",
                stroke: float = 1.7) -> QPixmap:
    """Pixmap del icono teñido (para QLabel / vistas pintadas)."""
    return _render(name, size, color, stroke)


def line_icon(name: str, size: int = 24, color: str = "#000000",
              stroke: float = 1.7) -> QIcon:
    """QIcon del icono teñido (para botones)."""
    return QIcon(_render(name, size, color, stroke))
