"""Panel de control derecho (ancho fijo 320 px).

Tres regiones verticales: control segmentado superior, cuerpo desplazable
con dos vistas (Configuracion y Visualizacion del control) y un pie con el
boton de restablecer. Coordina el estado de escucha de las filas de mapeo y
alimenta el diagrama de mando en vivo.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..services.input_service import SNES_INPUTS, InputService, MappingProfiles
from ..state import ConnectionState
from ..theme import (
    GUTTER_SIDEBAR,
    PANEL_WIDTH,
    Palette,
    SECTION_GAP,
)
from .controller_diagram import ControllerDiagram
from .icons import glyph_icon
from .mapping_row import MappingRow
from .segmented_control import SegmentedControl


def _section_header(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setProperty("role", "label-caps")
    return lbl


class ControlPanel(QFrame):
    device_changed = Signal(str)
    refresh_requested = Signal()
    reset_requested = Signal()
    listening_changed = Signal(bool)       # hay una fila esperando entrada

    def __init__(
        self,
        input_service: InputService,
        profiles: MappingProfiles,
        device_key: str,
        palette: Palette,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PanelControl")
        self.setFixedWidth(PANEL_WIDTH)

        self._input = input_service
        self._profiles = profiles
        self._device_key = device_key
        self._rows: dict[str, MappingRow] = {}
        self._listening_key: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(GUTTER_SIDEBAR, GUTTER_SIDEBAR, GUTTER_SIDEBAR, GUTTER_SIDEBAR)
        root.setSpacing(GUTTER_SIDEBAR)

        # --- Control segmentado ---
        self._segmented = SegmentedControl(["Configuración", "Visualización del control"])
        self._segmented.changed.connect(self._on_tab_changed)
        root.addWidget(self._segmented)

        # --- Cuerpo desplazable ---
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_config_view(palette))
        self._stack.addWidget(self._build_visual_view(palette))
        self._scroll.setWidget(self._stack)
        root.addWidget(self._scroll, stretch=1)

        # --- Pie ---
        footer = QWidget()
        fl = QVBoxLayout(footer)
        fl.setContentsMargins(0, 0, 0, 0)
        self._reset_btn = QPushButton("Restablecer configuración")
        self._reset_btn.clicked.connect(self.reset_requested.emit)
        self._reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fl.addWidget(self._reset_btn)
        root.addWidget(footer)

        self._refresh_device_combo()
        self.update_connection(self._input.connection_state)

    # -- construccion de vistas ---------------------------------------------
    def _build_config_view(self, palette: Palette) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(SECTION_GAP)

        # Seccion Control actual
        current = QWidget()
        cl = QVBoxLayout(current)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(8)
        cl.addWidget(_section_header("Control actual"))

        selector_row = QHBoxLayout()
        self._combo = QComboBox()
        # El combo no debe imponer su ancho minimo (item mas largo) al panel:
        # se permite encoger para respetar el ancho fijo de 320 px.
        self._combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self._combo.setMinimumContentsLength(6)
        self._combo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self._combo.currentTextChanged.connect(self._on_device_changed)
        selector_row.addWidget(self._combo, stretch=1)
        self._refresh_btn = QToolButton()
        self._refresh_btn.setObjectName("BotonRefrescar")
        self._refresh_btn.setIcon(glyph_icon("⟳", 18))
        self._refresh_btn.setToolTip("Re-enumerar dispositivos")
        self._refresh_btn.clicked.connect(self.refresh_requested.emit)
        selector_row.addWidget(self._refresh_btn)
        cl.addLayout(selector_row)

        status_row = QHBoxLayout()
        self._status_dot = QLabel("●")
        self._status_label = QLabel("")
        self._status_label.setProperty("role", "body-sm")
        status_row.addWidget(self._status_dot)
        status_row.addWidget(self._status_label)
        status_row.addStretch()
        cl.addLayout(status_row)
        layout.addWidget(current)

        # Seccion Asignacion de botones
        assign = QWidget()
        al = QVBoxLayout(assign)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(8)
        al.addWidget(_section_header("Asignación de botones"))

        illo_frame = QFrame()
        illo_frame.setObjectName("ContenedorIlustracion")
        illo_layout = QVBoxLayout(illo_frame)
        illo_layout.setContentsMargins(8, 8, 8, 8)
        self._illustration = ControllerDiagram(palette)
        self._illustration.setFixedHeight(140)
        illo_layout.addWidget(self._illustration)
        al.addWidget(illo_frame)

        rows_wrap = QWidget()
        rl = QVBoxLayout(rows_wrap)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)
        for spec in SNES_INPUTS:
            row = MappingRow(spec.key, spec.icon, spec.name,
                             self._profiles.label_for(self._device_key, spec.key))
            row.listen_requested.connect(self._on_listen_requested)
            self._rows[spec.key] = row
            rl.addWidget(row)
        al.addWidget(rows_wrap)
        layout.addWidget(assign)
        layout.addStretch()
        return view

    def _build_visual_view(self, palette: Palette) -> QWidget:
        view = QWidget()
        layout = QVBoxLayout(view)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(GUTTER_SIDEBAR)
        self._active_label = QLabel(self._input.current_device)
        self._active_label.setProperty("role", "label-md")
        self._active_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._active_label)
        self._live_diagram = ControllerDiagram(palette)
        self._live_diagram.setMinimumHeight(220)
        layout.addWidget(self._live_diagram)
        hint = QLabel("Vista de solo lectura. Las entradas presionadas se resaltan en tiempo real.")
        hint.setProperty("role", "body-sm")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)
        layout.addStretch()
        return view

    # -- dispositivo / conexion ---------------------------------------------
    def _refresh_device_combo(self) -> None:
        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItems(self._input.devices)
        idx = self._combo.findText(self._input.current_device)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)
        self._combo.blockSignals(False)

    def _on_device_changed(self, name: str) -> None:
        if name:
            self._active_label.setText(name)
            self.device_changed.emit(name)

    def update_devices(self, devices: list[str]) -> None:
        self._refresh_device_combo()

    def set_gamepad_devices(self, names: list[str]) -> None:
        """Puebla el combo con el teclado mas los mandos detectados."""
        self._combo.blockSignals(True)
        current = self._combo.currentText()
        self._combo.clear()
        self._combo.addItems(["Keyboard", *names])
        idx = self._combo.findText(current)
        self._combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._combo.blockSignals(False)

    def update_connection(self, state: ConnectionState) -> None:
        colors = {
            ConnectionState.CONNECTED: "#34C759",
            ConnectionState.DISCONNECTED: "#8D9199",
            ConnectionState.RECONNECTING: "#FF9F0A",
        }
        self._status_dot.setStyleSheet(f"color: {colors[state]}; font-size: 14px;")
        self._status_label.setText(state.label)

    def set_current_device(self, name: str) -> None:
        idx = self._combo.findText(name)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)

    # -- pestañas ------------------------------------------------------------
    def _on_tab_changed(self, index: int) -> None:
        self._stack.setCurrentIndex(index)

    def set_active_tab(self, index: int) -> None:
        self._segmented.set_current(index)

    def active_tab(self) -> int:
        return self._segmented.current()

    # -- escucha de asignacion ----------------------------------------------
    def _on_listen_requested(self, key: str) -> None:
        # Si otra fila estaba escuchando, cancelarla.
        self.cancel_listening()
        self._listening_key = key
        self._rows[key].set_listening(True)
        self.listening_changed.emit(True)

    @property
    def is_listening(self) -> bool:
        return self._listening_key is not None

    def cancel_listening(self) -> None:
        if self._listening_key:
            self._rows[self._listening_key].set_listening(False)
            self._listening_key = None
            self.listening_changed.emit(False)

    def assign_captured(self, binding) -> None:
        """Asigna el binding detectado (tecla o entrada de mando) a la fila."""
        if not self._listening_key:
            return
        key = self._listening_key
        self._profiles.assign(self._device_key, key, binding)
        self._rows[key].set_assignment(self._profiles.label_for(self._device_key, key))
        self._listening_key = None
        self.listening_changed.emit(False)

    # -- dispositivo activo / mapeo / reset ----------------------------------
    def set_active_device_key(self, device_key: str, *, gamepad: bool) -> None:
        """Cambia el perfil que muestra/edita el panel y refresca las filas."""
        self._profiles.ensure(device_key, gamepad=gamepad)
        self._device_key = device_key
        self.refresh_assignments_from_model()

    def refresh_assignments_from_model(self) -> None:
        for key, row in self._rows.items():
            row.set_assignment(self._profiles.label_for(self._device_key, key))

    # -- diagrama en vivo ----------------------------------------------------
    def set_live_pressed(self, pressed: set[str]) -> None:
        self._live_diagram.set_pressed(pressed)
        self._illustration.set_pressed(pressed)

    def set_palette(self, palette: Palette) -> None:
        self._illustration.set_palette(palette)
        self._live_diagram.set_palette(palette)
