"""Sondeo periódico de clientes no disponibles."""

import socket
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from admin.core import clients
from shared.constants import PUERTO, TIMEOUT
from shared.protocol import TipoOrden, enviar_orden, recv_exact


INTERVALO_SONDEO_SEGUNDOS = 30 * 60
_LOCK_INICIO = threading.Lock()
_DETENER = threading.Event()
_HILO: threading.Thread | None = None


def _sondear_cliente(ip: str) -> bool:
    """Consulta un cliente con un HEARTBEAT v2 por el puerto de órdenes."""
    try:
        with socket.create_connection((ip, PUERTO), timeout=TIMEOUT) as sock:
            sock.settimeout(TIMEOUT)
            enviar_orden(sock, TipoOrden.HEARTBEAT, 0, b"")
            respuesta = recv_exact(sock, 2)
            if respuesta != b"OK":
                raise ConnectionError(f"ACK inesperado: {respuesta!r}")
    except (OSError, ConnectionError, ValueError) as exc:
        print(f"[SCHEDULER][WARN] {ip} no respondió al sondeo: {exc}")
        return False

    resultado = clients.actualizar_disponibilidad_cliente(ip)
    if not resultado["ok"]:
        print(f"[SCHEDULER][ERROR] {ip}: {resultado['error']}")
        return False
    if not resultado["actualizado"]:
        print(f"[SCHEDULER] {ip} ya no está registrado")
        return False

    print(f"[SCHEDULER] Cliente disponible: {ip}")
    return True


def sondear_clientes_no_disponibles() -> dict[str, int]:
    """Sondea en paralelo los clientes no disponibles y devuelve el resumen."""
    ips = clients.obtener_clientes_no_disponibles()
    if not ips:
        print("[SCHEDULER] No hay clientes no disponibles para sondear")
        return {"total": 0, "disponibles": 0, "fallidos": 0}

    disponibles = 0
    with ThreadPoolExecutor(max_workers=min(len(ips), 32)) as executor:
        tareas = [executor.submit(_sondear_cliente, ip) for ip in ips]
        for tarea in as_completed(tareas):
            if tarea.result():
                disponibles += 1

    resumen = {
        "total": len(ips),
        "disponibles": disponibles,
        "fallidos": len(ips) - disponibles,
    }
    print(f"[SCHEDULER] Resultado del sondeo: {resumen}")
    return resumen


def _ejecutar_periodicamente(intervalo_segundos: float) -> None:
    while not _DETENER.is_set():
        try:
            sondear_clientes_no_disponibles()
        except Exception as exc:
            print(f"[SCHEDULER][ERROR] No se pudo completar el sondeo: {exc}")
        if _DETENER.wait(intervalo_segundos):
            return


def iniciar_scheduler(
    intervalo_segundos: float = INTERVALO_SONDEO_SEGUNDOS,
) -> threading.Thread:
    """Inicia un único scheduler daemon, con primer sondeo inmediato."""
    global _HILO
    if intervalo_segundos <= 0:
        raise ValueError("El intervalo del sondeo debe ser mayor que cero")

    with _LOCK_INICIO:
        if _HILO is not None and _HILO.is_alive():
            return _HILO

        _DETENER.clear()
        _HILO = threading.Thread(
            target=_ejecutar_periodicamente,
            args=(intervalo_segundos,),
            name="HermesAvailabilityScheduler",
            daemon=True,
        )
        _HILO.start()
        print(
            "[SCHEDULER] Sondeo de disponibilidad iniciado "
            f"(intervalo: {intervalo_segundos:g} s)"
        )
        return _HILO


def detener_scheduler(timeout: float = 2) -> None:
    """Detiene el scheduler; útil para el cierre limpio y pruebas."""
    global _HILO
    _DETENER.set()
    with _LOCK_INICIO:
        hilo = _HILO
    if hilo is not None:
        hilo.join(timeout)
    with _LOCK_INICIO:
        if _HILO is hilo and (hilo is None or not hilo.is_alive()):
            _HILO = None
