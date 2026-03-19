import ctypes
from shared.constants import ICONOS

def mostrar_mensaje(titulo, texto, icono):
    tipo = ICONOS.get(icono, 0x40)

    ctypes.windll.user32.MessageBoxW(0, texto, titulo, tipo)