"""Funciones compartidas de framing para el protocolo TCP v2 de HERMES."""

import socket
import struct
from enum import IntEnum


# Version del formato binario del header; es independiente del apodo "v2"
# usado por el equipo para esta migracion general del protocolo del proyecto.
VERSION_PROTOCOLO = 1
FORMATO_HEADER = "!BBII"
TAMANO_HEADER = struct.calcsize(FORMATO_HEADER)
MAX_PAYLOAD_BYTES = 32 * 1024 * 1024


class TipoOrden(IntEnum):
    """Codigos numericos de los tipos de orden del protocolo."""

    MENSAJE = 1
    CAMBIAR_FONDO = 2
    IMAGEN = 3
    HEARTBEAT = 4


def empacar_header(
    version: int,
    tipo_orden: int,
    order_id: int,
    longitud_payload: int,
) -> bytes:
    """Empaqueta los campos del header en su representacion binaria fija."""
    return struct.pack(
        FORMATO_HEADER,
        version,
        tipo_orden,
        order_id,
        longitud_payload,
    )


def desempacar_header(datos: bytes) -> tuple[int, int, int, int]:
    """Desempaqueta un header y devuelve version, tipo, ID y longitud."""
    if len(datos) != TAMANO_HEADER:
        raise ValueError(
            f"El header debe medir {TAMANO_HEADER} bytes; se recibieron {len(datos)}"
        )
    return struct.unpack(FORMATO_HEADER, datos)


def recv_exact(sock: socket.socket, n: int) -> bytes:
    """Lee exactamente n bytes o lanza ConnectionError si se cierra el socket."""
    if n < 0:
        raise ValueError("La cantidad de bytes no puede ser negativa")

    datos = bytearray()
    while len(datos) < n:
        bloque = sock.recv(n - len(datos))
        if not bloque:
            raise ConnectionError(
                f"Conexion cerrada antes de completar la lectura: "
                f"se esperaban {n} bytes y se recibieron {len(datos)}"
            )
        datos.extend(bloque)
    return bytes(datos)


def recibir_orden(sock: socket.socket) -> tuple[int, int, bytes]:
    """Recibe una orden y devuelve su tipo, ID y payload binario."""
    datos_header = recv_exact(sock, TAMANO_HEADER)
    version, tipo_orden, order_id, longitud_payload = desempacar_header(datos_header)
    if version != VERSION_PROTOCOLO:
        raise ValueError(f"Version de protocolo no soportada: {version}")
    if longitud_payload > MAX_PAYLOAD_BYTES:
        raise ValueError(
            f"El payload excede el maximo de {MAX_PAYLOAD_BYTES} bytes: "
            f"{longitud_payload}"
        )
    payload = recv_exact(sock, longitud_payload)
    return tipo_orden, order_id, payload


def enviar_orden(
    sock: socket.socket,
    tipo_orden: int,
    order_id: int,
    payload: bytes,
) -> None:
    """Envia el header v2 y el payload completo por el socket."""
    header = empacar_header(
        VERSION_PROTOCOLO,
        tipo_orden,
        order_id,
        len(payload),
    )
    sock.sendall(header)
    if payload:
        sock.sendall(payload)
