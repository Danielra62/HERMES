"""Simula un cliente enviando HEARTBEAT v2 al listener del admin.

Uso desde la raíz del proyecto:
    python -m scripts.pruebas.prueba_envio_heartbeat
    python -m scripts.pruebas.prueba_envio_heartbeat --host 192.168.1.10
"""

import argparse
import secrets
import socket

from shared.constants import PUERTO_HEARTBEAT, TIMEOUT
from shared.protocol import TipoOrden, enviar_orden, recv_exact


def enviar_heartbeat(host: str, puerto: int) -> int:
    order_id = secrets.randbits(32)
    with socket.create_connection((host, puerto), timeout=TIMEOUT) as sock:
        sock.settimeout(TIMEOUT)
        enviar_orden(sock, TipoOrden.HEARTBEAT, order_id, b"")
        respuesta = recv_exact(sock, 2)

    if respuesta != b"OK":
        raise RuntimeError(f"El admin rechazó el heartbeat: {respuesta!r}")
    print(f"Heartbeat aceptado: order_id={order_id}, destino={host}:{puerto}")
    return order_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="IP del admin")
    parser.add_argument("--port", type=int, default=PUERTO_HEARTBEAT)
    args = parser.parse_args()
    enviar_heartbeat(args.host, args.port)


if __name__ == "__main__":
    main()
