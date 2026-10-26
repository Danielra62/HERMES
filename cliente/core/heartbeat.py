"""Envío del heartbeat inicial del cliente al administrador."""

import os
import secrets
import socket

from shared.constants import PUERTO_HEARTBEAT
from shared.protocol import TipoOrden, enviar_orden, recv_exact


TIMEOUT_HEARTBEAT = 2


def enviar_ping_disponibilidad() -> bool:
    """Notifica disponibilidad al admin; un fallo no debe detener el cliente."""
    host = os.getenv("HERMES_ADMIN_HOST", "").strip()
    if not host:
        print(
            "[WARN] HERMES_ADMIN_HOST no está configurado; "
            "se omite el heartbeat inicial"
        )
        return False

    order_id = secrets.randbelow(0xFFFFFFFF) + 1
    try:
        with socket.create_connection(
            (host, PUERTO_HEARTBEAT),
            timeout=TIMEOUT_HEARTBEAT,
        ) as sock:
            sock.settimeout(TIMEOUT_HEARTBEAT)
            enviar_orden(sock, TipoOrden.HEARTBEAT, order_id, b"")
            respuesta = recv_exact(sock, 2)
            if respuesta != b"OK":
                raise ConnectionError(f"ACK inesperado: {respuesta!r}")
        print(f"[HEARTBEAT] Admin confirmó disponibilidad ({host})")
        return True
    except (OSError, ValueError) as exc:
        print(f"[WARN] No se pudo notificar disponibilidad a {host}: {exc}")
        return False
