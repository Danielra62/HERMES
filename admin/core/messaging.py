# =============================================================
#  HERMES — admin/core/messaging.py
#  Construcción y envío persistente de mensajes emergentes
# =============================================================

from shared.constants import ICONOS
from admin.core import order_delivery


def _construir_payload(titulo: str, texto: str, icono: str) -> dict:
    """
    Valida los parámetros y construye el objeto JSON del mensaje.
    Retorna {"ok": True, "payload": dict} o {"ok": False, "error": "..."}.
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

    payload = {"titulo": titulo, "texto": texto, "icono": icono}
    return {"ok": True, "payload": payload}


def enviar_mensaje_todos(titulo: str, texto: str, icono: str = "info") -> dict:
    """
    Envía un mensaje emergente a todas las PCs registradas.
    Retorna el resumen de resultados.
    """
    construccion = _construir_payload(titulo, texto, icono)
    if not construccion["ok"]:
        return construccion

    resultado = order_delivery.crear_y_entregar(
        tipo="MENSAJE",
        payload=construccion["payload"],
        destino_tipo="todos",
        destino_etiqueta=None,
    )
    return order_delivery.respuesta_masiva(resultado)


def enviar_mensaje_uno(ip: str, titulo: str, texto: str, icono: str = "info") -> dict:
    """
    Envía un mensaje emergente a una sola PC específica.
    Retorna el resultado de esa PC.
    """
    construccion = _construir_payload(titulo, texto, icono)
    if not construccion["ok"]:
        return construccion

    resultado = order_delivery.crear_y_entregar(
        tipo="MENSAJE",
        payload=construccion["payload"],
        destino_tipo="equipo",
        destino_etiqueta=ip.strip(),
    )
    return order_delivery.respuesta_individual(resultado)

def enviar_mensaje_grupo(grupo: str, titulo: str, texto: str, icono: str = "info") -> dict:
    """
    Envía un mensaje emergente a todos los clientes de un grupo específico.
    Retorna el resumen de resultados.
    """
    construccion = _construir_payload(titulo, texto, icono)
    if not construccion["ok"]:
        return construccion

    resultado = order_delivery.crear_y_entregar(
        tipo="MENSAJE",
        payload=construccion["payload"],
        destino_tipo="grupo",
        destino_etiqueta=grupo,
    )
    return order_delivery.respuesta_masiva(resultado)
