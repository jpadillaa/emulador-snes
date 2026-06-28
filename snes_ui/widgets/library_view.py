"""Vista de biblioteca: cuadrícula de juegos en el escenario vacío.

Cabecera con búsqueda y acciones (re-escanear, gestionar carpetas) sobre un
``QListWidget`` en modo icono (cuadrícula que ajusta columnas, navegación con
flechas, doble-clic/Enter para lanzar). Si no hay juegos, muestra una guía con
las acciones para añadir una carpeta o abrir un archivo suelto.
"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..services.library_service import GameEntry
from .icons import line_icon
from .state_card import StateCard

_PATH_ROLE = Qt.ItemDataRole.UserRole


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
        self._folders_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._folders_btn.clicked.connect(self.manage_folders_requested.emit)
        header.addWidget(self._folders_btn)

        self._rescan_btn = QToolButton()
        self._rescan_btn.setObjectName("BotonRefrescar")
        self._rescan_btn.setIcon(line_icon("refresh", 18))
        self._rescan_btn.setToolTip("Re-escanear carpetas")
        self._rescan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rescan_btn.clicked.connect(self.rescan_requested.emit)
        header.addWidget(self._rescan_btn)
        root.addLayout(header)

        # --- Cuerpo: lista o guía vacía ---
        self._stack = QStackedWidget()

        self._list = QListWidget()
        self._list.setObjectName("Biblioteca")
        self._list.setViewMode(QListWidget.ViewMode.IconMode)
        self._list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._list.setMovement(QListWidget.Movement.Static)
        self._list.setWrapping(True)
        self._list.setUniformItemSizes(True)
        self._list.setWordWrap(True)
        self._list.setSpacing(0)
        self._list.setGridSize(QSize(168, 84))
        self._list.setIconSize(QSize(0, 0))
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
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._list.addItem(item)
        self._apply_filter(self._search.text())
        self._stack.setCurrentWidget(
            self._list if games else self._empty_page
        )

    # -- internos ------------------------------------------------------------
    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self._list.count()):
            item = self._list.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def _on_item_activated(self, item: QListWidgetItem | None) -> None:
        if item is not None:
            self.game_selected.emit(item.data(_PATH_ROLE))
