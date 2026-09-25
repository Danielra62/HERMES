"""Acceso a grupos y clientes almacenados en MySQL/MariaDB."""

import os

import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error, IntegrityError


load_dotenv()

GRUPOS_DEFAULT = ["LABORATORIO1", "LABORATORIO2", "AULAS"]


def _conexion():
    """Abre una conexion nueva; nunca se comparte entre hilos."""
    return mysql.connector.connect(
        host=os.getenv("HERMES_DB_HOST", "localhost"),
        port=int(os.getenv("HERMES_DB_PORT", "3306")),
        user=os.getenv("HERMES_DB_USER", "root"),
        password=os.getenv("HERMES_DB_PASSWORD", ""),
        database=os.getenv("HERMES_DB_NAME", "hermes"),
    )


def _error(mensaje: str) -> dict:
    print(f"[ERROR][DB] {mensaje}")
    return {"ok": False, "error": mensaje}


def _asegurar_grupos_default(cursor) -> None:
    for nombre in GRUPOS_DEFAULT:
        cursor.execute(
            "INSERT IGNORE INTO grupos (nombre) VALUES (%s)",
            (nombre,),
        )


def obtener_grupos() -> dict:
    """Retorna un diccionario de grupos con sus clientes."""
    conexion = None
    try:
        conexion = _conexion()
        cursor = conexion.cursor(dictionary=True)
        _asegurar_grupos_default(cursor)
        conexion.commit()
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
    except Error as exc:
        print(f"[ERROR][DB] No se pudieron obtener los grupos: {exc}")
        return {}
    finally:
        if conexion is not None and conexion.is_connected():
            conexion.close()


def obtener_clientes() -> list[str]:
    """Retorna todas las IPs de los clientes registrados."""
    conexion = None
    try:
        conexion = _conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT ip FROM clientes ORDER BY id")
        return [fila["ip"] for fila in cursor.fetchall()]
    except Error as exc:
        print(f"[ERROR][DB] No se pudieron obtener los clientes: {exc}")
        return []
    finally:
        if conexion is not None and conexion.is_connected():
            conexion.close()


def total_clientes() -> int:
    """Retorna el total de clientes; devuelve cero si la lectura falla."""
    conexion = None
    try:
        conexion = _conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) AS total FROM clientes")
        return cursor.fetchone()["total"]
    except Error as exc:
        print(f"[ERROR][DB] No se pudo contar los clientes: {exc}")
        return 0
    finally:
        if conexion is not None and conexion.is_connected():
            conexion.close()


def agregar_cliente(grupo: str, nombre: str, ip: str) -> dict:
    """Agrega un cliente a un grupo, creandolo si no existe."""
    nombre, ip = nombre.strip(), ip.strip()
    if not nombre or not ip:
        return {"ok": False, "error": "El nombre y la IP no pueden estar vacíos"}

    conexion = None
    try:
        conexion = _conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT id FROM grupos WHERE nombre = %s", (grupo,))
        fila = cursor.fetchone()
        if fila is None:
            cursor.execute("INSERT INTO grupos (nombre) VALUES (%s)", (grupo,))
            grupo_id = cursor.lastrowid
        else:
            grupo_id = fila["id"]

        cursor.execute(
            "SELECT id FROM clientes WHERE ip = %s",
            (ip,),
        )
        if cursor.fetchone() is not None:
            conexion.rollback()
            return {"ok": False, "error": f"{ip} ya está en {grupo}"}

        cursor.execute(
            "INSERT INTO clientes (nombre, ip, grupo_id) VALUES (%s, %s, %s)",
            (nombre, ip, grupo_id),
        )
        conexion.commit()
        return {"ok": True}
    except IntegrityError:
        if conexion is not None:
            conexion.rollback()
        return {"ok": False, "error": f"{ip} ya está en {grupo}"}
    except Error as exc:
        if conexion is not None:
            conexion.rollback()
        return _error(f"No se pudo agregar el cliente: {exc}")
    finally:
        if conexion is not None and conexion.is_connected():
            conexion.close()


def eliminar_cliente(grupo: str, ip: str) -> dict:
    """Elimina un cliente por IP dentro del grupo indicado."""
    conexion = None
    try:
        conexion = _conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            """
            DELETE c FROM clientes AS c
            INNER JOIN grupos AS g ON g.id = c.grupo_id
            WHERE g.nombre = %s AND c.ip = %s
            """,
            (grupo, ip),
        )
        if cursor.rowcount == 0:
            conexion.rollback()
            return {"ok": False, "error": f"{ip} no encontrado en {grupo}"}
        conexion.commit()
        return {"ok": True}
    except Error as exc:
        if conexion is not None:
            conexion.rollback()
        return _error(f"No se pudo eliminar el cliente: {exc}")
    finally:
        if conexion is not None and conexion.is_connected():
            conexion.close()


def editar_cliente(grupo: str, ip_original: str, nuevo_nombre: str, nueva_ip: str) -> dict:
    """Edita el nombre y/o IP de un cliente existente."""
    nuevo_nombre, nueva_ip = nuevo_nombre.strip(), nueva_ip.strip()
    if not nuevo_nombre or not nueva_ip:
        return {"ok": False, "error": "Nombre e IP no pueden estar vacíos"}

    conexion = None
    try:
        conexion = _conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(
            """
            UPDATE clientes AS c
            INNER JOIN grupos AS g ON g.id = c.grupo_id
            SET c.nombre = %s, c.ip = %s
            WHERE g.nombre = %s AND c.ip = %s
            """,
            (nuevo_nombre, nueva_ip, grupo, ip_original),
        )
        if cursor.rowcount == 0:
            conexion.rollback()
            return {"ok": False, "error": f"{ip_original} no encontrado en {grupo}"}
        conexion.commit()
        return {"ok": True}
    except IntegrityError:
        if conexion is not None:
            conexion.rollback()
        return {"ok": False, "error": f"{nueva_ip} ya está registrada"}
    except Error as exc:
        if conexion is not None:
            conexion.rollback()
        return _error(f"No se pudo editar el cliente: {exc}")
    finally:
        if conexion is not None and conexion.is_connected():
            conexion.close()


def limpiar_clientes() -> dict:
    """Elimina clientes y conserva los tres grupos predeterminados."""
    conexion = None
    try:
        conexion = _conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("DELETE FROM clientes")
        cursor.execute(
            "DELETE FROM grupos WHERE nombre NOT IN (%s, %s, %s)",
            tuple(GRUPOS_DEFAULT),
        )
        _asegurar_grupos_default(cursor)
        conexion.commit()
        return {"ok": True}
    except Error as exc:
        if conexion is not None:
            conexion.rollback()
        return _error(f"No se pudieron limpiar los clientes: {exc}")
    finally:
        if conexion is not None and conexion.is_connected():
            conexion.close()


def agregar_grupo(nombre: str) -> dict:
    """Crea un nuevo grupo vacío."""
    nombre = nombre.strip().upper()
    if not nombre:
        return {"ok": False, "error": "El nombre del grupo no puede estar vacío"}

    conexion = None
    try:
        conexion = _conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("INSERT INTO grupos (nombre) VALUES (%s)", (nombre,))
        conexion.commit()
        return {"ok": True, "nombre": nombre}
    except IntegrityError:
        if conexion is not None:
            conexion.rollback()
        return {"ok": False, "error": f"El grupo '{nombre}' ya existe"}
    except Error as exc:
        if conexion is not None:
            conexion.rollback()
        return _error(f"No se pudo crear el grupo: {exc}")
    finally:
        if conexion is not None and conexion.is_connected():
            conexion.close()


def eliminar_grupo(nombre: str) -> dict:
    """Elimina un grupo y todos sus clientes por cascada."""
    conexion = None
    try:
        conexion = _conexion()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("DELETE FROM grupos WHERE nombre = %s", (nombre,))
        if cursor.rowcount == 0:
            conexion.rollback()
            return {"ok": False, "error": f"El grupo '{nombre}' no existe"}
        conexion.commit()
        return {"ok": True}
    except Error as exc:
        if conexion is not None:
            conexion.rollback()
        return _error(f"No se pudo eliminar el grupo: {exc}")
    finally:
        if conexion is not None and conexion.is_connected():
            conexion.close()