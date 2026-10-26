import ctypes
from shared.constants import CARPETA_COMPARTIDA, NOMBRE_IMAGEN


def aplicar_fondo(ruta):
    print(f"[INFO] Aplicando fondo: {ruta}")
    return bool(ctypes.windll.user32.SystemParametersInfoW(20, 0, ruta, 3))


def cambiar_fondo():
    ruta = f"{CARPETA_COMPARTIDA}\\{NOMBRE_IMAGEN}"
    aplicar_fondo(ruta)