# Implementación de la interfaz — SNES Emulator (PySide6)

Representación funcional y ejecutable de `docs/descripcion_interfaz.md`. La
lógica de emulación **no** se implementa: la UI opera contra un núcleo
simulado a través de un adaptador, listo para sustituirse por el núcleo real.

## Ejecutar

```bash
source .venv/bin/activate
python main.py
```

Requisitos en `requirements.txt` (PySide6 6.11). Las ROMs de ejemplo están en
`ROMS/`. Atajos: Cmd/Ctrl+O cargar, Cmd/Ctrl+S guardar, Cmd/Ctrl+L cargar
partida, Cmd/Ctrl+W salir del juego, Espacio pausar, Cmd+Ctrl+F / F11 pantalla
completa, Escape cancela escucha de mapeo o sale de pantalla completa.

## Arquitectura (preparada para el núcleo real)

- **`snes_ui/core/adapter.py`** — `EmulatorCore` (ABC) define el contrato; toda
  la UI depende solo de esta interfaz. `MockEmulatorCore` genera fotogramas
  animados. Una integración real (p. ej. ctypes a `snes9x_libretro`) solo debe
  implementar el ABC, sin tocar la UI.
- **`snes_ui/core/session.py`** — `SessionController`: máquina de estados única
  (los 5 estados de la especificación) y bucle de fotogramas por `QTimer`.
  Emite señales que la ventana observa para conmutar vistas y habilitar/
  deshabilitar acciones dependientes de sesión.
- **`snes_ui/services/`** — `InputService` (enumeración simulada de
  dispositivos, estado de conexión, perfil de teclas) y `SaveService` (estados
  de guardado en memoria). `MappingModel` modela las 12 asignaciones.
- **`snes_ui/widgets/`** — componentes reutilizables: `StateCard`, `ActionBar`,
  `ControlPanel`, `SegmentedControl`, `MappingRow` (instanciado ×12),
  `ControllerDiagram`, `VideoSurface`, `GameStage`, `Toast`, `OverlayActionBar`.
- **`snes_ui/theme.py`** — tokens de color/tipografía/espaciado/radio y QSS de
  los temas claro y oscuro. **`snes_ui/settings.py`** — persistencia con
  `QSettings` (geometría, tema, modo de escalado, pestaña, dispositivo, mapeos).

Cobertura del alcance: ventana principal, escenario con los 5 estados, panel
lateral (2 vistas), barra de acciones inferior + barra superpuesta de pantalla
completa, menús Archivo/Ver, diálogos (carga de ROM, selector de estados,
confirmaciones), temas claro/oscuro, navegación por pestañas, componentes
reutilizables y mock services.

## Decisiones ante ambigüedades de la especificación

1. **Botón de acción con doble etiqueta** — La especificación pide `QToolButton`
   con icono + etiqueta principal + secundaria. `QToolButton` solo admite un
   texto; se renderizan ambas etiquetas como texto de dos líneas bajo el icono.
   Fiel al widget indicado y a la disposición vertical pedida.
2. **Iconografía** — La especificación recomienda SF Symbols (macOS) / iconos de
   línea (Windows). Para mantener la demo autocontenida sin recursos externos,
   los iconos se renderizan desde glifos Unicode/emoji a `QIcon`
   (`widgets/icons.py`). Sustituibles por un set real sin cambios estructurales.
3. **Ilustración del mando** — Se implementa como `QWidget` pintado
   (`ControllerDiagram`) en lugar de un SVG externo, evitando dependencias de
   assets. El mismo widget sirve de ilustración estática y de diagrama en vivo.
4. **Captura de asignación de botones** — La "siguiente entrada física
   detectada" se captura desde el teclado vía un event filter de aplicación; la
   etiqueta resultante se prefija con el dispositivo activo (p. ej. `Tecla: X`,
   `Xbox: …`). En ausencia de hardware real, es la interpretación demostrable.
5. **Estado de conexión simulado** — `Refrescar` cicla de forma determinística
   entre Conectado / Reconectando / Desconectado para ejercitar los tres
   indicadores. "Keyboard" se reporta siempre conectado.
6. **Estado de carga perceptible** — Tras elegir la ROM se muestra el estado
   "Cargando" ~600 ms antes de validar, para que la transición sea visible
   (la validación del mock es instantánea).
7. **Validación de ROM (mock)** — Se acepta solo `.sfc`/`.smc` existente y no
   vacío; cualquier otra cosa dispara el estado de error con opción de
   reintentar, ejercitando el flujo de error de la especificación.
8. **Marca temporal de estados guardados** — Sin reloj real en la demo, se usa
   un contador incremental ("Ranura NN") como etiqueta estable y reproducible.
9. **`Cargar partida` siempre habilitada** — La especificación indica que puede
   activarse "con o sin sesión activa"; se mantiene habilitada incluso en vacío
   y muestra el estado vacío del selector cuando no hay estados.
10. **Truncado de nombres largos en el panel de 320 px** — Con el ancho fijo y
    el botón de asignación de mínimo 104 px, los nombres más largos (p. ej.
    "D-Pad Izquierda") pueden recortarse levemente. Se priorizó respetar las
    medidas de la especificación sobre evitar el recorte.
11. **Translucidez de paneles** — Opcional según la especificación; se usa
    superficie sólida del tema (más fiable multiplataforma), como permite el
    documento.

---

# Integración del núcleo de emulación real (libretro / snes9x)

Se conecta el núcleo real portando la lógica de `poc.py` **dentro de la
arquitectura existente, sin tocar la interfaz**. La clave fue que la UI ya
dependía solo del ABC `EmulatorCore`: bastó añadir una implementación nueva.

## Qué se hizo

- **`LibretroCore(EmulatorCore)`** en `snes_ui/core/adapter.py`: enlace al ABI
  de libretro vía `ctypes` (carga de `.dylib`, registro de los 6 callbacks,
  `retro_init`, `retro_load_game`, `retro_run`, `retro_unload_game`,
  `retro_deinit`), portado de `poc.py`.
- **Factoría `create_core()`**: intenta el núcleo real y, si la biblioteca o un
  símbolo faltan, cae al `MockEmulatorCore` (la app sigue usable en modo
  demostración). `main_window.py` solo cambió esta línea de construcción.
- **Entrada cableada**: el event filter de la ventana ahora también llama a
  `core.set_input(retro_id, pressed)` además de actualizar el diagrama en vivo.
- **Cierre ordenado**: `closeEvent` invoca `core.shutdown()` (`retro_deinit`).

## Decisiones técnicas

1. **Video con QImage en vez de pygame** — `poc.py` usaba `pygame.Surface`; aquí
   el callback de video convierte el buffer crudo a `QImage` respetando `pitch`
   y el formato negociado (RGB565 → `Format_RGB16`, 0RGB1555 → `Format_RGB555`,
   XRGB8888 → `Format_RGB32`). Se hace `.copy()` para desligar el `QImage` del
   buffer temporal del núcleo, válido solo durante el callback. snes9x emite
   RGB565 con `pitch` 1024 (buffer interno de 512 px); se toman los `width`
   píxeles visibles por fila automáticamente.
2. **Referencias de callbacks vivas** — Se guardan los objetos `CFUNCTYPE` como
   atributos de instancia. Es obligatorio: si el recolector de Python los
   liberara, el núcleo invocaría memoria liberada (cierre silencioso o corrupción).
3. **Entrada por consulta (pull)** — libretro pregunta el estado de cada botón
   cada frame vía el callback `input_state`. Se mantiene un diccionario
   `{id_libretro: 0/1}` que `set_input()` actualiza desde los eventos de teclado
   de Qt. `input_poll` queda no-op (no se sondea hardware). El mapeo de teclas
   replica el de `poc.py` (X=A, Z=B, S=X, A=Y, Q=L, W=R, Enter=Start, Shift=Select).
4. **Estados de guardado reales** — `save_state`/`load_state` usan
   `retro_serialize_size`/`retro_serialize`/`retro_unserialize`. El blob real de
   SMK ronda los 825 KB. El `SaveService` simulado sigue gestionando la lista de
   ranuras en memoria; solo el contenido del estado pasó a ser real.
5. **Ciclo de vida multi-juego** — `retro_init` se llama una vez; cada
   `load_game` hace `retro_unload_game` previo si había un juego, permitiendo
   cambiar de ROM sin reiniciar el núcleo. `retro_deinit` solo al cerrar la app.
6. **`fps` real del temporizador** — `SessionController` ya usaba
   `av_info().fps`; ahora se obtiene de `retro_get_system_av_info`
   (≈60.0988 Hz NTSC) en lugar de un valor fijo.
7. **Audio no implementado** — Fiel a `poc.py`: los callbacks de audio son
   no-op (`audio_sample` vacío, `audio_sample_batch` devuelve `frames`). Es el
   único punto pendiente para un emulador "completo" con sonido.
8. **Ruta de la biblioteca robusta** — `create_core` resuelve
   `kernel/snes9x_libretro.dylib` relativa a la raíz del repositorio, no al
   directorio de trabajo, para que la app arranque desde cualquier cwd.

## Verificación

Probado headless (`QT_QPA_PLATFORM=offscreen`): carga de ROM, render real del
título de Super Mario Kart, 900+ frames, guardado/cargado de estado (824 KB),
ciclo de recarga entre ROMs, rechazo de ROM inválida y cierre ordenado. La
ventana real arranca sin fallos con el núcleo nativo.

---

# Audio en tiempo real

Completa el emulador con sonido, reutilizando la arquitectura existente y sin
añadir dependencias (QtMultimedia ya viene con PySide6).

## Flujo

El núcleo genera audio dentro de `retro_run`: snes9x llama al callback
`audio_sample_batch(data, frames)` con muestras **PCM S16 estéreo intercaladas**
(L,R,L,R…) a la frecuencia de `retro_get_system_av_info().timing.sample_rate`
(32040 Hz). Antes esos callbacks eran no-op; ahora encolan las muestras en un
reproductor.

- **`snes_ui/core/audio.py` → `AudioPlayer`**: envoltura de `QAudioSink`
  (QtMultimedia) en **modo push**, formato S16/2 canales/sample_rate del juego.
- **`LibretroCore`**: el callback de audio hace `AudioPlayer.enqueue(bytes)`;
  `run_frame` hace `AudioPlayer.flush()` tras `retro_run`.
- **`SessionController`**: arranca/pausa/reanuda/detiene el audio en las
  transiciones de estado (`start_audio` al ejecutar, `pause_audio` en pausa,
  `resume_audio` al reanudar, `stop_audio` en salir/error). Métodos añadidos al
  ABC `EmulatorCore` como no-op por defecto (el mock no produce audio).

## Cómo cumple cada requisito

- **Tiempo real / sincronía A-V** — Audio y video comparten el mismo reloj: el
  `QTimer` de la sesión invoca `run_frame` a la `fps` del núcleo (≈60.0988 Hz);
  en cada frame se generan ~534 cuadros de audio (32040/60.0988) y se entregan
  de inmediato. Las tasas de generación y consumo coinciden, así que la deriva
  es nula en régimen permanente y el buffer absorbe el jitter.
- **Sin bloqueos de GUI** — Todo corre en el hilo principal; `QAudioSink`
  reproduce en su propio hilo de backend. `QIODevice.write` solo copia y
  retorna, y nunca se escribe más de `bytesFree()`, por lo que jamás bloquea.
- **Buffers y latencia** — Buffer del sink ≈100 ms (latencia objetivo) y backlog
  acumulado acotado a 200 ms: si el video se adelanta, se descarta lo más viejo
  en vez de crecer la latencia; si hay un *underrun* puntual (hipo de GUI), el
  sink se recupera al siguiente flush.
- **Liberación de recursos** — `stop_audio` vacía el backlog y hace
  `QAudioSink.stop`; `unload` (salir/reiniciar) y `shutdown` (cierre de la app,
  vía `closeEvent`) lo invocan. Cambiar de ROM recrea el reproductor por si la
  nueva frecuencia difiere.
- **Integración con estados** — Cubierto por `SessionController` (ver arriba):
  ejecutar = suena, pausa = silencio suspendido, salir = detiene y libera.
- **Degradación** — Si no hay dispositivo o el formato no se soporta, se registra
  el aviso y la emulación continúa sin sonido (no se interrumpe el juego).

## Decisión de diseño

Se eligió **push mode** (flush por frame desde el hilo principal) frente a pull
mode (QIODevice propio con buffer circular y mutex en el hilo de audio): el push
es más simple, no necesita sincronización entre hilos —el callback de audio ya
corre en el hilo principal dentro de `retro_run`— y la cadencia natural del
`QTimer` a 60 fps mantiene la sincronía sin lógica adicional. Verificado headless:
sample_rate 32040, `QAudioSink` en `ActiveState`, escritura continua, y
arranque/pausa/reanudación/parada limpios en todas las transiciones de estado.
