"""Reproduccion de audio del nucleo de emulacion (QtMultimedia).

Recibe muestras PCM S16 estereo intercaladas (L,R,L,R...) generadas por el
nucleo y las reproduce en tiempo real mediante ``QAudioSink`` en modo push.

Diseño:
- Todo ocurre en el hilo principal. El nucleo genera audio dentro de
  ``retro_run`` (invocado por el QTimer de la sesion); ``enqueue`` acumula y
  ``flush`` entrega al dispositivo. ``QAudioSink`` reproduce en su propio hilo
  de backend, por lo que ``write`` solo copia y retorna: la GUI nunca se bloquea.
- La latencia se acota con el tamaño de buffer del sink y un tope de backlog;
  ``bytesFree`` evita escribir mas de lo que el dispositivo puede aceptar.
- **Toda escritura y todo descarte se alinean a un frame estereo completo
  (4 bytes).** Escribir media muestra desincronizaria los canales L/R en el
  flujo continuo del dispositivo, produciendo un zumbido aspero persistente.
- Suavizado: un filtro pasa-bajos de un polo atenua los agudos mas duros y una
  ligera reduccion de ganancia evita la saturacion, para un tono mas calido.

No introduce dependencias nuevas: QtMultimedia viene con PySide6.
"""
from __future__ import annotations

import array
import math

from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices

BYTES_PER_FRAME = 4          # 2 canales * 2 bytes (S16)
DEFAULT_LATENCY_MS = 120     # objetivo de latencia (tamaño de buffer del sink)
MAX_BACKLOG_MS = 200         # backlog maximo acumulado antes de descartar

# Suavizado por defecto.
DEFAULT_CUTOFF_HZ = 13000.0  # frecuencia de corte del pasa-bajos (agudos)
DEFAULT_GAIN = 0.85          # ganancia maestra (<1 evita aspereza/saturacion)

_INT16_MIN, _INT16_MAX = -32768, 32767


class AudioPlayer:
    """Salida de audio en tiempo real para muestras PCM S16 estereo."""

    def __init__(
        self,
        sample_rate: float,
        latency_ms: int = DEFAULT_LATENCY_MS,
        cutoff_hz: float = DEFAULT_CUTOFF_HZ,
        gain: float = DEFAULT_GAIN,
    ) -> None:
        fmt = QAudioFormat()
        fmt.setSampleRate(int(sample_rate))
        fmt.setChannelCount(2)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)

        device = QMediaDevices.defaultAudioOutput()
        if device is None or device.isNull():
            raise RuntimeError("No hay dispositivo de salida de audio disponible.")
        if not device.isFormatSupported(fmt):
            fmt = device.preferredFormat()

        self._bytes_per_sec = int(sample_rate) * BYTES_PER_FRAME
        self._sink = QAudioSink(device, fmt)
        self._sink.setBufferSize(max(2048, self._bytes_per_sec * latency_ms // 1000))

        self._io = None                       # QIODevice de escritura (push mode)
        self._pending = bytearray()
        # El tope se alinea a frame para que el descarte nunca parta una muestra.
        cap = self._bytes_per_sec * MAX_BACKLOG_MS // 1000
        self._cap = cap - (cap % BYTES_PER_FRAME)
        self._active = False

        # Coeficiente del pasa-bajos de un polo: alpha = dt / (RC + dt).
        rc = 1.0 / (2.0 * math.pi * max(1.0, cutoff_hz))
        dt = 1.0 / max(1, int(sample_rate))
        self._alpha = dt / (rc + dt)
        self._gain = gain
        self._lp_l = 0.0                       # estado del filtro por canal
        self._lp_r = 0.0

    def _soften(self, data: bytes) -> bytes:
        """Aplica pasa-bajos + ganancia a un chunk S16 estereo, con estado."""
        samples = array.array("h")
        samples.frombytes(data)
        a, g = self._alpha, self._gain
        yl, yr = self._lp_l, self._lp_r
        for i in range(0, len(samples) - 1, 2):
            yl += a * (samples[i] - yl)
            yr += a * (samples[i + 1] - yr)
            left = int(yl * g)
            right = int(yr * g)
            # Recorte a rango int16.
            samples[i] = _INT16_MAX if left > _INT16_MAX else _INT16_MIN if left < _INT16_MIN else left
            samples[i + 1] = _INT16_MAX if right > _INT16_MAX else _INT16_MIN if right < _INT16_MIN else right
        # Guarda el estado del filtro (pre-ganancia) para continuidad entre chunks.
        self._lp_l, self._lp_r = yl, yr
        return samples.tobytes()

    def start(self) -> None:
        """Arranca o reanuda la reproduccion."""
        if self._io is None:
            self._io = self._sink.start()      # modo push: devuelve el QIODevice
        else:
            self._sink.resume()
        self._active = self._io is not None

    def enqueue(self, data: bytes) -> None:
        """Acumula muestras (suavizadas) generadas por el nucleo durante el frame."""
        if not self._active:
            return
        self._pending += self._soften(data)
        # Acota la latencia: si el video va por delante, descarta lo mas viejo,
        # siempre por frames estereo completos para no desincronizar L/R.
        excess = len(self._pending) - self._cap
        if excess > 0:
            excess -= excess % BYTES_PER_FRAME
            if excess > 0:
                del self._pending[:excess]

    def flush(self) -> None:
        """Entrega al dispositivo tanto como acepte, en frames estereo completos."""
        if not self._active or self._io is None or not self._pending:
            return
        free = self._sink.bytesFree()
        if free <= 0:
            return
        n = min(free, len(self._pending))
        n -= n % BYTES_PER_FRAME               # nunca escribir media muestra
        if n <= 0:
            return
        self._io.write(bytes(self._pending[:n]))
        del self._pending[:n]

    def pause(self) -> None:
        if self._active:
            self._sink.suspend()
            self._active = False

    def resume(self) -> None:
        if self._io is not None:
            self._sink.resume()
            self._active = True

    def stop(self) -> None:
        self._active = False
        self._pending.clear()
        try:
            self._sink.stop()
        except Exception:
            pass
        self._io = None
