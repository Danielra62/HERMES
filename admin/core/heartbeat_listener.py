"""Listener TCP v2 para actualizar la disponibilidad de clientes."""

import socket
import threading

from admin.core import clients
from shared.constants import PUERTO_HEARTBEAT, TIMEOUT
from shared.protocol import TipoOrden, recibir_orden


HOST = "0.0.0.0"
_LOCK_INICIO = threading.Lock()
_SERVIDOR: socket.socket | None = None
_HILO: threading.Thread | None = None


def _atender_conexion(conn: socket.socket, direccion: tuple[str, int]) -> None:
    ip = direccion[0]
    try:
        conn.settimeout(TIMEOUT)
        tipo_orden, order_id, payload = recibir_orden(conn)
        if tipo_orden != TipoOrden.HEARTBEAT:
            raise ValueError(f"Tipo de orden no permitido en heartbeat: {tipo_orden}")
        if payload:
            raise ValueError("El payload de HEARTBEAT debe estar vacío")

        resultado = clients.actualizar_disponibilidad_cliente(ip)
        if not resultado["ok"]:
            print(f"[HEARTBEAT][ERROR] {ip}: {resultado['error']}")
            conn.sendall(b"ER")
            return
        if not resultado["actualizado"]:
            print(f"[HEARTBEAT] IP no registrada; se ignora: {ip}")
        else:
            print(f"[HEARTBEAT] Cliente disponible: {ip} (order_id={order_id})")
        conn.sendall(b"OK")
    except (ConnectionError, OSError, ValueError, KeyError) as exc:
        print(f"[HEARTBEAT][ERROR] Conexión de {ip}: {exc}")
        try:
            conn.sendall(b"ER")
        except OSError:
            pass
    finally:
        conn.close()


def _aceptar_conexiones(servidor: socket.socket) -> None:
    while True:
        try:
            conn, direccion = servidor.accept()
        except OSError as exc:
            print(f"[HEARTBEAT][ERROR] Listener detenido: {exc}")
            return

        threading.Thread(
            target=_atender_conexion,
            args=(conn, direccion),
            name=f"HermesHeartbeat-{direccion[0]}",
            daemon=True,
        ).start()


def iniciar_listener_heartbeat() -> threading.Thread:
    """Inicia el listener una sola vez y retorna su hilo daemon."""
    global _SERVIDOR, _HILO

    with _LOCK_INICIO:
        if _HILO is not None and _HILO.is_alive():
            return _HILO

        servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            servidor.bind((HOST, PUERTO_HEARTBEAT))
            servidor.listen()
        except OSError:
            servidor.close()
            raise

        hilo = threading.Thread(
            target=_aceptar_conexiones,
            args=(servidor,),
            name="HermesHeartbeatListener",
            daemon=True,
        )
        _SERVIDOR = servidor
        _HILO = hilo
        hilo.start()
        print(
            f"[HEARTBEAT] Escuchando en {HOST}:{PUERTO_HEARTBEAT} "
            "(TCP v2)"
        )
        return hilo
