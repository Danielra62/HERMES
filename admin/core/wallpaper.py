# =============================================================
#  HERMES — admin/core/wallpaper.py
#  Publica la imagen del wallpaper en la carpeta compartida
#  del servidor para que los clientes puedan leerla.
# =============================================================

import os
import shutil
import subprocess
from shared.constants import (
    CARPETA_COMPARTIDA,
    NOMBRE_IMAGEN,
    IP_SERVIDOR,
    SERVIDOR_USUARIO,
    SERVIDOR_PASSWORD
)


def _conectar_servidor() -> dict:
    """
    Mapea la carpeta compartida del servidor usando net use.
    Necesario para autenticarse antes de leer o escribir archivos.
    Retorna {"ok": True} o {"ok": False, "error": "..."}
    """
    # [Modificación para pruebas en Linux]
    if os.name != 'nt':
        return {"ok": True, "nota": "Simulado en Linux"}

    try:
        resultado = subprocess.run(
            [
                "net", "use", CARPETA_COMPARTIDA,
                f"/user:{SERVIDOR_USUARIO}", SERVIDOR_PASSWORD,
                "/persistent:no"
            ],
            capture_output=True,
            text=True
        )
        # net use retorna 0 si tuvo éxito o si la conexión ya existía
        if resultado.returncode == 0:
            return {"ok": True}
        else:
            return {"ok": False, "error": resultado.stderr.strip()}

    except FileNotFoundError:
        return {"ok": False, "error": "Comando 'net use' no disponible — ¿estás en Windows?"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def publicar_wallpaper(ruta_imagen: str) -> dict:
    """
    Copia la imagen seleccionada por el admin a la carpeta
    compartida del servidor como 'wallpaper.jpg'.
    """

    # ── 1. Verificar que el archivo existe ────────────────────
    if not os.path.exists(ruta_imagen):
        return {"ok": False, "error": f"No se encontró la imagen: {ruta_imagen}"}

    extensiones_validas = (".jpg", ".jpeg", ".png", ".bmp")
    if not ruta_imagen.lower().endswith(extensiones_validas):
        return {"ok": False, "error": "Formato no soportado. Usa JPG, PNG o BMP"}

    # [Modificación para pruebas en Linux]
    if os.name != 'nt':
        return {"ok": True, "destino": "SIMULADOR_LINUX (no se copió el archivo)"}

    # ── 2. Conectar al servidor ───────────────────────────────
    conexion = _conectar_servidor()
    if not conexion["ok"]:
        return {"ok": False, "error": f"No se pudo conectar al servidor: {conexion['error']}"}

    # ── 3. Copiar imagen a la carpeta compartida ──────────────
    try:
        destino = os.path.join(CARPETA_COMPARTIDA, NOMBRE_IMAGEN)
        shutil.copy2(ruta_imagen, destino)
        return {"ok": True, "destino": destino}

    except PermissionError:
        return {"ok": False, "error": "Sin permisos para escribir en la carpeta compartida"}
    except Exception as e:
        return {"ok": False, "error": str(e)}