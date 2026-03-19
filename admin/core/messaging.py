# =============================================================
#  HERMES — admin/core/messaging.py
#  Construcción y envío de mensajes emergentes a los clientes
# =============================================================

from shared.constants import CMD_MENSAJE, ICONOS
from admin.core.network import enviar_a_todos, enviar_a_uno, resumen


def _construir_orden(titulo: str, texto: str, icono: str) -> dict:
    """
    Valida los parámetros y construye el string de la orden.
    Retorna {"ok": True, "orden": "..."} o {"ok": False, "error": "..."}
    """
    titulo = titulo.strip()
    texto  = texto.strip()
    icono  = icono.strip().lower()

    if not titulo:
        return {"ok": False, "error": "El título no puede estar vacío"}

    if not texto:
        return {"ok": False, "error": "El mensaje no puede estar vacío"}

    if icono not in ICONOS:
        iconos_validos = ", ".join(ICONOS.keys())
        return {"ok": False, "error": f"Ícono inválido. Opciones: {iconos_validos}"}

    # Formato: "MENSAJE|titulo|texto|icono"
    orden = f"{CMD_MENSAJE}|{titulo}|{texto}|{icono}"
    return {"ok": True, "orden": orden}


def enviar_mensaje_todos(titulo: str, texto: str, icono: str = "info") -> dict:
    """
    Envía un mensaje emergente a todas las PCs registradas.
    Retorna el resumen de resultados.
    """
    construccion = _construir_orden(titulo, texto, icono)
    if not construccion["ok"]:
        return construccion

    resultados = enviar_a_todos(construccion["orden"])
    return resumen(resultados)


def enviar_mensaje_uno(ip: str, titulo: str, texto: str, icono: str = "info") -> dict:
    """
    Envía un mensaje emergente a una sola PC específica.
    Retorna el resultado de esa PC.
    """
    construccion = _construir_orden(titulo, texto, icono)
    if not construccion["ok"]:
        return construccion

    return enviar_a_uno(ip, construccion["orden"])