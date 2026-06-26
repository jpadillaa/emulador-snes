"""Adaptador del nucleo de emulacion.

Aisla por completo la interfaz grafica de cualquier implementacion concreta
del nucleo. La aplicacion solo conoce la clase abstracta ``EmulatorCore``.

Hay dos implementaciones:
- ``LibretroCore`` enlaza el nucleo real (snes9x_libretro) por el ABI de
  libretro mediante ctypes. Porta la logica de ``poc.py`` (carga de ROM,
  ejecucion, video, entrada y estados) a la arquitectura de la aplicacion,
  reemplazando pygame por QImage para el video.
- ``MockEmulatorCore`` genera fotogramas sinteticos y sirve de respaldo
  cuando la biblioteca del nucleo no esta disponible.

La factoria ``create_core`` elige el nucleo real y cae al simulado si falla.
"""
from __future__ import annotations

import ctypes
import math
import os
import struct
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QFont


# Resolucion nativa de referencia del SNES (relacion 4:3 a efectos de UI).
NATIVE_WIDTH = 256
NATIVE_HEIGHT = 224


@dataclass(frozen=True)
class AVInfo:
    """Informacion audiovisual que el nucleo expone tras cargar un juego."""
    width: int
    height: int
    fps: float
    sample_rate: float = 32040.0   # frecuencia de muestreo de audio (Hz)


class EmulatorCore(ABC):
    """Contrato minimo que cualquier nucleo de emulacion debe cumplir.

    El ciclo de vida esperado es:
        load_game(path) -> run_frame()* -> unload()
    Los estados de guardado se serializan como ``bytes`` opacos.
    """

    @abstractmethod
    def load_game(self, path: str) -> bool:
        """Carga la ROM indicada. Devuelve True si la validacion es correcta."""

    @abstractmethod
    def run_frame(self) -> None:
        """Avanza la emulacion un fotograma."""

    @abstractmethod
    def get_frame(self) -> QImage:
        """Devuelve el ultimo fotograma renderizado como QImage."""

    @abstractmethod
    def av_info(self) -> AVInfo:
        """Informacion audiovisual del juego cargado."""

    @abstractmethod
    def set_input(self, button_id: int, pressed: bool) -> None:
        """Reporta el estado de un boton virtual del SNES al nucleo."""

    @abstractmethod
    def save_state(self) -> bytes:
        """Serializa el estado actual de la sesion."""

    @abstractmethod
    def load_state(self, blob: bytes) -> bool:
        """Restaura un estado previamente serializado."""

    @abstractmethod
    def unload(self) -> None:
        """Descarga el juego y libera recursos."""

    # -- control de audio (no-op por defecto; lo implementa el nucleo real) --
    def start_audio(self) -> None:
        """Inicia la reproduccion de audio de la sesion."""

    def pause_audio(self) -> None:
        """Suspende la reproduccion (estado pausado)."""

    def resume_audio(self) -> None:
        """Reanuda la reproduccion tras una pausa."""

    def stop_audio(self) -> None:
        """Detiene la reproduccion y libera el dispositivo de audio."""


class MockEmulatorCore(EmulatorCore):
    """Nucleo simulado: produce un patron animado en lugar de emular.

    Sirve para validar toda la cadena UI -> sesion -> superficie de video
    sin depender del nucleo real. Rechaza rutas que no terminen en .sfc/.smc
    para ejercitar el flujo de error.
    """

    VALID_EXT = (".sfc", ".smc")

    def __init__(self) -> None:
        self._loaded = False
        self._tick = 0
        self._title = ""
        self._image = QImage(NATIVE_WIDTH, NATIVE_HEIGHT, QImage.Format.Format_RGB32)
        self._image.fill(QColor("#0D0E12"))

    @property
    def title(self) -> str:
        return self._title

    def load_game(self, path: str) -> bool:
        import os
        if not path.lower().endswith(self.VALID_EXT):
            return False
        if not os.path.exists(path):
            return False
        if os.path.getsize(path) == 0:
            return False
        self._loaded = True
        self._tick = 0
        self._title = os.path.splitext(os.path.basename(path))[0]
        return True

    def run_frame(self) -> None:
        if not self._loaded:
            return
        self._tick += 1
        self._render()

    def get_frame(self) -> QImage:
        return self._image

    def av_info(self) -> AVInfo:
        return AVInfo(NATIVE_WIDTH, NATIVE_HEIGHT, 60.0)

    def set_input(self, button_id: int, pressed: bool) -> None:
        # El nucleo real reaccionaria a las entradas. El mock las ignora.
        pass

    def save_state(self) -> bytes:
        return f"MOCKSTATE::{self._title}::tick={self._tick}".encode()

    def load_state(self, blob: bytes) -> bool:
        return blob.startswith(b"MOCKSTATE::")

    def unload(self) -> None:
        self._loaded = False
        self._title = ""
        self._image.fill(QColor("#0D0E12"))

    # -- render interno ------------------------------------------------------
    def _render(self) -> None:
        img = self._image
        painter = QPainter(img)
        t = self._tick * 0.04
        grad = QLinearGradient(0, 0, NATIVE_WIDTH, NATIVE_HEIGHT)
        c1 = QColor.fromHsvF((0.6 + 0.1 * math.sin(t)) % 1.0, 0.55, 0.45)
        c2 = QColor.fromHsvF((0.85 + 0.1 * math.cos(t)) % 1.0, 0.6, 0.30)
        grad.setColorAt(0.0, c1)
        grad.setColorAt(1.0, c2)
        painter.fillRect(img.rect(), grad)

        # Sprite simple que rebota para evidenciar el avance de fotogramas.
        bx = int((NATIVE_WIDTH - 40) * (0.5 + 0.5 * math.sin(t)))
        by = int((NATIVE_HEIGHT - 40) * (0.5 + 0.5 * math.cos(t * 1.3)))
        painter.setBrush(QColor("#FFD60A"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(bx, by, 40, 40, 8, 8)

        font = QFont()
        font.setPixelSize(14)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255, 200))
        painter.drawText(8, 20, "MOCK CORE")
        painter.end()


# ---------------------------------------------------------------------------
# Nucleo real: enlace libretro por ctypes (portado de poc.py)
# ---------------------------------------------------------------------------

# Firmas de los callbacks de libretro segun el C ABI (identicas a poc.py).
_RetroEnvironment_t = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_uint, ctypes.c_void_p)
_RetroVideoRefresh_t = ctypes.CFUNCTYPE(
    None, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_size_t
)
_RetroAudioSample_t = ctypes.CFUNCTYPE(None, ctypes.c_int16, ctypes.c_int16)
_RetroAudioSampleBatch_t = ctypes.CFUNCTYPE(
    ctypes.c_size_t, ctypes.POINTER(ctypes.c_int16), ctypes.c_size_t
)
_RetroInputPoll_t = ctypes.CFUNCTYPE(None)
_RetroInputState_t = ctypes.CFUNCTYPE(
    ctypes.c_int16, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint
)

# Comandos / constantes de libretro usados.
_ENV_SET_PIXEL_FORMAT = 10
_DEVICE_JOYPAD = 1
# Formatos de pixel -> formato QImage equivalente.
_PIXEL_0RGB1555 = 0
_PIXEL_XRGB8888 = 1
_PIXEL_RGB565 = 2


class _RetroGameInfo(ctypes.Structure):
    _fields_ = [
        ("path", ctypes.c_char_p),
        ("data", ctypes.c_void_p),
        ("size", ctypes.c_size_t),
        ("meta", ctypes.c_char_p),
    ]


class _RetroGameGeometry(ctypes.Structure):
    _fields_ = [
        ("base_width", ctypes.c_uint),
        ("base_height", ctypes.c_uint),
        ("max_width", ctypes.c_uint),
        ("max_height", ctypes.c_uint),
        ("aspect_ratio", ctypes.c_float),
    ]


class _RetroSystemTiming(ctypes.Structure):
    _fields_ = [("fps", ctypes.c_double), ("sample_rate", ctypes.c_double)]


class _RetroSystemAVInfo(ctypes.Structure):
    _fields_ = [("geometry", _RetroGameGeometry), ("timing", _RetroSystemTiming)]


class LibretroCore(EmulatorCore):
    """Nucleo de emulacion real enlazado al ABI de libretro via ctypes.

    Replica la mecanica de ``poc.py`` dentro del contrato ``EmulatorCore``:
    registra los callbacks obligatorios, negocia el formato de pixel, recibe
    los fotogramas como QImage y resuelve la entrada por consulta (pull).
    """

    def __init__(self, lib_path: str) -> None:
        # Puede lanzar OSError (lib ausente) o AttributeError (simbolo ausente);
        # la factoria los captura para caer al nucleo simulado.
        self._lib = ctypes.CDLL(lib_path)
        self._configure_signatures()

        self._pixel_format = _PIXEL_RGB565   # snes9x lo fija; valor por defecto seguro
        self._frame: QImage | None = None
        self._rom_buffer = None              # mantiene viva la ROM en memoria
        self._game_loaded = False
        self._title = ""
        self._av = AVInfo(NATIVE_WIDTH, NATIVE_HEIGHT, 60.0)
        # Estado de los botones del SNES por id libretro (modelo pull).
        self._input_state: dict[int, int] = {}
        self._inited = False

        # Audio: reproductor perezoso (se crea al conocer el sample_rate).
        self._audio = None
        self._audio_playing = False
        self._audio_failed = False

        # IMPORTANTE: conservar referencias vivas a los callbacks. Si Python
        # los recolecta, el nucleo llamaria a memoria liberada.
        self._cb_env = _RetroEnvironment_t(self._on_environment)
        self._cb_video = _RetroVideoRefresh_t(self._on_video_refresh)
        self._cb_audio = _RetroAudioSample_t(self._on_audio_sample)
        self._cb_audio_batch = _RetroAudioSampleBatch_t(self._on_audio_batch)
        self._cb_input_poll = _RetroInputPoll_t(self._on_input_poll)
        self._cb_input_state = _RetroInputState_t(self._on_input_state)

        self._lib.retro_set_environment(self._cb_env)
        self._lib.retro_set_video_refresh(self._cb_video)
        self._lib.retro_set_audio_sample(self._cb_audio)
        self._lib.retro_set_audio_sample_batch(self._cb_audio_batch)
        self._lib.retro_set_input_poll(self._cb_input_poll)
        self._lib.retro_set_input_state(self._cb_input_state)

        self._lib.retro_init()
        self._inited = True

    def _configure_signatures(self) -> None:
        self._lib.retro_load_game.argtypes = [ctypes.c_void_p]
        self._lib.retro_load_game.restype = ctypes.c_bool
        self._lib.retro_get_system_av_info.argtypes = [ctypes.c_void_p]
        self._lib.retro_serialize_size.restype = ctypes.c_size_t
        self._lib.retro_serialize.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        self._lib.retro_serialize.restype = ctypes.c_bool
        self._lib.retro_unserialize.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        self._lib.retro_unserialize.restype = ctypes.c_bool

    @property
    def title(self) -> str:
        return self._title

    # -- callbacks libretro --------------------------------------------------
    def _on_environment(self, cmd, data) -> bool:
        if cmd == _ENV_SET_PIXEL_FORMAT:
            self._pixel_format = ctypes.cast(
                data, ctypes.POINTER(ctypes.c_uint)
            ).contents.value
            return True
        return False

    def _qimage_format(self) -> QImage.Format:
        if self._pixel_format == _PIXEL_XRGB8888:
            return QImage.Format.Format_RGB32
        if self._pixel_format == _PIXEL_RGB565:
            return QImage.Format.Format_RGB16
        return QImage.Format.Format_RGB555

    def _on_video_refresh(self, data, width, height, pitch) -> None:
        # data NULL indica fotograma duplicado: se conserva el anterior.
        if not data:
            return
        try:
            raw = ctypes.string_at(data, int(height) * int(pitch))
            img = QImage(raw, int(width), int(height), int(pitch), self._qimage_format())
            # .copy() desliga el QImage del buffer temporal antes de devolverlo.
            self._frame = img.copy()
        except Exception:
            pass

    def _on_audio_sample(self, left, right) -> None:
        # Camino de muestra unica (snes9x usa el batch; se cubre por completitud).
        if self._audio is not None and self._audio_playing:
            self._audio.enqueue(struct.pack("<hh", int(left), int(right)))

    def _on_audio_batch(self, data, frames) -> int:
        # ``data`` apunta a int16 estereo intercalado; ``frames`` cuadros estereo.
        if self._audio is not None and self._audio_playing and data:
            try:
                raw = ctypes.string_at(ctypes.cast(data, ctypes.c_void_p), int(frames) * 4)
                self._audio.enqueue(raw)
            except Exception:
                pass
        return frames

    def _on_input_poll(self) -> None:
        pass  # el estado se actualiza desde los eventos de Qt via set_input

    def _on_input_state(self, port, device, index, button_id) -> int:
        if port == 0 and device == _DEVICE_JOYPAD:
            return self._input_state.get(int(button_id), 0)
        return 0

    # -- EmulatorCore --------------------------------------------------------
    def load_game(self, path: str) -> bool:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return False
        if self._game_loaded:
            self._lib.retro_unload_game()
            self._game_loaded = False
        # Reinicia el audio: el nuevo juego puede tener otra frecuencia.
        self.stop_audio()
        self._audio = None
        self._audio_failed = False

        with open(path, "rb") as fh:
            data = fh.read()
        # Buffer propio que mantiene viva la ROM mientras el nucleo la use.
        self._rom_buffer = ctypes.create_string_buffer(data, len(data))
        info = _RetroGameInfo(
            path=path.encode("utf-8"),
            data=ctypes.cast(self._rom_buffer, ctypes.c_void_p),
            size=len(data),
            meta=None,
        )
        ok = bool(self._lib.retro_load_game(ctypes.byref(info)))
        if not ok:
            self._rom_buffer = None
            return False

        self._game_loaded = True
        self._title = os.path.splitext(os.path.basename(path))[0]
        self._input_state.clear()
        self._frame = None

        av = _RetroSystemAVInfo()
        self._lib.retro_get_system_av_info(ctypes.byref(av))
        self._av = AVInfo(
            av.geometry.base_width or NATIVE_WIDTH,
            av.geometry.base_height or NATIVE_HEIGHT,
            av.timing.fps or 60.0,
            av.timing.sample_rate or 32040.0,
        )
        return True

    def run_frame(self) -> None:
        if self._game_loaded:
            self._lib.retro_run()       # genera video y, via callback, audio
            if self._audio is not None and self._audio_playing:
                self._audio.flush()

    def get_frame(self) -> QImage:
        if self._frame is not None:
            return self._frame
        blank = QImage(NATIVE_WIDTH, NATIVE_HEIGHT, QImage.Format.Format_RGB32)
        blank.fill(QColor("#0D0E12"))
        return blank

    def av_info(self) -> AVInfo:
        return self._av

    def set_input(self, button_id: int, pressed: bool) -> None:
        self._input_state[int(button_id)] = 1 if pressed else 0

    def save_state(self) -> bytes:
        size = int(self._lib.retro_serialize_size())
        if size <= 0:
            return b""
        buf = (ctypes.c_ubyte * size)()
        ok = bool(self._lib.retro_serialize(ctypes.cast(buf, ctypes.c_void_p), size))
        return bytes(buf) if ok else b""

    def load_state(self, blob: bytes) -> bool:
        if not blob:
            return False
        size = len(blob)
        buf = (ctypes.c_ubyte * size).from_buffer_copy(blob)
        return bool(self._lib.retro_unserialize(ctypes.cast(buf, ctypes.c_void_p), size))

    # -- control de audio ----------------------------------------------------
    def start_audio(self) -> None:
        if self._audio_failed:
            return
        if self._audio is None:
            try:
                from .audio import AudioPlayer
                self._audio = AudioPlayer(self._av.sample_rate)
            except Exception as exc:  # sin dispositivo, formato, etc.
                print(f"[adapter] Audio no disponible ({exc}).", file=sys.stderr)
                self._audio_failed = True
                return
        self._audio.start()
        self._audio_playing = True

    def pause_audio(self) -> None:
        if self._audio is not None:
            self._audio.pause()
        self._audio_playing = False

    def resume_audio(self) -> None:
        if self._audio is not None:
            self._audio.resume()
            self._audio_playing = True

    def stop_audio(self) -> None:
        if self._audio is not None:
            self._audio.stop()
        self._audio_playing = False

    def unload(self) -> None:
        self.stop_audio()
        if self._game_loaded:
            self._lib.retro_unload_game()
            self._game_loaded = False
        self._rom_buffer = None
        self._frame = None
        self._input_state.clear()

    def shutdown(self) -> None:
        """Libera el nucleo por completo. Llamar al cerrar la aplicacion."""
        self.unload()
        self._audio = None
        if self._inited:
            self._lib.retro_deinit()
            self._inited = False


def _resolve_lib_path(lib_path: str) -> str:
    """Resuelve la ruta de la biblioteca con independencia del cwd."""
    if os.path.isabs(lib_path) and os.path.exists(lib_path):
        return lib_path
    # Raiz del repositorio = dos niveles por encima de este archivo.
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidates = [lib_path, os.path.join(repo_root, lib_path)]
    for cand in candidates:
        if os.path.exists(cand):
            return cand
    return lib_path  # se intentara igualmente; CDLL lanzara OSError si no existe


def create_core(lib_path: str = "kernel/snes9x_libretro.dylib") -> EmulatorCore:
    """Devuelve el nucleo real si la biblioteca carga; si no, el simulado.

    Permite que la aplicacion siga siendo utilizable (modo demostracion)
    aunque el nucleo nativo no este presente o falle al inicializar.
    """
    try:
        core = LibretroCore(_resolve_lib_path(lib_path))
        core.backend = "libretro"  # type: ignore[attr-defined]
        return core
    except (OSError, AttributeError) as exc:
        print(
            f"[adapter] Núcleo libretro no disponible ({exc}); usando núcleo "
            "simulado (modo demostración).",
            file=sys.stderr,
        )
        core = MockEmulatorCore()
        core.backend = "mock"  # type: ignore[attr-defined]
        return core
