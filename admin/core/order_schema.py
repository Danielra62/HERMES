"""Migraciones del esquema persistente de órdenes para SQLite."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


VERSION_ESQUEMA_ORDENES = 1

_TABLAS_ORDENES = {"ordenes", "entregas", "intentos"}

_DDL = (
    """
    CREATE TABLE ordenes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo TEXT NOT NULL
            CHECK (tipo IN ('MENSAJE', 'IMAGEN', 'CAMBIAR_FONDO')),
        payload TEXT NOT NULL,
        image_id TEXT,
        destino_tipo TEXT NOT NULL
            CHECK (destino_tipo IN ('equipo', 'grupo', 'todos')),
        destino_etiqueta TEXT,
        creada_en TEXT NOT NULL,
        expira_en TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE entregas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        orden_id INTEGER NOT NULL
            REFERENCES ordenes(id) ON DELETE CASCADE,
        cliente_id INTEGER NOT NULL
            REFERENCES clientes(id) ON DELETE CASCADE,
        nombre_snapshot TEXT NOT NULL,
        ip_snapshot TEXT NOT NULL,
        estado TEXT NOT NULL DEFAULT 'pendiente'
            CHECK (estado IN (
                'pendiente', 'enviando', 'confirmada',
                'fallida', 'expirada', 'cancelada'
            )),
        intentos INTEGER NOT NULL DEFAULT 0 CHECK (intentos >= 0),
        resultado_incierto INTEGER NOT NULL DEFAULT 0
            CHECK (resultado_incierto IN (0, 1)),
        proximo_intento_en TEXT,
        ultimo_intento_en TEXT,
        confirmada_en TEXT,
        detalle TEXT
    )
    """,
    """
    CREATE TABLE intentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT
            CHECK (id BETWEEN 1 AND 4294967295),
        entrega_id INTEGER NOT NULL
            REFERENCES entregas(id) ON DELETE CASCADE,
        iniciado_en TEXT NOT NULL,
        terminado_en TEXT,
        resultado TEXT
            CHECK (resultado IN (
                'confirmado', 'no_conecto', 'incierto', 'interrumpido'
            )),
        detalle TEXT
    )
    """,
    """
    CREATE INDEX idx_entregas_cola
    ON entregas (cliente_id, estado, proximo_intento_en)
    """,
    "CREATE INDEX idx_entregas_orden ON entregas (orden_id)",
    "CREATE INDEX idx_ordenes_imagen ON ordenes (image_id)",
    "CREATE INDEX idx_intentos_entrega ON intentos (entrega_id)",
)


class MigracionOrdenesError(RuntimeError):
    """Error que impide migrar sin preservar los datos existentes."""


def _crear_respaldo(conexion: sqlite3.Connection, ruta_bd: Path) -> Path:
    marca_tiempo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ruta_respaldo = ruta_bd.with_name(
        f"{ruta_bd.name}.pre-orders-{marca_tiempo}.bak"
    )
    if ruta_respaldo.exists():
        raise FileExistsError(f"El respaldo ya existe: {ruta_respaldo}")

    respaldo = sqlite3.connect(ruta_respaldo)
    try:
        conexion.backup(respaldo)
    finally:
        respaldo.close()
    return ruta_respaldo


def _verificar_esquema(conexion: sqlite3.Connection) -> None:
    tablas = {
        fila[0]
        for fila in conexion.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    faltantes = _TABLAS_ORDENES - tablas
    if faltantes:
        raise MigracionOrdenesError(
            f"Faltan tablas de órdenes requeridas: {', '.join(sorted(faltantes))}"
        )

    foreign_keys = {
        (tabla, fila[2])
        for tabla in ("entregas", "intentos")
        for fila in conexion.execute(f'PRAGMA foreign_key_list("{tabla}")')
    }
    esperadas = {
        ("entregas", "ordenes"),
        ("entregas", "clientes"),
        ("intentos", "entregas"),
    }
    if not esperadas.issubset(foreign_keys):
        raise MigracionOrdenesError(
            f"Las claves foráneas del esquema de órdenes no coinciden: "
            f"{foreign_keys}"
        )

    errores_fk = conexion.execute("PRAGMA foreign_key_check").fetchall()
    if errores_fk:
        raise MigracionOrdenesError(
            f"La verificación de claves foráneas falló: {errores_fk}"
        )


def migrar_esquema_ordenes(ruta_bd: str | Path) -> Path | None:
    """Migra la tabla legacy vacía y retorna el respaldo creado, si aplica.

    La migración no descarta órdenes legacy: si la tabla antigua contiene filas,
    se detiene para que puedan mapearse explícitamente a entregas por cliente.
    """
    ruta = Path(ruta_bd).resolve()
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe la base SQLite: {ruta}")

    conexion = sqlite3.connect(ruta, timeout=30)
    conexion.row_factory = sqlite3.Row
    respaldo: Path | None = None
    try:
        conexion.execute("PRAGMA foreign_keys = OFF")
        version = conexion.execute("PRAGMA user_version").fetchone()[0]
        if version > VERSION_ESQUEMA_ORDENES:
            raise MigracionOrdenesError(
                f"La base tiene una versión de esquema más nueva ({version})"
            )
        if version == VERSION_ESQUEMA_ORDENES:
            _verificar_esquema(conexion)
            return None

        existentes = {
            fila[0]
            for fila in conexion.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        nuevas_existentes = existentes & _TABLAS_ORDENES
        if nuevas_existentes:
            raise MigracionOrdenesError(
                "Hay tablas nuevas de órdenes, pero user_version no está "
                f"actualizado: {', '.join(sorted(nuevas_existentes))}"
            )

        if "ordenes_pendientes" in existentes:
            cantidad = conexion.execute(
                "SELECT COUNT(*) FROM ordenes_pendientes"
            ).fetchone()[0]
            if cantidad:
                raise MigracionOrdenesError(
                    f"ordenes_pendientes contiene {cantidad} filas; "
                    "se requiere una conversión explícita antes de migrar"
                )

        respaldo = _crear_respaldo(conexion, ruta)
        conexion.execute("BEGIN IMMEDIATE")
        if "ordenes_pendientes" in existentes:
            conexion.execute("DROP TABLE ordenes_pendientes")
        for ddl in _DDL:
            conexion.execute(ddl)
        conexion.execute(f"PRAGMA user_version = {VERSION_ESQUEMA_ORDENES}")
        conexion.commit()

        conexion.execute("PRAGMA foreign_keys = ON")
        _verificar_esquema(conexion)
        return respaldo
    except Exception:
        if conexion.in_transaction:
            conexion.rollback()
        raise
    finally:
        conexion.close()
