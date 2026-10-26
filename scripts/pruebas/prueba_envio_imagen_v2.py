"""Envía una imagen real al cliente HERMES por TCP v2.

Uso desde la raíz del proyecto:
    python -m scripts.pruebas.prueba_envio_imagen_v2 --tipo imagen --archivo "C:\\ruta\\foto.jpg"
    python -m scripts.pruebas.prueba_envio_imagen_v2 --tipo fondo --archivo "C:\\ruta\\foto.jpg"
"""

import argparse
import os
import secrets
import socket
import time

from PIL import Image

from shared.constants import PUERTO
from shared.protocol import TipoOrden, VERSION_PROTOCOLO, empacar_header, recv_exact


def validar_archivo(ruta: str) -> None:
    with Image.open(ruta) as imagen:
        imagen.verify()
    with Image.open(ruta) as imagen:
        imagen.load()


def enviar_imagen(
    host: str,
    puerto: int,
    tipo: str,
    ruta_archivo: str,
) -> int:
    validar_archivo(ruta_archivo)
    order_id = secrets.randbits(32)
    tipo_orden = (
        TipoOrden.IMAGEN if tipo == "imagen" else TipoOrden.CAMBIAR_FONDO
    )
    longitud = os.path.getsize(ruta_archivo)
    header = empacar_header(
        VERSION_PROTOCOLO,
        tipo_orden,
        order_id,
        longitud,
    )

    with socket.create_connection((host, puerto), timeout=30) as sock:
        sock.settimeout(30)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        for inicio in range(0, len(header), 2):
            sock.sendall(header[inicio:inicio + 2])
            time.sleep(0.002)

        with open(ruta_archivo, "rb") as archivo:
            while bloque := archivo.read(8192):
                sock.sendall(bloque)

        ack = recv_exact(sock, 2)
        if ack != b"OK":
            raise RuntimeError(f"ACK inesperado: {ack!r}")

    print(
        f"OK order_id={order_id}; tipo={tipo}; bytes={longitud}; "
        f"archivo={ruta_archivo}"
    )
    return order_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=PUERTO)
    parser.add_argument("--tipo", choices=("imagen", "fondo"), required=True)
    parser.add_argument("--archivo", required=True, help="Ruta a una imagen real")
    args = parser.parse_args()

    enviar_imagen(args.host, args.port, args.tipo, args.archivo)


if __name__ == "__main__":
    main()
