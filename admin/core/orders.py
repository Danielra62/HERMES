"""Persistencia de órdenes y entregas por cliente."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from admin.core import clients
from admin.core.image_processing import buscar_imagen_comprimida


TIPOS_ORDEN_VALIDOS = {"MENSAJE", "IMAGEN", "CAMBIAR_FONDO"}
DESTINOS_VALIDOS = {"equipo", "grupo", "todos"}
_IMAGE_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _timestamp_utc(valor: datetime) -> str:
    return valor.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _serializar_payload(payload: str | Mapping[str, Any]) -> str:
    if isinstance(payload, str):
        try:
            datos = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("El payload debe ser JSON válido") from exc
    elif isinstance(payload, Mapping):
        datos = dict(payload)
    else:
        raise TypeError("El payload debe ser un objeto JSON o texto JSON")

    try:
        return json.dumps(
            datos,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"El payload no se puede serializar como JSON: {exc}") from exc


def _normalizar_cliente_ids(cliente_ids: Sequence[int | Mapping[str, Any]]) -> list[int]:
    normalizados: list[int] = []
    ids_vistos = set()
    for destinatario in cliente_ids:
        try:
            cliente_id = int(
                destinatario["id"]
                if isinstance(destinatario, Mapping)
                else destinatario
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Cada destinatario debe tener un id válido") from exc
        if cliente_id <= 0:
            raise ValueError("El id del destinatario debe ser positivo")
        if cliente_id in ids_vistos:
            raise ValueError(f"Destinatario duplicado: cliente_id={cliente_id}")
        ids_vistos.add(cliente_id)
        normalizados.append(cliente_id)
    return normalizados


def crear_orden(
    tipo: str,
    payload: str | Mapping[str, Any],
    cliente_ids: Sequence[int | Mapping[str, Any]],
    *,
    destino_tipo: str,
    destino_etiqueta: str | None,
    ttl_segundos: int,
    image_id: str | None = None,
    ahora: datetime | None = None,
) -> dict[str, Any]:
    """Guarda la orden y congela una entrega por destinatario en una transacción.

    No realiza conexiones TCP. El envío inicial y el procesamiento de pendientes
    pertenecen a la siguiente fase de la cola.
    """
    tipo = tipo.upper()
    if tipo not in TIPOS_ORDEN_VALIDOS:
        raise ValueError(f"Tipo de orden no permitido: {tipo}")
    if destino_tipo not in DESTINOS_VALIDOS:
        raise ValueError(f"Tipo de destino no permitido: {destino_tipo}")
    if type(ttl_segundos) is not int or ttl_segundos < 0:
        raise ValueError("ttl_segundos debe ser un entero no negativo")

    if tipo in {"IMAGEN", "CAMBIAR_FONDO"}:
        if not isinstance(image_id, str) or not _IMAGE_ID_RE.fullmatch(image_id):
            raise ValueError("IMAGEN y CAMBIAR_FONDO requieren un image_id válido")
        if buscar_imagen_comprimida(image_id) is None:
            raise ValueError(f"No existe la imagen almacenada con image_id={image_id}")
    elif image_id is not None:
        raise ValueError("MENSAJE no admite image_id")
    if destino_etiqueta is not None and not isinstance(destino_etiqueta, str):
        raise TypeError("destino_etiqueta debe ser texto o None")

    datos_payload = _serializar_payload(payload)
    destinatarios = _normalizar_cliente_ids(cliente_ids)
    if not destinatarios:
        raise ValueError("No se puede registrar una orden sin destinatarios")

    instante = ahora or datetime.now(timezone.utc)
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError("ahora debe incluir zona horaria")
    creada_en = _timestamp_utc(instante)
    expira_en = _timestamp_utc(instante + timedelta(seconds=ttl_segundos))

    conexion = clients._conexion()
    cursor = None
    try:
        cursor = clients._cursor(conexion, dictionary=True)
        if isinstance(conexion, sqlite3.Connection):
            cursor.execute("BEGIN IMMEDIATE")
        else:
            conexion.start_transaction()

        marcadores = ", ".join("?" for _ in destinatarios)
        cursor.execute(
            f"""
            SELECT id, nombre, ip
            FROM clientes
            WHERE id IN ({marcadores})
            """,
            tuple(destinatarios),
        )
        clientes_por_id = {
            int(fila["id"]): {
                "nombre": fila["nombre"],
                "ip": fila["ip"],
            }
            for fila in cursor.fetchall()
        }
        no_encontrados = set(destinatarios) - clientes_por_id.keys()
        if no_encontrados:
            raise ValueError(
                "No existen los clientes destinatarios: "
                + ", ".join(str(cliente_id) for cliente_id in sorted(no_encontrados))
            )

        cursor.execute(
            """
            INSERT INTO ordenes (
                tipo, payload, image_id, destino_tipo, destino_etiqueta,
                creada_en, expira_en
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tipo,
                datos_payload,
                image_id,
                destino_tipo,
                destino_etiqueta,
                creada_en,
                expira_en,
            ),
        )
        orden_id = cursor.lastrowid

        for cliente_id in destinatarios:
            cliente = clientes_por_id[cliente_id]
            cursor.execute(
                """
                INSERT INTO entregas (
                    orden_id, cliente_id, nombre_snapshot, ip_snapshot
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    orden_id,
                    cliente_id,
                    cliente["nombre"],
                    cliente["ip"],
                ),
            )

        if tipo == "CAMBIAR_FONDO":
            cursor.execute(
                """
                UPDATE entregas
                SET estado = 'cancelada',
                    detalle = 'Reemplazada por una orden de fondo más reciente'
                WHERE cliente_id IN (
                    SELECT cliente_id
                    FROM entregas
                    WHERE orden_id = ?
                )
                  AND estado = 'pendiente'
                  AND orden_id <> ?
                  AND orden_id IN (
                    SELECT id FROM ordenes WHERE tipo = 'CAMBIAR_FONDO'
                  )
                """,
                (orden_id, orden_id),
            )

        conexion.commit()
        return {
            "orden_id": orden_id,
            "total": len(destinatarios),
            "creada_en": creada_en,
            "expira_en": expira_en,
        }
    except Exception:
        conexion.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if not clients._cerrada(conexion):
            conexion.close()


def obtener_destinatarios(
    destino_tipo: str,
    destino_etiqueta: str | None,
) -> list[dict[str, Any]]:
    """Resuelve los clientes registrados que quedan congelados en una orden."""
    conexion = clients._conexion()
    cursor = None
    try:
        cursor = clients._cursor(conexion, dictionary=True)
        if destino_tipo == "todos":
            cursor.execute(
                "SELECT id, nombre, ip FROM clientes ORDER BY id"
            )
        elif destino_tipo == "grupo":
            cursor.execute(
                """
                SELECT c.id, c.nombre, c.ip
                FROM clientes AS c
                JOIN grupos AS g ON g.id = c.grupo_id
                WHERE g.nombre = ?
                ORDER BY c.id
                """,
                (destino_etiqueta,),
            )
        elif destino_tipo == "equipo":
            cursor.execute(
                "SELECT id, nombre, ip FROM clientes WHERE ip = ?",
                (destino_etiqueta,),
            )
        else:
            raise ValueError(f"Tipo de destino no permitido: {destino_tipo}")
        return [
            {"id": int(fila["id"]), "nombre": fila["nombre"], "ip": fila["ip"]}
            for fila in cursor.fetchall()
        ]
    finally:
        if cursor is not None:
            cursor.close()
        if not clients._cerrada(conexion):
            conexion.close()


def obtener_entregas_ids(orden_id: int) -> list[int]:
    """Devuelve los IDs de entrega de una orden recién creada."""
    conexion = clients._conexion()
    cursor = None
    try:
        cursor = clients._cursor(conexion, dictionary=True)
        cursor.execute(
            "SELECT id FROM entregas WHERE orden_id = ? ORDER BY id",
            (orden_id,),
        )
        return [int(fila["id"]) for fila in cursor.fetchall()]
    finally:
        if cursor is not None:
            cursor.close()
        if not clients._cerrada(conexion):
            conexion.close()


def reclamar_entregas(
    *,
    limite: int,
    cliente_ip: str | None = None,
    entrega_ids: Sequence[int] | None = None,
) -> list[dict[str, Any]]:
    """Marca entregas vencidas para envío y registra un intento antes de la red."""
    if type(limite) is not int or limite < 1:
        raise ValueError("limite debe ser un entero positivo")
    if entrega_ids is not None and not entrega_ids:
        return []

    ahora = _timestamp_utc(datetime.now(timezone.utc))
    conexion = clients._conexion()
    cursor = None
    reclamadas: list[dict[str, Any]] = []
    try:
        cursor = clients._cursor(conexion, dictionary=True)
        if isinstance(conexion, sqlite3.Connection):
            cursor.execute("BEGIN IMMEDIATE")
        else:
            conexion.start_transaction()

        condiciones = [
            "e.estado = 'pendiente'",
            "o.expira_en > ?",
            "(e.proximo_intento_en IS NULL OR e.proximo_intento_en <= ?)",
        ]
        parametros: list[Any] = [ahora, ahora]
        if cliente_ip is not None:
            condiciones.append("c.ip = ?")
            parametros.append(cliente_ip)
        if entrega_ids is not None:
            marcadores = ", ".join("?" for _ in entrega_ids)
            condiciones.append(f"e.id IN ({marcadores})")
            parametros.extend(entrega_ids)
        parametros.append(limite)

        cursor.execute(
            f"""
            SELECT e.id
            FROM entregas AS e
            JOIN ordenes AS o ON o.id = e.orden_id
            JOIN clientes AS c ON c.id = e.cliente_id
            WHERE {" AND ".join(condiciones)}
            ORDER BY e.id
            LIMIT ?
            """,
            tuple(parametros),
        )
        ids = [int(fila["id"]) for fila in cursor.fetchall()]

        for entrega_id in ids:
            cursor.execute(
                """
                UPDATE entregas
                SET estado = 'enviando',
                    intentos = intentos + 1,
                    proximo_intento_en = NULL,
                    ultimo_intento_en = ?
                WHERE id = ? AND estado = 'pendiente'
                """,
                (ahora, entrega_id),
            )
            if cursor.rowcount != 1:
                continue
            cursor.execute(
                """
                SELECT e.id AS entrega_id, e.intentos, e.resultado_incierto,
                       o.tipo, o.payload, o.image_id, c.ip AS ip_actual
                FROM entregas AS e
                JOIN ordenes AS o ON o.id = e.orden_id
                JOIN clientes AS c ON c.id = e.cliente_id
                WHERE e.id = ?
                """,
                (entrega_id,),
            )
            fila = cursor.fetchone()
            cursor.execute(
                """
                INSERT INTO intentos (entrega_id, iniciado_en)
                VALUES (?, ?)
                """,
                (entrega_id, ahora),
            )
            reclamadas.append({
                "entrega_id": entrega_id,
                "intento_id": int(cursor.lastrowid),
                "intentos": int(fila["intentos"]),
                "resultado_incierto": bool(fila["resultado_incierto"]),
                "tipo": fila["tipo"],
                "payload": fila["payload"],
                "image_id": fila["image_id"],
                "ip": fila["ip_actual"],
            })

        conexion.commit()
        return reclamadas
    except Exception:
        conexion.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if not clients._cerrada(conexion):
            conexion.close()


def completar_intento(
    entrega_id: int,
    intento_id: int,
    *,
    resultado: str,
    detalle: str | None,
    proximo_intento_en: str | None = None,
    incierto: bool = False,
) -> str:
    """Confirma el resultado de red y transiciona la entrega atómicamente."""
    if resultado not in {"confirmado", "no_conecto", "incierto", "interrumpido"}:
        raise ValueError(f"Resultado de intento no permitido: {resultado}")

    ahora_dt = datetime.now(timezone.utc)
    ahora = _timestamp_utc(ahora_dt)
    conexion = clients._conexion()
    cursor = None
    try:
        cursor = clients._cursor(conexion, dictionary=True)
        if isinstance(conexion, sqlite3.Connection):
            cursor.execute("BEGIN IMMEDIATE")
        else:
            conexion.start_transaction()

        cursor.execute(
            """
            SELECT o.expira_en, e.resultado_incierto
            FROM entregas AS e
            JOIN ordenes AS o ON o.id = e.orden_id
            WHERE e.id = ? AND e.estado = 'enviando'
            """,
            (entrega_id,),
        )
        fila = cursor.fetchone()
        if fila is None:
            raise ValueError(f"La entrega {entrega_id} ya no está en envío")

        if resultado == "confirmado":
            estado = "confirmada"
            confirmada_en = ahora
            incierto_final = 0
            proximo_intento_en = None
        elif fila["expira_en"] <= ahora:
            estado = "expirada"
            confirmada_en = None
            incierto_final = int(bool(fila["resultado_incierto"]) or incierto)
            proximo_intento_en = None
        elif proximo_intento_en is not None:
            estado = "pendiente"
            confirmada_en = None
            incierto_final = int(bool(fila["resultado_incierto"]) or incierto)
        else:
            estado = "fallida"
            confirmada_en = None
            incierto_final = int(bool(fila["resultado_incierto"]) or incierto)

        cursor.execute(
            """
            UPDATE intentos
            SET terminado_en = ?, resultado = ?, detalle = ?
            WHERE id = ? AND entrega_id = ? AND terminado_en IS NULL
            """,
            (ahora, resultado, detalle, intento_id, entrega_id),
        )
        if cursor.rowcount != 1:
            raise ValueError(f"El intento {intento_id} ya fue finalizado")
        cursor.execute(
            """
            UPDATE entregas
            SET estado = ?, detalle = ?, resultado_incierto = ?,
                proximo_intento_en = ?, confirmada_en = ?
            WHERE id = ?
            """,
            (
                estado,
                detalle,
                incierto_final,
                proximo_intento_en,
                confirmada_en,
                entrega_id,
            ),
        )
        conexion.commit()
        return estado
    except Exception:
        conexion.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if not clients._cerrada(conexion):
            conexion.close()


def marcar_entregas_expiradas() -> int:
    """Cierra entregas pendientes cuyo TTL ya venció."""
    ahora = _timestamp_utc(datetime.now(timezone.utc))
    conexion = clients._conexion()
    cursor = None
    try:
        cursor = clients._cursor(conexion, dictionary=True)
        cursor.execute(
            """
            UPDATE entregas
            SET estado = 'expirada',
                detalle = 'La orden expiró antes de ser entregada'
            WHERE estado = 'pendiente'
              AND orden_id IN (
                  SELECT id FROM ordenes WHERE expira_en <= ?
              )
            """,
            (ahora,),
        )
        cantidad = cursor.rowcount
        conexion.commit()
        return cantidad
    except Exception:
        conexion.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if not clients._cerrada(conexion):
            conexion.close()


def resumen_entregas(orden_id: int) -> dict[str, int]:
    """Cuenta entregas pendientes e inciertas de una orden."""
    conexion = clients._conexion()
    cursor = None
    try:
        cursor = clients._cursor(conexion, dictionary=True)
        cursor.execute(
            """
            SELECT
                SUM(CASE WHEN estado IN ('pendiente', 'enviando') THEN 1 ELSE 0 END)
                    AS pendientes,
                SUM(CASE WHEN resultado_incierto = 1 THEN 1 ELSE 0 END) AS inciertas
            FROM entregas
            WHERE orden_id = ?
            """,
            (orden_id,),
        )
        fila = cursor.fetchone()
        return {
            "pendientes": int(fila["pendientes"] or 0),
            "inciertas": int(fila["inciertas"] or 0),
        }
    finally:
        if cursor is not None:
            cursor.close()
        if not clients._cerrada(conexion):
            conexion.close()


def adelantar_reintentos_cliente(cliente_ip: str) -> int:
    """Hace inmediatamente elegibles las entregas pendientes de un cliente."""
    conexion = clients._conexion()
    cursor = None
    try:
        cursor = clients._cursor(conexion, dictionary=True)
        cursor.execute(
            """
            UPDATE entregas
            SET proximo_intento_en = NULL
            WHERE estado = 'pendiente'
              AND cliente_id IN (
                  SELECT id FROM clientes WHERE ip = ?
              )
            """,
            (cliente_ip,),
        )
        cantidad = cursor.rowcount
        conexion.commit()
        return cantidad
    except Exception:
        conexion.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if not clients._cerrada(conexion):
            conexion.close()


def recuperar_entregas_interrumpidas(
    max_intentos: int,
    retrasos_reintento_segundos: Sequence[int],
) -> int:
    """Recupera entregas que quedaron en envío al detenerse el proceso."""
    if len(retrasos_reintento_segundos) < max_intentos - 1:
        raise ValueError("Faltan retrasos para la política de reintentos")

    ahora_dt = datetime.now(timezone.utc)
    ahora = _timestamp_utc(ahora_dt)
    conexion = clients._conexion()
    cursor = None
    try:
        cursor = clients._cursor(conexion, dictionary=True)
        if isinstance(conexion, sqlite3.Connection):
            cursor.execute("BEGIN IMMEDIATE")
        else:
            conexion.start_transaction()
        cursor.execute(
            """
            SELECT e.id, e.intentos, o.tipo, o.expira_en
            FROM entregas AS e
            JOIN ordenes AS o ON o.id = e.orden_id
            WHERE e.estado = 'enviando'
            """
        )
        filas = cursor.fetchall()
        for fila in filas:
            expirada = fila["expira_en"] <= ahora
            puede_reintentar_fondo = (
                not expirada
                and fila["tipo"] == "CAMBIAR_FONDO"
                and int(fila["intentos"]) < max_intentos
            )
            estado = (
                "expirada"
                if expirada
                else "pendiente" if puede_reintentar_fondo else "fallida"
            )
            proximo = (
                _timestamp_utc(
                    ahora_dt
                    + timedelta(
                        seconds=retrasos_reintento_segundos[
                            int(fila["intentos"]) - 1
                        ]
                    )
                )
                if puede_reintentar_fondo
                else None
            )
            detalle = "Proceso interrumpido durante el envío; resultado incierto"
            cursor.execute(
                """
                UPDATE intentos
                SET terminado_en = ?, resultado = 'interrumpido', detalle = ?
                WHERE entrega_id = ? AND terminado_en IS NULL
                """,
                (ahora, detalle, fila["id"]),
            )
            cursor.execute(
                """
                UPDATE entregas
                SET estado = ?, resultado_incierto = 1,
                    proximo_intento_en = ?, detalle = ?
                WHERE id = ? AND estado = 'enviando'
                """,
                (estado, proximo, detalle, fila["id"]),
            )
        conexion.commit()
        return len(filas)
    except Exception:
        conexion.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if not clients._cerrada(conexion):
            conexion.close()
