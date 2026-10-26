import ctypes
import ntpath


def aplicar_fondo(ruta_local: str) -> bool:
    """Aplica como fondo de Windows una imagen guardada en una ruta local."""
    unidad, _ = ntpath.splitdrive(ruta_local)
    if not ntpath.isabs(ruta_local) or not unidad or unidad.startswith("\\\\"):
        raise ValueError("La ruta del fondo debe ser absoluta y local")
    if ctypes.windll.kernel32.GetDriveTypeW(f"{unidad}\\") == 4:
        raise ValueError("La ruta del fondo no puede estar en una unidad de red")

    print(f"[INFO] Aplicando fondo: {ruta_local}")
    return bool(ctypes.windll.user32.SystemParametersInfoW(20, 0, ruta_local, 3))