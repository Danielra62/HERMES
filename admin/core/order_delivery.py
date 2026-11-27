"""Despacho inmediato y reintentos de órdenes persistidas."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

from admin.core import clients, image_processing, network, orders
from shared.protocol import TipoOrden


TTL_MENSAJE_IMAGEN_SEGUNDOS = 8 * 60 * 60
TTL_FONDO_SEGUNDOS = 7 * 24 * 60 * 60
RETRASOS_REINTENTO_SEGUNDOS = (15, 60, 5 * 60, 15 * 60, 60 * 60)
MAX_INTENTOS = len(RETRASOS_REINTENTO_SEGUNDOS) + 1
INTERVALO_WORKER_SEGUNDOS = 1
MAX_ENTREGAS_POR_LOTE = 64
MAX_ENVIOS_REINTENTO = 32
TIMEOUT_INTENTO_SEGUNDOS = 10

_LOCK_WORKER = threading.Lock()
_LOCK_RECLAMAR = threading.Lock()
_LOCK_NOTIFICACIONES = threading.Lock()
_CLIENTES_NOTIFICANDO: set[str] = set()
_DETENER_WORKER = threading.Event()
_HILO_WORKER: threading.Thread | None = None


def _validar_backend() -> None:
    if clients._usar_mysql():
        raise RuntimeError(
            "La cola de órdenes requiere SQLite; la migración MySQL aún no está implementada"
        )


def _siguiente_reintento(intentos: int) -> str | None:
    if intentos >= MAX_INTENTOS:
        return None
    instante = datetime.now(timezone.utc) + timedelta(
        seconds=RETRASOS_REINTENTO_SEGUNDOS[intentos - 1]
    )
    return instante.isoformat(timespec="seconds").replace("+00:00", "Z")


def _payload_para_entrega(entrega: dict[str, Any]) -> tuple[TipoOrden, bytes]:
    tipo = entrega["tipo"]
    if tipo == "MENSAJE":
        payload = json.dumps(
            json.loads(entrega["payload"]),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return TipoOrden.MENSAJE, payload
    if tipo in {"IMAGEN", "CAMBIAR_FONDO"}:
        ruta = image_processing.buscar_imagen_comprimida(entrega["image_id"])
        if ruta is None:
            raise FileNotFoundError(
                f"No existe la imagen almacenada con image_id={entrega['image_id']}"
            )
        orden = (
            TipoOrden.IMAGEN if tipo == "IMAGEN" else TipoOrden.CAMBIAR_FONDO
        )
        return orden, ruta.read_bytes()
    raise ValueError(f"Tipo de orden persistida no soportado: {tipo}")


def _procesar_entrega(entrega: dict[str, Any]) -> dict[str, Any]:
    entrega_id = entrega["entrega_id"]
    intento_id = entrega["intento_id"]
    tipo = entrega["tipo"]
    try:
        tipo_protocolo, payload = _payload_para_entrega(entrega)
    except (OSError, ValueError, TypeError) as exc:
        estado = orders.completar_intento(
            entrega_id,
            intento_id,
            resultado="no_conecto",
            detalle=str(exc),
        )
        return {
            "ip": entrega["ip"],
            "ok": False,
            "error": str(exc),
            "estado": estado,
            "entrega_id": entrega_id,
        }

    resultado = network.enviar_orden_v2_a_uno(
        entrega["ip"],
        tipo_protocolo,
        payload,
        timeout_total=TIMEOUT_INTENTO_SEGUNDOS,
    )
    if resultado["ok"]:
        estado = orders.completar_intento(
            entrega_id,
            intento_id,
            resultado="confirmado",
            detalle=None,
        )
        return {
            **resultado,
            "estado": estado,
            "entrega_id": entrega_id,
        }

    incierto = bool(resultado["conectado"])
    proximo_intento = None
    if entrega["intentos"] < MAX_INTENTOS and (
        not incierto or tipo == "CAMBIAR_FONDO"
    ):
        proximo_intento = _siguiente_reintento(entrega["intentos"])
    estado = orders.completar_intento(
        entrega_id,
        intento_id,
        resultado="incierto" if incierto else "no_conecto",
        detalle=resultado["error"],
        proximo_intento_en=proximo_intento,
        incierto=incierto,
    )
    return {
        **resultado,
        "estado": estado,
        "entrega_id": entrega_id,
    }


def _procesar_lote(
    entregas: list[dict[str, Any]],
    *,
    max_workers: int | None = None,
) -> list[dict[str, Any]]:
    if not entregas:
        return []
    cantidad_hilos = max_workers or len(entregas)
    with ThreadPoolExecutor(max_workers=min(len(entregas), cantidad_hilos)) as executor:
        return list(executor.map(_procesar_entrega, entregas))


def procesar_entregas_pendientes(
    *,
    cliente_ip: str | None = None,
    entrega_ids: list[int] | None = None,
    limite: int = MAX_ENTREGAS_POR_LOTE,
) -> list[dict[str, Any]]:
    """Reclama y procesa entregas elegibles sin mantener abierta la transacción."""
    with _LOCK_RECLAMAR:
        orders.marcar_entregas_expiradas()
        entregas = orders.reclamar_entregas(
            limite=limite,
            cliente_ip=cliente_ip,
            entrega_ids=entrega_ids,
        )
    return _procesar_lote(entregas, max_workers=MAX_ENVIOS_REINTENTO)


def crear_y_entregar(
    *,
    tipo: str,
    payload: dict[str, Any],
    destino_tipo: str,
    destino_etiqueta: str | None,
    image_id: str | None = None,
) -> dict[str, Any]:
    """Persiste una orden y realiza un primer intento acotado de entrega."""
    _validar_backend()
    destinatarios = orders.obtener_destinatarios(destino_tipo, destino_etiqueta)
    if not destinatarios:
        return {
            "orden_id": None,
            "resultados": [],
            "destinatarios": 0,
            "destino_etiqueta": destino_etiqueta,
            "pendientes": 0,
            "inciertas": 0,
        }

    ttl = (
        TTL_FONDO_SEGUNDOS
        if tipo == "CAMBIAR_FONDO"
        else TTL_MENSAJE_IMAGEN_SEGUNDOS
    )
    with _LOCK_RECLAMAR:
        creada = orders.crear_orden(
            tipo,
            payload,
            destinatarios,
            destino_tipo=destino_tipo,
            destino_etiqueta=destino_etiqueta,
            ttl_segundos=ttl,
            image_id=image_id,
        )
        conexion_ids = orders.obtener_entregas_ids(creada["orden_id"])
        orders.marcar_entregas_expiradas()
        entregas = orders.reclamar_entregas(
            entrega_ids=conexion_ids,
            limite=len(conexion_ids),
        )
    resultados = _procesar_lote(entregas)
    conteos = orders.resumen_entregas(creada["orden_id"])
    return {
        "orden_id": creada["orden_id"],
        "resultados": resultados,
        "destinatarios": creada["total"],
        "destino_etiqueta": destino_etiqueta,
        "pendientes": conteos["pendientes"],
        "inciertas": conteos["inciertas"],
    }


def _trabajador(intervalo_segundos: float) -> None:
    while not _DETENER_WORKER.is_set():
        try:
            procesar_entregas_pendientes()
        except Exception as exc:
            print(f"[ORDERS][ERROR] No se pudo procesar la cola: {exc}")
        if _DETENER_WORKER.wait(intervalo_segundos):
            return


def iniciar_worker_ordenes(
    intervalo_segundos: float = INTERVALO_WORKER_SEGUNDOS,
) -> threading.Thread | None:
    """Recupera envíos interrumpidos y arranca un worker periódico único."""
    global _HILO_WORKER
    if intervalo_segundos <= 0:
        raise ValueError("El intervalo del worker debe ser mayor que cero")

    if clients._usar_mysql():
        print(
            "[ORDERS][WARN] Worker de cola deshabilitado: "
            "la persistencia de órdenes requiere SQLite"
        )
        return None

    with _LOCK_WORKER:
        if _HILO_WORKER is not None and _HILO_WORKER.is_alive():
            return _HILO_WORKER

        orders.recuperar_entregas_interrumpidas(
            MAX_INTENTOS,
            RETRASOS_REINTENTO_SEGUNDOS,
        )
        _DETENER_WORKER.clear()
        _HILO_WORKER = threading.Thread(
            target=_trabajador,
            args=(intervalo_segundos,),
            name="HermesOrderDeliveryWorker",
            daemon=True,
        )
        _HILO_WORKER.start()
        return _HILO_WORKER


def detener_worker_ordenes(timeout: float = 2) -> None:
    """Detiene el worker para pruebas y cierre ordenado."""
    global _HILO_WORKER
    _DETENER_WORKER.set()
    with _LOCK_WORKER:
        hilo = _HILO_WORKER
    if hilo is not None:
        hilo.join(timeout)
    with _LOCK_WORKER:
        if _HILO_WORKER is hilo and (hilo is None or not hilo.is_alive()):
            _HILO_WORKER = None


def notificar_cliente_disponible(ip: str) -> None:
    """Acelera y procesa las entregas pendientes tras heartbeat o sondeo."""
    with _LOCK_NOTIFICACIONES:
        if ip in _CLIENTES_NOTIFICANDO:
            return
        _CLIENTES_NOTIFICANDO.add(ip)

    def procesar() -> None:
        try:
            if orders.adelantar_reintentos_cliente(ip) == 0:
                return
            procesar_entregas_pendientes(cliente_ip=ip)
        except Exception as exc:
            print(f"[ORDERS][ERROR] No se pudo drenar la cola de {ip}: {exc}")
        finally:
            with _LOCK_NOTIFICACIONES:
                _CLIENTES_NOTIFICANDO.discard(ip)

    threading.Thread(
        target=procesar,
        name=f"HermesOrderDelivery-{ip}",
        daemon=True,
    ).start()


def respuesta_masiva(resultado: dict[str, Any]) -> dict[str, Any]:
    """Conserva el resumen de red y agrega el estado persistente de la orden."""
    resumen = network.resumen(resultado["resultados"])
    exitosos = resumen["exitosos"]
    total = resultado["destinatarios"]
    fallos = list(resumen["fallos"])
    ids_enviados = {fila["entrega_id"] for fila in resultado["resultados"]}
    no_intentados = total - len(ids_enviados)
    if no_intentados:
        fallos.append({
            "ip": "cola",
            "error": f"{no_intentados} entrega(s) guardada(s) para envío en segundo plano",
        })
    resumen.update({
        "total": total,
        "fallidos": total - exitosos,
        "fallos": fallos,
        "orden_id": resultado["orden_id"],
        "encoladas": resultado["pendientes"],
        "inciertas": resultado["inciertas"],
    })
    return resumen


def respuesta_individual(resultado: dict[str, Any]) -> dict[str, Any]:
    """Conserva el formato de un envío individual y añade sus conteos."""
    if resultado["resultados"]:
        respuesta = dict(resultado["resultados"][0])
    else:
        respuesta = {
            "ip": resultado["destino_etiqueta"],
            "ok": False,
            "error": "No hay destinatarios registrados",
        }
    respuesta.update({
        "orden_id": resultado["orden_id"],
        "encoladas": resultado["pendientes"],
        "inciertas": resultado["inciertas"],
    })
    return respuesta
