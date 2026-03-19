import ctypes
from shared.constants import CARPETA_COMPARTIDA, NOMBRE_IMAGEN

def cambiar_fondo():
    ruta = f"{CARPETA_COMPARTIDA}\\{NOMBRE_IMAGEN}"

    print(f"[INFO] Aplicando fondo: {ruta}")

    ctypes.windll.user32.SystemParametersInfoW(20, 0, ruta, 3)