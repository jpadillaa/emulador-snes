"""Vista de biblioteca: cuadrícula de juegos en el escenario vacío.

Cabecera con búsqueda y acciones (re-escanear, gestionar carpetas) sobre un
``QListWidget`` en modo icono. Cada juego se dibuja como una **tarjeta llena**
de su color característico (estable por nombre) mediante un ``QStyledItemDelegate``
a medida: degradado suave del color, un monograma fantasma como mini-carátula y
el nombre en una banda inferior con texto de contraste automático. Si no hay
juegos, muestra una guía con las acciones para añadir una carpeta o abrir un
archivo suelto.
"""
from __future__ import annotations

import hashlib

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..services.library_service import GameEntry
from ..theme import Palette
from .icons import line_icon
from .state_card import StateCard

_PATH_ROLE = Qt.ItemDataRole.UserRole

# Geometría de la tarjeta (la celda del grid es mayor; el delegate deja aire
# para la sombra de elevación al hover).
_CELL = QSize(184, 178)
_CARD_INSET = 10
_CARD_RADIUS = 18.0
_NAME_BAND = 52  # alto reservado para el nombre en la base


class _GameSkin:
    """Colores derivados de forma estable del nombre del juego."""

    __slots__ = ("top", "base", "mono", "text", "scrim")

    def __init__(self, name: str) -> None:
        digest = hashlib.md5(name.encode("utf-8")).hexdigest()
        hue = int(digest[:8], 16) % 360
        # Saturación con ligera variación por nombre para que no sean clones.
        sat = 150 + (int(digest[8:10], 16) % 50)          # 150–199
        base = QColor.fromHsl(hue, min(sat, 255), 138)
        self.base = base
        self.top = QColor.fromHsl(hue, max(sat - 28, 0), 182)   # esquina clara
        self.mono = QColor.fromHsl(hue, min(sat + 20, 255), 92)  # emblema profundo

        # Texto con contraste perceptual sobre el color base.
        r, g, b, _ = base.getRgb()
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        if luminance > 150:
            self.text = QColor.fromHsl(hue, 200, 46)   # tono oscuro de la familia
            self.scrim = QColor(255, 255, 255, 0)      # no hace falta velo
        else:
            self.text = QColor(255, 255, 255)
            self.scrim = QColor(0, 0, 0, 64)


class GameCardDelegate(QStyledItemDelegate):
    """Pinta cada juego como una tarjeta de color con nombre armonioso."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.accent = QColor("#007AFF")
        self._skins: dict[str, _GameSkin] = {}

    def _skin(self, name: str) -> _GameSkin:
        skin = self._skins.get(name)
        if skin is None:
            skin = _GameSkin(name)
            self._skins[name] = skin
        return skin

    def sizeHint(self, option, index) -> QSize:  # noqa: N802 (Qt API)
        return _CELL

    def paint(self, painter: QPainter, option, index) -> None:  # noqa: N802
        name = index.data(Qt.ItemDataRole.DisplayRole) or ""
        skin = self._skin(name)
        state = option.state
        hovered = bool(state & QStyle.StateFlag.State_MouseOver)
        selected = bool(state & QStyle.StateFlag.State_Selected)

        card = QRectF(option.rect).adjusted(
            _CARD_INSET, _CARD_INSET, -_CARD_INSET, -_CARD_INSET
        )

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # Elevación al hover: sombra suave (capas translúcidas crecientes que
        # imitan un desenfoque) bajo la tarjeta.
        if hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 9))
            for spread in range(6, 0, -1):
                sh = card.translated(0, 3).adjusted(-spread, -spread, spread, spread)
                painter.drawRoundedRect(
                    sh, _CARD_RADIUS + spread, _CARD_RADIUS + spread
                )

        path = QPainterPath()
        path.addRoundedRect(card, _CARD_RADIUS, _CARD_RADIUS)

        # Fondo: degradado diagonal del color del juego.
        grad = QLinearGradient(card.topLeft(), card.bottomRight())
        grad.setColorAt(0.0, skin.top)
        grad.setColorAt(1.0, skin.base)
        painter.fillPath(path, grad)

        painter.setClipPath(path)

        # Brillo superior sutil para dar volumen (sin lavar el monograma).
        sheen = QLinearGradient(card.topLeft(), card.bottomLeft())
        sheen.setColorAt(0.0, QColor(255, 255, 255, 30))
        sheen.setColorAt(0.45, QColor(255, 255, 255, 0))
        painter.fillRect(card, sheen)

        # Emblema: inicial gigante y fantasmal como mini-carátula. Se centra por
        # el contorno real del glifo (no por la caja de texto, que incluye
        # ascenso/descenso y márgenes laterales y descentra ópticamente).
        initial = next((c for c in name if c.isalnum()), "?").upper()
        mono_font = QFont(painter.font())
        mono_font.setBold(True)
        mono_font.setPixelSize(int(card.height() * 0.74))
        painter.setFont(mono_font)
        mono = QColor(skin.mono)
        mono.setAlpha(58)
        painter.setPen(mono)
        emblem_zone = QRectF(card.left(), card.top(),
                             card.width(), card.height() - _NAME_BAND)
        glyph = QFontMetricsF(mono_font).boundingRect(initial)  # caja ajustada
        origin = QPointF(
            emblem_zone.center().x() - glyph.center().x(),
            emblem_zone.center().y() - glyph.center().y(),
        )
        painter.drawText(origin, initial)

        # Velo inferior para legibilidad cuando el texto es blanco.
        if skin.scrim.alpha() > 0:
            band = QRectF(card.left(), card.bottom() - _NAME_BAND - 18,
                          card.width(), _NAME_BAND + 18)
            veil = QLinearGradient(band.topLeft(), band.bottomLeft())
            top_c = QColor(skin.scrim)
            top_c.setAlpha(0)
            veil.setColorAt(0.0, top_c)
            veil.setColorAt(1.0, skin.scrim)
            painter.fillRect(band, veil)

        # Realce al pasar el ratón (sutil aclarado de toda la tarjeta).
        if hovered and not selected:
            overlay = QColor(255, 255, 255, 28)
            painter.fillPath(path, overlay)

        # Nombre: banda inferior, centrado, con auto-ajuste de tamaño.
        name_rect = QRectF(
            card.left() + 12,
            card.bottom() - _NAME_BAND,
            card.width() - 24,
            _NAME_BAND - 10,
        )
        # Nombres con espacios envuelven por palabra (bonito); un único token
        # largo ("SuperMarioKart") se parte por carácter como último recurso.
        wrap = (
            Qt.TextFlag.TextWordWrap
            if " " in name.strip()
            else Qt.TextFlag.TextWrapAnywhere
        )
        flags = (
            Qt.AlignmentFlag.AlignHCenter
            | Qt.AlignmentFlag.AlignBottom
            | wrap
        )
        name_font = QFont(painter.font())
        name_font.setBold(True)
        size = 15
        while size > 10:
            name_font.setPixelSize(size)
            painter.setFont(name_font)
            br = painter.boundingRect(name_rect, flags, name)
            if br.height() <= name_rect.height() and br.width() <= name_rect.width():
                break
            size -= 1
        painter.setFont(name_font)
        painter.setPen(skin.text)
        painter.drawText(name_rect, flags, name)

        painter.setClipping(False)

        # Canto de la tarjeta: hairline oscura del propio color para definir el
        # borde, o anillo de acento si está seleccionada.
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if selected:
            painter.setPen(QPen(self.accent, 2.5))
        else:
            edge = QColor(skin.mono)
            edge.setAlpha(60)
            painter.setPen(QPen(edge, 1.0))
        painter.drawRoundedRect(card, _CARD_RADIUS, _CARD_RADIUS)

        painter.restore()


class LibraryView(QWidget):
    game_selected = Signal(str)          # ruta de la ROM a cargar
    rescan_requested = Signal()
    manage_folders_requested = Signal()
    open_file_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        # --- Cabecera ---
        header = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Buscar juego…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._apply_filter)
        header.addWidget(self._search, stretch=1)

        self._folders_btn = QPushButton("Carpetas…")
        self._folders_btn.setObjectName("BotonCarpetas")
        self._folders_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._folders_btn.clicked.connect(self.manage_folders_requested.emit)
        header.addWidget(self._folders_btn)

        self._rescan_btn = QToolButton()
        self._rescan_btn.setObjectName("BotonRefrescarBiblioteca")
        self._rescan_btn.setIcon(line_icon("refresh", 18, "#007AFF"))
        self._rescan_btn.setToolTip("Re-escanear carpetas")
        self._rescan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rescan_btn.clicked.connect(self.rescan_requested.emit)
        header.addWidget(self._rescan_btn)
        root.addLayout(header)

        # --- Cuerpo: lista o guía vacía ---
        self._stack = QStackedWidget()

        self._delegate = GameCardDelegate(self)
        self._list = QListWidget()
        self._list.setObjectName("Biblioteca")
        self._list.setViewMode(QListWidget.ViewMode.IconMode)
        self._list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._list.setMovement(QListWidget.Movement.Static)
        self._list.setWrapping(True)
        self._list.setUniformItemSizes(True)
        self._list.setMouseTracking(True)
        self._list.setSpacing(0)
        self._list.setGridSize(_CELL)
        self._list.setItemDelegate(self._delegate)
        self._list.itemActivated.connect(self._on_item_activated)
        self._stack.addWidget(self._list)            # índice 0

        self._empty_page = self._build_empty_page()
        self._stack.addWidget(self._empty_page)      # índice 1

        root.addWidget(self._stack, stretch=1)

    def _build_empty_page(self) -> QWidget:
        card = StateCard(
            "controller",
            "No hay juegos en la biblioteca",
            "Añade una carpeta con ROMs de SNES o abre un archivo suelto.",
        )
        card.add_action("Añadir carpeta", self.manage_folders_requested.emit, primary=True)
        card.add_action("Abrir archivo…", self.open_file_requested.emit)
        return card

    # -- API -----------------------------------------------------------------
    def set_games(self, games: list[GameEntry]) -> None:
        self._list.clear()
        for g in games:
            item = QListWidgetItem(g.display_name)
            item.setData(_PATH_ROLE, str(g.path))
            item.setToolTip(f"{g.display_name}\n{g.folder} · {g.path}")
            self._list.addItem(item)
        self._apply_filter(self._search.text())
        self._stack.setCurrentWidget(
            self._list if games else self._empty_page
        )

    def apply_palette(self, palette: Palette) -> None:
        """Re-tiñe los iconos dependientes del tema y el acento de selección."""
        self._rescan_btn.setIcon(line_icon("refresh", 18, palette.accent))
        self._empty_page.apply_icon_color(palette.text_secondary)
        self._delegate.accent = QColor(palette.accent)
        self._list.viewport().update()

    # -- internos ------------------------------------------------------------
    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self._list.count()):
            item = self._list.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def _on_item_activated(self, item: QListWidgetItem | None) -> None:
        if item is not None:
            self.game_selected.emit(item.data(_PATH_ROLE))
