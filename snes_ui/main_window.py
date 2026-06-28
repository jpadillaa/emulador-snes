"""Ventana principal: orquesta layout, menus, atajos y estados de sesion.

Centraliza el manejo de los cinco estados de la interfaz y el cableado entre
la barra de acciones, los menus, el panel de control y el controlador de
sesion. Toda la logica de emulacion queda detras del adaptador del nucleo.
"""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QColor, QFont, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from .core.adapter import create_core
from .core.session import SessionController
from .services.gamepad_service import GamepadService
from .services.input_service import (
    InputService,
    MappingProfiles,
    KEYBOARD_KEY,
    key_binding,
    SNES_INPUTS,
)
from .services.save_service import SaveService
from .settings import AppSettings
from .state import ConnectionState, ScaleMode, SessionState
from .theme import (
    MARGIN_WINDOW,
    STACK_GAP,
    ThemeName,
    WINDOW_INITIAL,
    WINDOW_MINIMUM,
    build_stylesheet,
    palette_for,
    system_font_family,
)
from .widgets.action_bar import ActionBar
from .widgets.control_panel import ControlPanel
from .widgets.game_stage import GameStage
from .widgets.overlay_action_bar import OverlayActionBar
from .widgets.toast import Toast


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SNES Emulator")
        self.setMinimumSize(*WINDOW_MINIMUM)

        # -- servicios y estado --------------------------------------------
        self._settings = AppSettings()
        # Nucleo real (libretro) si la biblioteca esta disponible; si no, mock.
        self._core = create_core()
        self._session = SessionController(self._core, self)
        self._input = InputService(self)
        self._gamepad = GamepadService(parent=self)
        self._pad_by_name: dict[str, object] = {}   # nombre -> PadInfo
        self._saves = SaveService()
        # Perfiles de asignacion por dispositivo (migra el formato anterior).
        self._profiles = MappingProfiles.from_json(self._settings.profiles_json())
        self._profiles.ensure(KEYBOARD_KEY, gamepad=False)
        self._active_device_key = KEYBOARD_KEY
        # Conjuntos de entradas presionadas por origen (OR-combine en el juego).
        self._kbd_pressed: set[str] = set()
        self._pad_pressed: set[str] = set()

        self._theme_pref = self._settings.theme_preference()
        self._theme = self._resolve_theme()
        self._scale_mode = ScaleMode(self._settings.scale_mode())

        self._build_ui()
        self._build_menus()
        self._connect_signals()
        self._apply_theme()

        # Restaurar dispositivo y pestaña persistidos.
        self._input.set_current_device(self._settings.device())
        self._panel.set_current_device(self._settings.device())
        self._panel.set_active_tab(self._settings.active_tab())

        self._restore_geometry()
        self._on_state_changed(SessionState.EMPTY)

        QApplication.instance().installEventFilter(self)
        self._gamepad.start()

    # -- construccion de UI -------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("WidgetCentral")
        self.setCentralWidget(central)

        body = QHBoxLayout(central)
        body.setContentsMargins(MARGIN_WINDOW, MARGIN_WINDOW, MARGIN_WINDOW, MARGIN_WINDOW)
        body.setSpacing(MARGIN_WINDOW)

        # Area principal
        self._main_area = QWidget()
        main_layout = QVBoxLayout(self._main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(STACK_GAP)

        self._stage = GameStage()
        # En pantalla completa o maximizado se fuerza 4:3 (ver _aspect_locked).
        self._aspect_locked = False
        self._stage.set_scale_mode(self._scale_mode)
        main_layout.addWidget(self._stage, stretch=1)

        self._action_bar = ActionBar()
        main_layout.addWidget(self._action_bar)

        body.addWidget(self._main_area, stretch=1)

        # Panel de control
        self._panel = ControlPanel(self._input, self._profiles, KEYBOARD_KEY, palette_for(self._theme))
        body.addWidget(self._panel)

        # Sombra de elevación suave en las superficies de material (no en el
        # escenario: lleva vídeo a 60 fps y un efecto gráfico lo re-renderizaría).
        self._add_elevation(self._panel)
        self._add_elevation(self._action_bar)

        # Overlay de pantalla completa y toast (hijos del area principal).
        self._overlay = OverlayActionBar(self._main_area)
        self._toast = Toast(self._main_area)

    def _add_elevation(self, widget: QWidget) -> None:
        """Aplica una sombra sutil tipo macOS para despegar la superficie del fondo.

        El radio de desenfoque se mantiene por debajo del margen disponible
        alrededor de la superficie (MARGIN_WINDOW / STACK_GAP ≈ 16-20 px); si el
        blur excede ese margen, QGraphicsDropShadowEffect recorta la sombra
        contra el borde de la ventana y deja cantos duros y esquinas extrañas."""
        shadow = QGraphicsDropShadowEffect(widget)
        shadow.setBlurRadius(16)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 55))
        widget.setGraphicsEffect(shadow)

    def _build_menus(self) -> None:
        bar = self.menuBar()

        # --- Archivo ---
        m_file = bar.addMenu("Archivo")
        self._act_load = QAction("Cargar juego…", self)
        self._act_load.setShortcut(QKeySequence("Ctrl+O"))
        self._act_load.triggered.connect(self._flow_load_game)
        m_file.addAction(self._act_load)

        self._act_save = QAction("Guardar partida", self)
        self._act_save.setShortcut(QKeySequence("Ctrl+S"))
        self._act_save.triggered.connect(self._flow_save_state)
        m_file.addAction(self._act_save)

        self._act_loadstate = QAction("Cargar partida…", self)
        self._act_loadstate.setShortcut(QKeySequence("Ctrl+L"))
        self._act_loadstate.triggered.connect(self._flow_load_state)
        m_file.addAction(self._act_loadstate)

        m_file.addSeparator()
        self._act_quit_session = QAction("Salir del juego", self)
        self._act_quit_session.setShortcut(QKeySequence("Ctrl+W"))
        self._act_quit_session.triggered.connect(self._flow_quit_game)
        m_file.addAction(self._act_quit_session)

        m_file.addSeparator()
        act_exit = QAction("Salir de la aplicación", self)
        act_exit.setShortcut(QKeySequence.StandardKey.Quit)
        act_exit.triggered.connect(self.close)
        m_file.addAction(act_exit)

        # --- Ver ---
        m_view = bar.addMenu("Ver")
        self._act_pause = QAction("Pausar / Reanudar", self)
        self._act_pause.setShortcut(QKeySequence(Qt.Key.Key_Space))
        self._act_pause.triggered.connect(self._session.toggle_pause)
        m_view.addAction(self._act_pause)

        self._act_fullscreen = QAction("Pantalla completa", self)
        self._act_fullscreen.setCheckable(True)
        if sys.platform == "darwin":
            self._act_fullscreen.setShortcut(QKeySequence("Ctrl+Meta+F"))
        else:
            self._act_fullscreen.setShortcut(QKeySequence(Qt.Key.Key_F11))
        self._act_fullscreen.triggered.connect(self._toggle_fullscreen)
        m_view.addAction(self._act_fullscreen)

        m_view.addSeparator()

        # Submenu modos de escalado
        m_scale = m_view.addMenu("Modo de visualización")
        self._scale_group = QActionGroup(self)
        self._scale_group.setExclusive(True)
        for mode in ScaleMode:
            act = QAction(mode.label, self, checkable=True)
            act.setData(mode)
            act.setChecked(mode == self._scale_mode)
            act.triggered.connect(lambda _=False, m=mode: self._set_scale_mode(m))
            self._scale_group.addAction(act)
            m_scale.addAction(act)

        # Submenu tema
        m_theme = m_view.addMenu("Tema")
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)
        for label, value in (("Sistema", "system"), ("Claro", "light"), ("Oscuro", "dark")):
            act = QAction(label, self, checkable=True)
            act.setData(value)
            act.setChecked(value == self._theme_pref)
            act.triggered.connect(lambda _=False, v=value: self._set_theme_pref(v))
            self._theme_group.addAction(act)
            m_theme.addAction(act)

    def _connect_signals(self) -> None:
        self._session.state_changed.connect(self._on_state_changed)
        self._session.frame_ready.connect(self._on_frame_ready)
        self._session.error_raised.connect(self._stage.set_error_message)
        self._session.rom_changed.connect(self._stage.set_loading_filename)

        self._action_bar.triggered.connect(self._on_action)
        self._overlay.triggered.connect(self._on_action)

        self._stage.request_load.connect(self._flow_load_game)
        self._stage.retry_requested.connect(self._flow_load_game)
        self._stage.close_error_requested.connect(self._session.reset_to_empty)
        self._stage.resume_requested.connect(self._session.resume)

        self._panel.device_changed.connect(self._on_device_changed)
        self._panel.reset_requested.connect(self._flow_reset_mappings)
        self._panel.listening_changed.connect(self._on_listening_changed)

        # El indicador de conexion del teclado (siempre conectado); el gamepad
        # lo sobrescribe cuando hay mando activo.
        self._input.connection_changed.connect(self._panel.update_connection)

        # Gamepad: el combo de dispositivos y la conexion los gobierna el
        # servicio; el boton de refrescar re-enumera mandos.
        self._gamepad.pressed_changed.connect(self._on_pad_pressed)
        self._gamepad.binding_captured.connect(self._on_pad_binding_captured)
        self._gamepad.devices_changed.connect(self._on_pad_devices_changed)
        self._gamepad.connection_changed.connect(self._panel.update_connection)
        self._panel.refresh_requested.connect(self._gamepad.poll_once)

        sh = QApplication.instance().styleHints()
        if hasattr(sh, "colorSchemeChanged"):
            sh.colorSchemeChanged.connect(self._on_system_scheme_changed)

    # -- tema ----------------------------------------------------------------
    def _resolve_theme(self) -> ThemeName:
        if self._theme_pref == "light":
            return ThemeName.LIGHT
        if self._theme_pref == "dark":
            return ThemeName.DARK
        # system
        sh = QApplication.instance().styleHints()
        scheme = getattr(sh, "colorScheme", lambda: None)()
        if scheme == Qt.ColorScheme.Dark:
            return ThemeName.DARK
        return ThemeName.LIGHT

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        # Fija explicitamente la fuente base de la app a una del sistema para
        # evitar el alias inexistente "Sans Serif" que usan algunos backends.
        app.setFont(QFont(system_font_family()))
        app.setStyleSheet(build_stylesheet(self._theme))
        pal = palette_for(self._theme)
        self._panel.set_palette(pal)
        # Re-teñir los iconos de línea monocromáticos al color del tema (los
        # pixmaps no se adaptan solos al cambiar claro/oscuro).
        self._action_bar.set_icon_color(pal.text_primary)
        self._overlay.set_icon_color(pal.text_primary)
        self._stage.apply_icon_color(pal)
        self._toast.set_palette(pal)

    def _set_theme_pref(self, value: str) -> None:
        self._theme_pref = value
        self._settings.set_theme_preference(value)
        self._theme = self._resolve_theme()
        self._apply_theme()

    def _on_system_scheme_changed(self, _scheme) -> None:
        if self._theme_pref == "system":
            self._theme = self._resolve_theme()
            self._apply_theme()

    # -- modo de escalado ----------------------------------------------------
    def _set_scale_mode(self, mode: ScaleMode) -> None:
        # Guarda la preferencia del usuario; el modo efectivo en pantalla puede
        # estar forzado a 4:3 mientras la ventana esta en pantalla completa o
        # maximizada (ver _apply_effective_scale_mode).
        self._scale_mode = mode
        self._settings.set_scale_mode(mode.value)
        self._apply_effective_scale_mode()

    # -- bloqueo de relacion de aspecto 4:3 ----------------------------------
    def _apply_effective_scale_mode(self) -> None:
        """Aplica 4:3 (Ajuste a ventana) si esta bloqueado; si no, el modo del usuario."""
        effective = ScaleMode.FIT_WINDOW if self._aspect_locked else self._scale_mode
        self._stage.set_scale_mode(effective)

    def _update_aspect_lock(self) -> None:
        """Fuerza 4:3 en pantalla completa o maximizado; restaura al salir."""
        locked = self.isFullScreen() or self.isMaximized()
        if locked == self._aspect_locked:
            return
        self._aspect_locked = locked
        self._apply_effective_scale_mode()

    def changeEvent(self, event) -> None:  # noqa: N802
        if event.type() == QEvent.Type.WindowStateChange:
            self._update_aspect_lock()
        super().changeEvent(event)

    # -- maquina de estados --------------------------------------------------
    def _on_state_changed(self, state: SessionState) -> None:
        self._stage.show_state(state)
        active = state in (SessionState.RUNNING, SessionState.PAUSED)
        self._action_bar.set_session_active(active)
        self._overlay.set_session_active(active)
        self._act_save.setEnabled(active)
        self._act_loadstate.setEnabled(True)  # se puede cargar con o sin sesion
        self._act_quit_session.setEnabled(active)
        self._act_pause.setEnabled(active)

    def _on_frame_ready(self) -> None:
        self._stage.update_frame(self._core.get_frame())

    # -- enrutamiento de entrada (OR-combine teclado + mando) ----------------
    def _recompute_inputs(self) -> None:
        """Combina (unión) teclado y mando y alimenta el núcleo + diagrama."""
        union = self._kbd_pressed | self._pad_pressed
        self._panel.set_live_pressed(union)
        for spec in SNES_INPUTS:
            self._core.set_input(spec.retro_id, spec.key in union)

    # -- acciones (barra y overlay) -----------------------------------------
    def _on_action(self, key: str) -> None:
        {
            "load_game": self._flow_load_game,
            "save_state": self._flow_save_state,
            "load_state": self._flow_load_state,
            "quit_game": self._flow_quit_game,
            "fullscreen": self._toggle_fullscreen,
        }[key]()

    # -- flujos --------------------------------------------------------------
    def _flow_load_game(self) -> None:
        start_dir = "ROMS" if os.path.isdir("ROMS") else os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, "Cargar juego", start_dir, "ROMs SNES (*.sfc *.smc)"
        )
        if not path:
            return  # cancelado: sin cambios
        self._session.begin_loading(path)
        # Cede el control al event loop una vez (sin retraso artificial) para
        # que la vista CARGANDO se pinte antes de la carga sincrona del nucleo.
        QTimer.singleShot(0, self._session.finish_loading)

    def _flow_save_state(self) -> None:
        if not self._session.has_session:
            return
        blob = self._session.save_state()
        if not blob:
            self._show_error_dialog("El núcleo no pudo serializar el estado actual.")
            return
        # Miniatura del fotograma vigente para previsualizar la partida.
        self._saves.create(self._session.rom_name, blob, self._core.get_frame())
        self._toast.show_message("✓ Partida guardada", "ok")

    def _flow_load_state(self) -> None:
        rom = self._session.rom_name or (self._core.title + ".sfc" if self._core.title else "")
        states = self._saves.list_for(rom) if rom else []
        dlg = _SaveStateDialog(states, self._saves, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        chosen = dlg.selected()
        if chosen is None:
            return
        try:
            blob = chosen.read_blob()
        except OSError:
            self._show_error_dialog("No se pudo leer el archivo de la partida.")
            return
        if self._session.load_state(blob):
            self._toast.show_message("✓ Partida restaurada", "ok")
        else:
            self._show_error_dialog("No se pudo restaurar el estado seleccionado.")

    def _flow_quit_game(self) -> None:
        if not self._session.has_session:
            return
        if self._session.is_dirty:
            box = QMessageBox(self)
            box.setWindowTitle("Salir del juego")
            box.setText("Hay progreso sin guardar.")
            box.setInformativeText("¿Deseas guardar antes de salir?")
            save = box.addButton("Guardar y salir", QMessageBox.ButtonRole.AcceptRole)
            discard = box.addButton("Salir sin guardar", QMessageBox.ButtonRole.DestructiveRole)
            box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            clicked = box.clickedButton()
            if clicked == save:
                self._flow_save_state()
            elif clicked != discard:
                return  # cancelar
        if self.isFullScreen():
            self._toggle_fullscreen()
        self._stage.clear_video()
        self._session.quit_session()

    def _flow_reset_mappings(self) -> None:
        res = QMessageBox.question(
            self,
            "Restablecer configuración",
            "¿Restablecer todas las asignaciones a sus valores iniciales?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if res == QMessageBox.StandardButton.Yes:
            self._profiles.reset(
                self._active_device_key, gamepad=(self._active_device_key != KEYBOARD_KEY)
            )
            self._panel.refresh_assignments_from_model()
            self._toast.show_message("Configuración restablecida", "info")

    # -- dispositivos / gamepad ---------------------------------------------
    def _on_device_changed(self, name: str) -> None:
        # El teclado siempre alimenta el juego; este selector elige el mando
        # activo y que perfil edita el panel.
        if name == "Keyboard" or name not in self._pad_by_name:
            self._active_device_key = KEYBOARD_KEY
            self._panel.set_active_device_key(KEYBOARD_KEY, gamepad=False)
            self._gamepad.set_active(None, {})
            self._pad_pressed = set()
            self._recompute_inputs()
            return
        info = self._pad_by_name[name]
        self._active_device_key = info.guid
        self._profiles.ensure(info.guid, gamepad=True)
        self._panel.set_active_device_key(info.guid, gamepad=True)
        self._gamepad.set_active(info.instance_id, self._profiles.profile(info.guid))

    def _on_pad_pressed(self, pressed: set) -> None:
        self._pad_pressed = set(pressed)
        self._recompute_inputs()

    def _on_pad_devices_changed(self, devices: list) -> None:
        self._pad_by_name = {d.name: d for d in devices}
        self._panel.set_gamepad_devices([d.name for d in devices])
        # Auto-seleccionar el primer mando si seguimos en teclado.
        if self._active_device_key == KEYBOARD_KEY and devices:
            self._panel.set_current_device(devices[0].name)

    def _on_pad_binding_captured(self, binding) -> None:
        if self._panel.is_listening:
            self._panel.assign_captured(binding)
        self._gamepad.set_capture(False)

    def _on_listening_changed(self, listening: bool) -> None:
        # Captura por mando solo si el dispositivo activo es un mando.
        self._gamepad.set_capture(listening and self._active_device_key != KEYBOARD_KEY)

    # -- pantalla completa ---------------------------------------------------
    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            self._panel.setVisible(True)
            self._action_bar.setVisible(True)
            self._overlay.setVisible(False)
            self._act_fullscreen.setChecked(False)
            self._main_area.setMouseTracking(False)
        else:
            self._panel.setVisible(False)
            self._action_bar.setVisible(False)
            self.showFullScreen()
            self._act_fullscreen.setChecked(True)
            self._overlay.set_session_active(self._session.has_session)
            self._overlay.reveal()
            self._main_area.setMouseTracking(True)

    # -- captura de entrada (event filter) ----------------------------------
    def eventFilter(self, obj, event):  # noqa: N802
        et = event.type()
        if et == QEvent.Type.KeyPress:
            if self._handle_key_press(event):
                return True
        elif et == QEvent.Type.KeyRelease:
            self._handle_key_release(event)
        elif et == QEvent.Type.MouseMove and self.isFullScreen():
            pos = self._main_area.mapFromGlobal(event.globalPosition().toPoint())
            self._overlay.handle_mouse_y(pos.y())
        return super().eventFilter(obj, event)

    def _handle_key_press(self, event) -> bool:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            if self._panel.is_listening:
                self._panel.cancel_listening()
                return True
            if self.isFullScreen():
                self._toggle_fullscreen()
                return True
            return False
        # Captura de asignacion: si el dispositivo activo es el teclado, la
        # tecla pulsada se guarda como Binding; si es un mando, las teclas se
        # ignoran (la captura la resuelve el GamepadService).
        if self._panel.is_listening:
            if self._active_device_key == KEYBOARD_KEY:
                self._panel.assign_captured(key_binding(key))
            return True
        # Entrada de juego: resuelve la tecla contra el perfil del teclado y
        # recompone la union teclado+mando.
        if not event.isAutoRepeat():
            input_key = self._profiles.input_for_key(KEYBOARD_KEY, key)
            if input_key:
                self._kbd_pressed.add(input_key)
                self._recompute_inputs()
        return False

    def _handle_key_release(self, event) -> None:
        if event.isAutoRepeat():
            return
        input_key = self._profiles.input_for_key(KEYBOARD_KEY, event.key())
        if input_key:
            self._kbd_pressed.discard(input_key)
            self._recompute_inputs()

    # -- persistencia / geometria -------------------------------------------
    def _restore_geometry(self) -> None:
        geo = self._settings.geometry()
        if geo:
            self.restoreGeometry(geo)
        else:
            self.resize(*WINDOW_INITIAL)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._settings.save_geometry(self.saveGeometry(), self.saveState())
        self._settings.set_profiles_json(self._profiles.to_json())
        self._settings.set_device(self._input.current_device)
        self._settings.set_theme_preference(self._theme_pref)
        self._settings.set_scale_mode(self._scale_mode.value)
        self._settings.set_active_tab(self._panel.active_tab())
        self._gamepad.stop()
        # Liberar el nucleo nativo de forma ordenada.
        shutdown = getattr(self._core, "shutdown", None)
        if callable(shutdown):
            shutdown()
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self.isFullScreen():
            self._overlay._reposition()


class _SaveStateDialog(QDialog):
    """Selector de estados guardados con miniatura, fecha y borrado.

    Muestra un estado vacio si la ROM no tiene partidas. Cada elemento lleva
    el SaveState asociado en su UserRole, de modo que la seleccion y el
    borrado funcionan aunque la lista cambie.
    """

    def __init__(self, states, service, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cargar partida")
        self.setMinimumWidth(420)
        self._service = service

        layout = QVBoxLayout(self)
        if not states:
            empty = QLabel("No hay partidas guardadas para esta ROM.")
            empty.setProperty("role", "body-lg")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setWordWrap(True)
            layout.addWidget(empty)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            buttons.rejected.connect(self.reject)
            layout.addWidget(buttons)
            self._list = None
            return

        self._list = QListWidget()
        self._list.setIconSize(QSize(96, 72))
        for st in states:
            item = QListWidgetItem(f"{st.rom_name}\n{st.label}")
            if st.thumb_path is not None:
                item.setIcon(QIcon(QPixmap(str(st.thumb_path))))
            item.setData(Qt.ItemDataRole.UserRole, st)
            self._list.addItem(item)
        self._list.setCurrentRow(0)
        self._list.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self._list)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel
        )
        self._delete_btn = buttons.addButton(
            "Eliminar", QDialogButtonBox.ButtonRole.ActionRole
        )
        self._delete_btn.clicked.connect(self._on_delete)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_delete(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        st = item.data(Qt.ItemDataRole.UserRole)
        res = QMessageBox.question(
            self,
            "Eliminar partida",
            f"¿Eliminar la partida guardada del {st.label}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if res != QMessageBox.StandardButton.Yes:
            return
        self._service.delete(st)
        self._list.takeItem(self._list.row(item))
        if self._list.count() == 0:
            self.reject()  # ya no queda nada que cargar

    def selected(self):
        if not self._list:
            return None
        item = self._list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None
