"""Acceso a grupos y clientes mediante SQLite o MySQL/MariaDB."""

import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

try:
    import mysql.connector
    from mysql.connector import Error as MysqlError
    from mysql.connector import IntegrityError as MysqlIntegrityError
except ImportError:
    mysql = None

    class MysqlError(sqlite3.Error):
        pass

    class MysqlIntegrityError(sqlite3.IntegrityError, MysqlError):
        pass


load_dotenv()

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
RUTA_SQLITE = RAIZ_PROYECTO / "hermes.db"


def _usar_mysql() -> bool:
    return os.getenv("HERMES_USE_MYSQL", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "si",
    }


def _conexion():
    """Abre una conexion nueva; nunca se comparte entre hilos."""
    if _usar_mysql():
        if mysql is None:
            raise RuntimeError(
                "HERMES_USE_MYSQL=true requiere mysql-connector-python"
            )
        return mysql.connector.connect(
            host=os.getenv("HERMES_DB_HOST", "localhost"),
            port=int(os.getenv("HERMES_DB_PORT", "3306")),
            user=os.getenv("HERMES_DB_USER", "root"),
            password=os.getenv("HERMES_DB_PASSWORD", ""),
            database=os.getenv("HERMES_DB_NAME", "hermes"),
        )

    conexion = sqlite3.connect(RUTA_SQLITE, timeout=30)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


def _sql(conexion, consulta: str) -> str:
    """Convierte marcadores universales al dialecto del conector activo."""
    if isinstance(conexion, sqlite3.Connection):
        return consulta
    return consulta.replace("?", "%s")


def _cerrada(conexion) -> bool:
    if isinstance(conexion, sqlite3.Connection):
        return False
    return not conexion.is_connected()


class _CursorCompat:
    def __init__(self, conexion, cursor):
        self._conexion = conexion
        self._cursor = cursor

    def execute(self, consulta, parametros=None):
        consulta = _sql(self._conexion, consulta)
        if parametros is None:
            return self._cursor.execute(consulta)
        return self._cursor.execute(consulta, parametros)

    def __getattr__(self, nombre):
        return getattr(self._cursor, nombre)


def _cursor(conexion, dictionary: bool = False):
    if isinstance(conexion, sqlite3.Connection):
        conexion.row_factory = sqlite3.Row
        cursor = conexion.cursor()
    else:
        cursor = conexion.cursor(dictionary=dictionary)
    return _CursorCompat(conexion, cursor)


ERRORES_BD = (MysqlError, sqlite3.Error)
ERRORES_INTEGRIDAD = (MysqlIntegrityError, sqlite3.IntegrityError)


def _error(mensaje: str) -> dict:
    print(f"[ERROR][DB] {mensaje}")
    return {"ok": False, "error": mensaje}


def obtener_grupos() -> dict:
    """Retorna un diccionario de grupos con sus clientes."""
    conexion = None
    try:
        conexion = _conexion()
        cursor = _cursor(conexion, dictionary=True)
        cursor.execute(
            """
            SELECT g.nombre AS grupo, c.nombre AS nombre, c.ip AS ip
            FROM grupos AS g
            LEFT JOIN clientes AS c ON c.grupo_id = g.id
            ORDER BY g.id, c.id
            """
        )
        grupos = {}
        for fila in cursor.fetchall():
            grupos.setdefault(fila["grupo"], [])
            if fila["ip"] is not None:
                grupos[fila["grupo"]].append(
                    {"nombre": fila["nombre"], "ip": fila["ip"]}
                )
        return grupos
    except ERRORES_BD as exc:
        print(f"[ERROR][DB] No se pudieron obtener los grupos: {exc}")
        return {}
    finally:
        if conexion is not None and not _cerrada(conexion):
            conexion.close()


def obtener_clientes() -> list[str]:
    """Retorna todas las IPs de los clientes registrados."""
    conexion = None
    try:
        conexion = _conexion()
        cursor = _cursor(conexion, dictionary=True)
        cursor.execute("SELECT ip FROM clientes ORDER BY id")
        return [fila["ip"] for fila in cursor.fetchall()]
    except ERRORES_BD as exc:
        print(f"[ERROR][DB] No se pudieron obtener los clientes: {exc}")
        return []
    finally:
        if conexion is not None and not _cerrada(conexion):
            conexion.close()


def actualizar_disponibilidad_cliente(
    ip: str,
    estado: str = "disponible",
) -> dict:
    """Actualiza atómicamente un cliente registrado sin crear registros."""
    conexion = None
    cursor = None
    try:
        conexion = _conexion()
        cursor = _cursor(conexion, dictionary=True)
        cursor.execute(
            """
            UPDATE clientes
            SET estado = ?, ultima_conexion = CURRENT_TIMESTAMP
            WHERE ip = ?
            """,
            (estado, ip),
        )
        actualizado = cursor.rowcount > 0
        if not actualizado:
            cursor.execute("SELECT 1 FROM clientes WHERE ip = ?", (ip,))
            actualizado = cursor.fetchone() is not None
        conexion.commit()
        return {"ok": True, "actualizado": actualizado}
    except ERRORES_BD as exc:
        if conexion is not None:
            conexion.rollback()
        return _error(f"No se pudo actualizar la disponibilidad de {ip}: {exc}")
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and not _cerrada(conexion):
            conexion.close()


def obtener_clientes_no_disponibles() -> list[str]:
    """Obtiene las IPs que requieren verificación de disponibilidad."""
    conexion = None
    cursor = None
    try:
        conexion = _conexion()
        cursor = _cursor(conexion, dictionary=True)
        cursor.execute(
            "SELECT ip FROM clientes WHERE estado = ? ORDER BY id",
            ("no_disponible",),
        )
        return [fila["ip"] for fila in cursor.fetchall()]
    finally:
        if cursor is not None:
            cursor.close()
        if conexion is not None and not _cerrada(conexion):
            conexion.close()


def total_clientes() -> int:
    """Retorna el total de clientes; devuelve cero si la lectura falla."""
    conexion = None
    try:
        conexion = _conexion()
        cursor = _cursor(conexion, dictionary=True)
        cursor.execute("SELECT COUNT(*) AS total FROM clientes")
        return cursor.fetchone()["total"]
    except ERRORES_BD as exc:
        print(f"[ERROR][DB] No se pudo contar los clientes: {exc}")
        return 0
    finally:
        if conexion is not None and not _cerrada(conexion):
            conexion.close()


def agregar_cliente(grupo: str, nombre: str, ip: str) -> dict:
    """Agrega un cliente a un grupo, creandolo si no existe."""
    nombre, ip = nombre.strip(), ip.strip()
    if not nombre or not ip:
        return {"ok": False, "error": "El nombre y la IP no pueden estar vacíos"}

    conexion = None
    try:
        conexion = _conexion()
        cursor = _cursor(conexion, dictionary=True)
        cursor.execute("SELECT id FROM grupos WHERE nombre = ?", (grupo,))
        fila = cursor.fetchone()
        if fila is None:
            cursor.execute("INSERT INTO grupos (nombre) VALUES (?)", (grupo,))
            grupo_id = cursor.lastrowid
        else:
            grupo_id = fila["id"]

        cursor.execute(
            "SELECT id FROM clientes WHERE ip = ?",
            (ip,),
        )
        if cursor.fetchone() is not None:
            conexion.rollback()
            return {"ok": False, "error": f"{ip} ya está en {grupo}"}

        cursor.execute(
            "INSERT INTO clientes (nombre, ip, grupo_id) VALUES (?, ?, ?)",
            (nombre, ip, grupo_id),
        )
        conexion.commit()
        return {"ok": True}
    except ERRORES_INTEGRIDAD:
        if conexion is not None:
            conexion.rollback()
        return {"ok": False, "error": f"{ip} ya está en {grupo}"}
    except ERRORES_BD as exc:
        if conexion is not None:
            conexion.rollback()
        return _error(f"No se pudo agregar el cliente: {exc}")
    finally:
        if conexion is not None and not _cerrada(conexion):
            conexion.close()


def eliminar_cliente(grupo: str, ip: str) -> dict:
    """Elimina un cliente por IP dentro del grupo indicado."""
    conexion = None
    try:
        conexion = _conexion()
        cursor = _cursor(conexion, dictionary=True)
        if isinstance(conexion, sqlite3.Connection):
            cursor.execute(
                """
                DELETE FROM clientes
                WHERE grupo_id = (SELECT id FROM grupos WHERE nombre = ?)
                  AND ip = ?
                """,
                (grupo, ip),
            )
        else:
            cursor.execute(
                """
                DELETE c FROM clientes AS c
                INNER JOIN grupos AS g ON g.id = c.grupo_id
                WHERE g.nombre = ? AND c.ip = ?
                """,
                (grupo, ip),
            )
        if cursor.rowcount == 0:
            conexion.rollback()
            return {"ok": False, "error": f"{ip} no encontrado en {grupo}"}
        conexion.commit()
        return {"ok": True}
    except ERRORES_BD as exc:
        if conexion is not None:
            conexion.rollback()
        return _error(f"No se pudo eliminar el cliente: {exc}")
    finally:
        if conexion is not None and not _cerrada(conexion):
            conexion.close()


def editar_cliente(grupo: str, ip_original: str, nuevo_nombre: str, nueva_ip: str) -> dict:
    """Edita el nombre y/o IP de un cliente existente."""
    nuevo_nombre, nueva_ip = nuevo_nombre.strip(), nueva_ip.strip()
    if not nuevo_nombre or not nueva_ip:
        return {"ok": False, "error": "Nombre e IP no pueden estar vacíos"}

    conexion = None
    try:
        conexion = _conexion()
        cursor = _cursor(conexion, dictionary=True)
        if isinstance(conexion, sqlite3.Connection):
            cursor.execute(
                """
                UPDATE clientes
                SET nombre = ?, ip = ?
                WHERE grupo_id = (SELECT id FROM grupos WHERE nombre = ?)
                  AND ip = ?
                """,
                (nuevo_nombre, nueva_ip, grupo, ip_original),
            )
        else:
            cursor.execute(
                """
                UPDATE clientes AS c
                INNER JOIN grupos AS g ON g.id = c.grupo_id
                SET c.nombre = ?, c.ip = ?
                WHERE g.nombre = ? AND c.ip = ?
                """,
                (nuevo_nombre, nueva_ip, grupo, ip_original),
            )
        if cursor.rowcount == 0:
            conexion.rollback()
            return {"ok": False, "error": f"{ip_original} no encontrado en {grupo}"}
        conexion.commit()
        return {"ok": True}
    except ERRORES_INTEGRIDAD:
        if conexion is not None:
            conexion.rollback()
        return {"ok": False, "error": f"{nueva_ip} ya está registrada"}
    except ERRORES_BD as exc:
        if conexion is not None:
            conexion.rollback()
        return _error(f"No se pudo editar el cliente: {exc}")
    finally:
        if conexion is not None and not _cerrada(conexion):
            conexion.close()


def limpiar_clientes() -> dict:
    """Elimina todos los clientes y conserva los grupos existentes."""
    conexion = None
    try:
        conexion = _conexion()
        cursor = _cursor(conexion, dictionary=True)
        cursor.execute("DELETE FROM clientes")
        conexion.commit()
        return {"ok": True}
    except ERRORES_BD as exc:
        if conexion is not None:
            conexion.rollback()
        return _error(f"No se pudieron limpiar los clientes: {exc}")
    finally:
        if conexion is not None and not _cerrada(conexion):
            conexion.close()


def agregar_grupo(nombre: str) -> dict:
    """Crea un nuevo grupo vacío."""
    nombre = nombre.strip().upper()
    if not nombre:
        return {"ok": False, "error": "El nombre del grupo no puede estar vacío"}

    conexion = None
    try:
        conexion = _conexion()
        cursor = _cursor(conexion, dictionary=True)
        cursor.execute("INSERT INTO grupos (nombre) VALUES (?)", (nombre,))
        conexion.commit()
        return {"ok": True, "nombre": nombre}
    except ERRORES_INTEGRIDAD:
        if conexion is not None:
            conexion.rollback()
        return {"ok": False, "error": f"El grupo '{nombre}' ya existe"}
    except ERRORES_BD as exc:
        if conexion is not None:
            conexion.rollback()
        return _error(f"No se pudo crear el grupo: {exc}")
    finally:
        if conexion is not None and not _cerrada(conexion):
            conexion.close()


def eliminar_grupo(nombre: str) -> dict:
    """Elimina un grupo y todos sus clientes por cascada."""
    conexion = None
    try:
        conexion = _conexion()
        cursor = _cursor(conexion, dictionary=True)
        cursor.execute("DELETE FROM grupos WHERE nombre = ?", (nombre,))
        if cursor.rowcount == 0:
            conexion.rollback()
            return {"ok": False, "error": f"El grupo '{nombre}' no existe"}
        conexion.commit()
        return {"ok": True}
    except ERRORES_BD as exc:
        if conexion is not None:
            conexion.rollback()
        return _error(f"No se pudo eliminar el grupo: {exc}")
    finally:
        if conexion is not None and not _cerrada(conexion):
            conexion.close()