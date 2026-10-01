# =============================================================
#  HERMES — admin/core/messaging.py
#  Construcción y envío v2 de mensajes emergentes a los clientes
# =============================================================

import json

from shared.constants import ICONOS
from shared.protocol import TipoOrden
from admin.core.network import (
    enviar_v2_a_lista,
    enviar_v2_a_todos,
    enviar_v2_a_uno,
    resumen,
)


def _construir_payload(titulo: str, texto: str, icono: str) -> dict:
    """
    Valida los parámetros y construye el payload JSON UTF-8 del mensaje.
    Retorna {"ok": True, "payload": bytes} o {"ok": False, "error": "..."}.
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

    payload = json.dumps(
        {"titulo": titulo, "texto": texto, "icono": icono},
        ensure_ascii=False,
    ).encode("utf-8")
    return {"ok": True, "payload": payload}


def enviar_mensaje_todos(titulo: str, texto: str, icono: str = "info") -> dict:
    """
    Envía un mensaje emergente a todas las PCs registradas.
    Retorna el resumen de resultados.
    """
    construccion = _construir_payload(titulo, texto, icono)
    if not construccion["ok"]:
        return construccion

    resultados = enviar_v2_a_todos(
        TipoOrden.MENSAJE,
        construccion["payload"],
    )
    return resumen(resultados)


def enviar_mensaje_uno(ip: str, titulo: str, texto: str, icono: str = "info") -> dict:
    """
    Envía un mensaje emergente a una sola PC específica.
    Retorna el resultado de esa PC.
    """
    construccion = _construir_payload(titulo, texto, icono)
    if not construccion["ok"]:
        return construccion

    return enviar_v2_a_uno(ip, TipoOrden.MENSAJE, construccion["payload"])

def enviar_mensaje_grupo(grupo: str, titulo: str, texto: str, icono: str = "info") -> dict:
    """
    Envía un mensaje emergente a todos los clientes de un grupo específico.
    Retorna el resumen de resultados.
    """
    from admin.core.clients import obtener_grupos
    construccion = _construir_payload(titulo, texto, icono)
    if not construccion["ok"]:
        return construccion

    ips = [c["ip"] for c in obtener_grupos().get(grupo, [])]
    resultados = enviar_v2_a_lista(
        TipoOrden.MENSAJE,
        construccion["payload"],
        ips,
    )
    return resumen(resultados)
