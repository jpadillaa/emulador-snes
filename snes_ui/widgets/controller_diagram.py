"""Diagrama de mando SNES pintado.

Dibuja una representacion estilizada de un control SNES y resalta en tiempo
real las entradas presionadas. Se usa tanto como ilustracion estatica en la
seccion de asignacion como en la vista de visualizacion del control en vivo.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..theme import Palette


class ControllerDiagram(QWidget):
    def __init__(self, palette: Palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._p = palette
        self._pressed: set[str] = set()
        self.setMinimumHeight(120)

    def set_palette(self, palette: Palette) -> None:
        self._p = palette
        self.update()

    def set_pressed(self, pressed: set[str]) -> None:
        if pressed != self._pressed:
            self._pressed = set(pressed)
            self.update()

    def _color(self, key: str, base: str) -> QColor:
        return QColor(self._p.accent) if key in self._pressed else QColor(base)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Lienzo con relacion 2:1 centrado; toda la geometria se calcula en
        # pixeles a partir de la unidad u = altura del lienzo / 100.
        w, h = self.width(), self.height()
        cw = min(w, h * 2.0)
        ch = cw / 2.0
        ox = (w - cw) / 2.0
        oy = (h - ch) / 2.0
        u = ch / 100.0  # unidad de trabajo

        def px(nx: float) -> float:
            return ox + nx * cw

        def py(ny: float) -> float:
            return oy + ny * ch

        outline = QColor(self._p.border)

        # --- Hombros L / R (detras del cuerpo, sobre el borde superior) ---
        shoulder_w, shoulder_h = 22 * u, 11 * u
        for key, cx_n in (("l", 0.20), ("r", 0.80)):
            rect = QRectF(px(cx_n) - shoulder_w / 2, py(0.08),
                          shoulder_w, shoulder_h + 8 * u)
            p.setPen(QPen(outline, max(1.0, u)))
            p.setBrush(self._color(key, self._p.elevated))
            p.drawRoundedRect(rect, 5 * u, 5 * u)
            self._centered_text(p, rect, key.upper(), 11 * u,
                                self._p.text_secondary, top=True)

        # --- Cuerpo del mando ("dog-bone" SNES) ---
        body = QRectF(px(0.03), py(0.20), cw * 0.94, ch * 0.62)
        p.setPen(QPen(outline, max(1.0, 1.4 * u)))
        p.setBrush(QColor(self._p.elevated_max))
        p.drawRoundedRect(body, body.height() / 2.0, body.height() / 2.0)

        # --- D-Pad (cruz) a la izquierda ---
        dpx, dpy = px(0.205), py(0.51)
        th = 13 * u           # grosor del brazo
        al = 19 * u           # longitud del brazo desde el centro
        # base de la cruz
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._p.surface))
        vbar = QRectF(dpx - th / 2, dpy - al, th, 2 * al)
        hbar = QRectF(dpx - al, dpy - th / 2, 2 * al, th)
        p.drawRoundedRect(vbar, 3 * u, 3 * u)
        p.drawRoundedRect(hbar, 3 * u, 3 * u)
        # brazos presionados (resaltado)
        arms = {
            "up": QRectF(dpx - th / 2, dpy - al, th, al),
            "down": QRectF(dpx - th / 2, dpy, th, al),
            "left": QRectF(dpx - al, dpy - th / 2, al, th),
            "right": QRectF(dpx, dpy - th / 2, al, th),
        }
        for key, rect in arms.items():
            if key in self._pressed:
                p.setBrush(QColor(self._p.accent))
                p.drawRoundedRect(rect, 3 * u, 3 * u)

        # --- Select / Start (centro, inclinados) ---
        p.save()
        p.translate(px(0.49), py(0.62))
        p.rotate(-22)
        pill_w, pill_h, gap = 14 * u, 6 * u, 4 * u
        for i, key in enumerate(("select", "start")):
            rect = QRectF(-pill_w - gap / 2 + i * (pill_w + gap), -pill_h / 2,
                          pill_w, pill_h)
            p.setBrush(self._color(key, self._p.border_subtle))
            p.drawRoundedRect(rect, pill_h / 2, pill_h / 2)
        p.restore()

        # --- Botones de accion (diamante Y/X/B/A) a la derecha ---
        fbx, fby = px(0.80), py(0.51)
        spread, br = 17 * u, 10.5 * u
        # Disposicion SNES: X arriba, B abajo, Y izquierda, A derecha.
        buttons = [
            ("x", QPointF(fbx, fby - spread)),
            ("b", QPointF(fbx, fby + spread)),
            ("y", QPointF(fbx - spread, fby)),
            ("a", QPointF(fbx + spread, fby)),
        ]
        font = QFont()
        font.setPixelSize(max(8, int(13 * u)))
        font.setBold(True)
        p.setFont(font)
        for key, c in buttons:
            rect = QRectF(c.x() - br, c.y() - br, 2 * br, 2 * br)
            p.setPen(QPen(outline, max(1.0, u)))
            p.setBrush(self._color(key, self._p.border_subtle))
            p.drawEllipse(rect)
            self._centered_text(p, rect, key.upper(), 13 * u,
                                self._p.text_primary)
        p.end()

    def _centered_text(self, p: QPainter, rect: QRectF, text: str, size: float,
                       color: str, top: bool = False) -> None:
        font = QFont()
        font.setPixelSize(max(7, int(size)))
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(color))
        align = Qt.AlignmentFlag.AlignHCenter | (
            Qt.AlignmentFlag.AlignTop if top else Qt.AlignmentFlag.AlignVCenter)
        p.drawText(rect, align, text)
        p.setPen(Qt.PenStyle.NoPen)
