import json
import socket
import threading
from shared.constants import PUERTO, CMD_CAMBIAR_FONDO, CMD_MENSAJE
from shared.protocol import VERSION_PROTOCOLO, TipoOrden, recibir_orden

from cliente.core.wallpaper import cambiar_fondo
from cliente.core.messaging import mostrar_mensaje

HOST = "0.0.0.0"

def manejar_comando(data):
    print(f"[CMD] {data}")

    if data == CMD_CAMBIAR_FONDO:
        cambiar_fondo()

    elif data.startswith(CMD_MENSAJE):
        try:
            _, titulo, texto, icono = data.split("|")
            mostrar_mensaje(titulo, texto, icono)
        except Exception as e:
            print("[ERROR] Formato de mensaje inválido:", e)


def manejar_orden_v2(tipo_orden, payload) -> tuple[str, str, str]:
    """Valida y extrae los campos de una orden MENSAJE v2."""
    if tipo_orden != TipoOrden.MENSAJE:
        raise ValueError(f"Tipo de orden v2 no soportado: {tipo_orden}")

    mensaje = json.loads(payload.decode("utf-8"))
    titulo = mensaje["titulo"]
    texto = mensaje["texto"]
    icono = mensaje["icono"]
    print(f"[CMD v2] MENSAJE: {titulo}")
    return titulo, texto, icono


def _manejar_conexion(conn):
    try:
        primer_byte = conn.recv(1, socket.MSG_PEEK)
        if primer_byte == bytes([VERSION_PROTOCOLO]):
            tipo_orden, order_id, payload = recibir_orden(conn)
            print(f"[ORDEN v2] id={order_id}")
            titulo, texto, icono = manejar_orden_v2(tipo_orden, payload)
            conn.sendall(b"OK")
            threading.Thread(
                target=mostrar_mensaje,
                args=(titulo, texto, icono),
                daemon=True,
            ).start()
        else:
            data = conn.recv(1024).decode().strip()
            if data:
                manejar_comando(data)
                conn.sendall("OK".encode("utf-8"))
    except Exception as e:
        print("[ERROR] leyendo datos:", e)
    finally:
        conn.close()


def iniciar_listener():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PUERTO))
    server.listen()

    print(f"[LISTENER] Escuchando en {HOST}:{PUERTO}")

    while True:
        conn, addr = server.accept()
        print(f"[CONEXION] {addr}")

        threading.Thread(
            target=_manejar_conexion,
            args=(conn,),
            daemon=True,
        ).start()
