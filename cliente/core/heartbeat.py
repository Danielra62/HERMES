"""Heartbeats periódicos dirigidos al admin aprendido por TCP."""

import secrets
import socket
import threading

from shared.constants import PUERTO_HEARTBEAT
from shared.protocol import TipoOrden, enviar_orden, recv_exact


TIMEOUT_HEARTBEAT = 2
INTERVALO_HEARTBEAT_SEGUNDOS = 30 * 60
_LOCK_ADMIN = threading.Lock()
_IP_ADMIN: str | None = None
_HILO_HEARTBEAT: threading.Thread | None = None
_CAMBIO_ADMIN = threading.Event()


def enviar_ping_disponibilidad(host: str) -> bool:
    """Envía un HEARTBEAT v2 al admin indicado y devuelve si recibió ACK."""
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
        print(f"[HEARTBEAT][WARN] No se pudo notificar a {host}: {exc}")
        return False


def _enviar_periodicamente() -> None:
    while True:
        _CAMBIO_ADMIN.clear()
        with _LOCK_ADMIN:
            host = _IP_ADMIN
        if host is not None:
            enviar_ping_disponibilidad(host)
        _CAMBIO_ADMIN.wait(INTERVALO_HEARTBEAT_SEGUNDOS)


def registrar_ip_admin(ip: str) -> None:
    """Guarda la IP observada en una conexión entrante y activa heartbeats."""
    global _IP_ADMIN, _HILO_HEARTBEAT

    if not ip or ip == "0.0.0.0":
        return

    with _LOCK_ADMIN:
        cambio = _IP_ADMIN != ip
        _IP_ADMIN = ip
        if _HILO_HEARTBEAT is None or not _HILO_HEARTBEAT.is_alive():
            _HILO_HEARTBEAT = threading.Thread(
                target=_enviar_periodicamente,
                name="HermesHeartbeatClient",
                daemon=True,
            )
            _HILO_HEARTBEAT.start()
        elif cambio:
            _CAMBIO_ADMIN.set()

    if cambio:
        print(f"[HEARTBEAT] Admin aprendido desde conexión TCP: {ip}")


def obtener_ip_admin() -> str | None:
    """Devuelve la IP aprendida, principalmente para diagnóstico y pruebas."""
    with _LOCK_ADMIN:
        return _IP_ADMIN
