import ctypes
from shared.constants import ICONOS

MB_SETFOREGROUND = 0x00010000
MB_TOPMOST = 0x00040000


def mostrar_mensaje(titulo, texto, icono):
    tipo = ICONOS.get(icono, 0x40)
    tipo |= MB_SETFOREGROUND | MB_TOPMOST

    ctypes.windll.user32.MessageBoxW(0, texto, titulo, tipo)