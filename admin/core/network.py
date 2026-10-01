# =============================================================
#  HERMES — admin/core/network.py
#  Envío de órdenes por socket TCP a los clientes
# =============================================================

import socket
import threading
from admin.core.clients import obtener_clientes
from shared.constants import PUERTO, TIMEOUT
from shared.protocol import enviar_orden


_order_id = 0
_order_id_lock = threading.Lock()


def _siguiente_order_id() -> int:
    """Genera un identificador de orden de 32 bits seguro entre hilos."""
    global _order_id
    with _order_id_lock:
        _order_id = (_order_id + 1) & 0xFFFFFFFF
        return _order_id


def _enviar_a_uno(ip: str, orden: str) -> dict:
    """
    Envía una orden a una sola PC y retorna el resultado.
    Retorna {"ip": ip, "ok": True, "respuesta": "..."}
          o {"ip": ip, "ok": False, "error": "..."}
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(TIMEOUT)
            s.connect((ip, PUERTO))
            s.sendall(orden.encode("utf-8"))
            respuesta = s.recv(1024).decode("utf-8")
            return {"ip": ip, "ok": True, "respuesta": respuesta}

    except socket.timeout:
        return {"ip": ip, "ok": False, "error": "TIMEOUT — PC apagada o inaccesible"}
    except ConnectionRefusedError:
        return {"ip": ip, "ok": False, "error": "RECHAZADO — cliente no activo"}
    except OSError as e:
        return {"ip": ip, "ok": False, "error": str(e)}


def _enviar_v2_a_uno(ip: str, tipo_orden: int, payload: bytes) -> dict:
    """Envía una orden con framing v2 a una sola PC."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(TIMEOUT)
            s.connect((ip, PUERTO))
            enviar_orden(s, tipo_orden, _siguiente_order_id(), payload)
            respuesta = s.recv(1024).decode("utf-8")
            return {"ip": ip, "ok": True, "respuesta": respuesta}

    except socket.timeout:
        return {"ip": ip, "ok": False, "error": "TIMEOUT — PC apagada o inaccesible"}
    except ConnectionRefusedError:
        return {"ip": ip, "ok": False, "error": "RECHAZADO — cliente no activo"}
    except OSError as e:
        return {"ip": ip, "ok": False, "error": str(e)}


def _enviar_v2_a_lista(tipo_orden: int, payload: bytes, ips: list[str]) -> list[dict]:
    """Envía una orden v2 en paralelo a una lista de IPs."""
    if not ips:
        return []

    resultados = [None] * len(ips)

    def tarea(index, ip):
        resultados[index] = _enviar_v2_a_uno(ip, tipo_orden, payload)

    hilos = [
        threading.Thread(target=tarea, args=(index, ip), daemon=True)
        for index, ip in enumerate(ips)
    ]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()
    return resultados


def enviar_v2_a_todos(tipo_orden: int, payload: bytes) -> list[dict]:
    """Envía una orden v2 a todos los clientes registrados."""
    return _enviar_v2_a_lista(tipo_orden, payload, obtener_clientes())


def enviar_v2_a_uno(ip: str, tipo_orden: int, payload: bytes) -> dict:
    """Envía una orden v2 a una PC específica."""
    return _enviar_v2_a_uno(ip, tipo_orden, payload)


def enviar_v2_a_lista(
    tipo_orden: int,
    payload: bytes,
    ips: list[str],
) -> list[dict]:
    """Envía una orden v2 a una lista específica de IPs."""
    return _enviar_v2_a_lista(tipo_orden, payload, ips)


def enviar_a_todos(orden: str) -> list[dict]:
    """
    Envía una orden a todas las PCs registradas en clientes.json.
    Usa hilos para enviar en paralelo y no esperar PC por PC.
    Retorna una lista con el resultado de cada PC.
    """
    clientes = obtener_clientes()

    if not clientes:
        return []

    resultados = [None] * len(clientes)

    def tarea(index, ip):
        resultados[index] = _enviar_a_uno(ip, orden)

    hilos = []
    for i, ip in enumerate(clientes):
        t = threading.Thread(target=tarea, args=(i, ip), daemon=True)
        hilos.append(t)
        t.start()

    for t in hilos:
        t.join()

    return resultados


def enviar_a_uno(ip: str, orden: str) -> dict:
    """
    Envía una orden a una sola PC específica.
    Retorna el resultado de esa PC.
    """
    return _enviar_a_uno(ip, orden)


def resumen(resultados: list[dict]) -> dict:
    """
    Recibe la lista de resultados de enviar_a_todos()
    y retorna un resumen con conteo de éxitos y fallos.

    Ejemplo de retorno:
    {
        "total":   60,
        "exitosos": 55,
        "fallidos": 5,
        "fallos": [
            {"ip": "172.16.20.45", "error": "TIMEOUT ..."},
            ...
        ]
    }
    """
    exitosos = [r for r in resultados if r and r["ok"]]
    fallidos = [r for r in resultados if r and not r["ok"]]

    return {
        "total":    len(resultados),
        "exitosos": len(exitosos),
        "fallidos": len(fallidos),
        "fallos":   [{"ip": r["ip"], "error": r["error"]} for r in fallidos]
    }

def enviar_a_lista(orden: str, ips: list[str]) -> list[dict]:
    """
    Envía una orden a una lista específica de IPs (en paralelo).
    Útil para enviar a un grupo o a un subconjunto de clientes.
    """
    if not ips:
        return []

    resultados = [None] * len(ips)

    def tarea(index, ip):
        resultados[index] = _enviar_a_uno(ip, orden)

    hilos = [threading.Thread(target=tarea, args=(i, ip), daemon=True) for i, ip in enumerate(ips)]
    for t in hilos: t.start()
    for t in hilos: t.join()

    return resultados