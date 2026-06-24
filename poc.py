import ctypes
import sys
import pygame

# Variable global para almacenar el formato de pixel negociado
formato_pixel = 0

# Mapeo de botones de SNES (Libretro ID) a teclas de Pygame
MAPEO_TECLADO = {
    4: pygame.K_UP,       # RETRO_DEVICE_ID_JOYPAD_UP
    5: pygame.K_DOWN,     # RETRO_DEVICE_ID_JOYPAD_DOWN
    6: pygame.K_LEFT,     # RETRO_DEVICE_ID_JOYPAD_LEFT
    7: pygame.K_RIGHT,    # RETRO_DEVICE_ID_JOYPAD_RIGHT
    8: pygame.K_x,        # RETRO_DEVICE_ID_JOYPAD_A
    0: pygame.K_z,        # RETRO_DEVICE_ID_JOYPAD_B
    9: pygame.K_s,        # RETRO_DEVICE_ID_JOYPAD_X
    1: pygame.K_a,        # RETRO_DEVICE_ID_JOYPAD_Y
    10: pygame.K_q,       # RETRO_DEVICE_ID_JOYPAD_L
    11: pygame.K_w,       # RETRO_DEVICE_ID_JOYPAD_R
    3: pygame.K_RETURN,   # RETRO_DEVICE_ID_JOYPAD_START
    2: pygame.K_RSHIFT,   # RETRO_DEVICE_ID_JOYPAD_SELECT
}

# Inicializacion de ventana para visualizar el framebuffer
pygame.init()
pantalla = pygame.display.set_mode((256, 224), pygame.SCALED)
pygame.display.set_caption("Validacion SNES9x Libretro")

# Carga de la biblioteca compartida del nucleo
try:
    nucleo = ctypes.CDLL('./kernel/snes9x_libretro.dylib')
except OSError:
    print("Error al cargar snes9x_libretro.dylib. Verifique la ruta.")
    sys.exit(1)

# Definicion de firmas para los callbacks de Libretro segun la especificacion C ABI
RetroEnvironment_t = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_uint, ctypes.c_void_p)
RetroVideoRefresh_t = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_size_t)
RetroAudioSample_t = ctypes.CFUNCTYPE(None, ctypes.c_int16, ctypes.c_int16)
RetroAudioSampleBatch_t = ctypes.CFUNCTYPE(ctypes.c_size_t, ctypes.POINTER(ctypes.c_int16), ctypes.c_size_t)
RetroInputPoll_t = ctypes.CFUNCTYPE(None)
RetroInputState_t = ctypes.CFUNCTYPE(ctypes.c_int16, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint)

# Implementacion minima de callbacks obligatorios
@RetroEnvironment_t
def cb_environment(cmd, data):
    global formato_pixel
    # Comando 10 corresponde a RETRO_ENVIRONMENT_SET_PIXEL_FORMAT
    if cmd == 10:
        formato_pixel = ctypes.cast(data, ctypes.POINTER(ctypes.c_uint)).contents.value
        return True
    return False

@RetroVideoRefresh_t
def cb_video_refresh(data, width, height, pitch):
    if data:
        try:
            buffer_crudo = ctypes.string_at(data, height * pitch)
            bytes_por_pixel = 2 if formato_pixel in (0, 2) else 4
            
            # Calcular el ancho real en memoria para procesar el stride (pitch) correctamente
            ancho_real = pitch // bytes_por_pixel
            
            # Crear superficie nativa de Pygame con la profundidad de color adecuada
            superficie = pygame.Surface((ancho_real, height), depth=bytes_por_pixel * 8)
            
            # Escribir los bytes crudos directamente en la memoria de la superficie
            if superficie.get_pitch() == pitch:
                superficie.get_buffer().write(buffer_crudo)
            
            # Extraer unicamente el area visualizable y ajustar a la resolucion de la ventana
            area_visible = pygame.Rect(0, 0, width, height)
            superficie_recortada = superficie.subsurface(area_visible)
            superficie_escalada = pygame.transform.scale(superficie_recortada, pantalla.get_size())
            
            pantalla.blit(superficie_escalada, (0, 0))
            pygame.display.flip()
        except Exception:
            pass

@RetroAudioSample_t
def cb_audio_sample(left, right):
    pass

@RetroAudioSampleBatch_t
def cb_audio_sample_batch(data, frames):
    return frames

@RetroInputPoll_t
def cb_input_poll():
    pygame.event.pump()

@RetroInputState_t
def cb_input_state(port, device, index, id):
    # Dispositivo 1 corresponde a RETRO_DEVICE_JOYPAD en la especificacion
    if port == 0 and device == 1:
        tecla = MAPEO_TECLADO.get(id)
        if tecla is not None:
            teclas_presionadas = pygame.key.get_pressed()
            return 1 if teclas_presionadas[tecla] else 0
    return 0

# Asignacion de los callbacks al nucleo en memoria
nucleo.retro_set_environment(cb_environment)
nucleo.retro_set_video_refresh(cb_video_refresh)
nucleo.retro_set_audio_sample(cb_audio_sample)
nucleo.retro_set_audio_sample_batch(cb_audio_sample_batch)
nucleo.retro_set_input_poll(cb_input_poll)
nucleo.retro_set_input_state(cb_input_state)

# Inicializacion de la logica interna del emulador
nucleo.retro_init()

# Definicion de la estructura de datos requerida para cargar la ROM
class RetroGameInfo(ctypes.Structure):
    _fields_ = [
        ("path", ctypes.c_char_p),
        ("data", ctypes.c_void_p),
        ("size", ctypes.c_size_t),
        ("meta", ctypes.c_char_p)
    ]

ruta_rom = b"./ROMS/SuperMarioKart.sfc"
try:
    with open(ruta_rom, 'rb') as f:
        datos_rom = f.read()
except FileNotFoundError:
    print("No se encontro la ROM en la ruta especificada.")
    sys.exit(1)

# Construccion de la estructura apuntando al buffer de memoria de la ROM
info_juego = RetroGameInfo(
    path=ruta_rom,
    data=ctypes.cast(ctypes.c_char_p(datos_rom), ctypes.c_void_p),
    size=len(datos_rom),
    meta=None
)

# Instruccion de carga al nucleo
if not nucleo.retro_load_game(ctypes.byref(info_juego)):
    print("El nucleo rechazo la ROM suministrada.")
    sys.exit(1)

# Bucle principal de control
reloj = pygame.time.Clock()
ejecutando = True

while ejecutando:
    for evento in pygame.event.get():
        if evento.type == pygame.QUIT:
            ejecutando = False
            
    # Solicitud de procesamiento de un fotograma
    nucleo.retro_run()
    # Limitacion de la ejecucion a 30 fotogramas por segundo
    reloj.tick(30)

# Procedimiento de limpieza y liberacion de memoria
nucleo.retro_unload_game()
nucleo.retro_deinit()
pygame.quit()