"""
verificar_migracion.py

Compara el contenido de clientes.json contra lo que quedó en la BD,
para confirmar el criterio "listo cuando" de la tarjeta 0.4:
mismos clientes Y mismos grupos (incluyendo grupos vacíos), sin
duplicados ocultos, usando la misma configuración .env que el resto
de la app.

USO:
    python verificar_migracion.py [--ruta-json clientes.json]

Requiere:
    pip install mysql-connector-python python-dotenv
"""

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

import mysql.connector
from mysql.connector import Error as MySQLError

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Si no hay .env ni python-dotenv instalado, no pasa nada -- los
    # os.getenv() de abajo caen a los mismos defaults que clients.py.
    pass

# Mismos defaults que admin/core/clients.py, para que ambos scripts
# se conecten exactamente a la misma BD sin necesidad de .env en local
# (XAMPP/MariaDB con root sin contraseña).
DB_CONFIG = {
    "host": os.getenv("HERMES_DB_HOST", "localhost"),
    "port": int(os.getenv("HERMES_DB_PORT", "3306")),
    "user": os.getenv("HERMES_DB_USER", "root"),
    "password": os.getenv("HERMES_DB_PASSWORD", ""),
    "database": os.getenv("HERMES_DB_NAME", "hermes"),
}


def validar_config():
    # host, user y database siempre tienen un default no vacío, así que
    # esto solo dispara si alguien puso una variable de entorno vacía
    # a propósito (ej. HERMES_DB_HOST="" en el .env), lo cual sí sería
    # un error de configuración real. password="" es válido (root sin
    # contraseña en local) y no se valida aquí.
    campos_criticos = {"host": DB_CONFIG["host"], "user": DB_CONFIG["user"], "database": DB_CONFIG["database"]}
    faltantes = [k for k, v in campos_criticos.items() if not v]
    if faltantes:
        print(
            f"ERROR: configuración de BD inválida, campos vacíos: {faltantes}. "
            "Revisa tu .env (HERMES_DB_HOST, HERMES_DB_USER, HERMES_DB_NAME)."
        )
        sys.exit(1)


def cargar_json(ruta: Path) -> dict:
    if not ruta.exists():
        print(f"ERROR: no se encontró el archivo {ruta}")
        sys.exit(1)
    with ruta.open("r", encoding="utf-8") as f:
        return json.load(f)


def detectar_duplicados_json(datos: dict) -> list[str]:
    """
    Devuelve advertencias si clientes.json tiene entradas repetidas
    (mismo nombre+ip dentro del mismo grupo).
    """
    advertencias = []
    contador = Counter()
    for nombre_grupo, clientes in datos.get("grupos", {}).items():
        for c in clientes:
            contador[(c["nombre"], c["ip"], nombre_grupo)] += 1

    for clave, veces in contador.items():
        if veces > 1:
            advertencias.append(f"Entrada duplicada en el JSON: {clave} aparece {veces} veces")

    return advertencias


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ruta-json", default="clientes.json")
    args = parser.parse_args()

    validar_config()
    datos = cargar_json(Path(args.ruta_json))

    dup_json = detectar_duplicados_json(datos)
    if dup_json:
        print("ADVERTENCIA -- inconsistencias en el JSON de origen:")
        for d in dup_json:
            print(f"  - {d}")
        print()

    grupos_esperados = set(datos.get("grupos", {}).keys())
    clientes_esperados = set()
    for nombre_grupo, clientes in datos.get("grupos", {}).items():
        for c in clientes:
            clientes_esperados.add((c["nombre"], c["ip"], nombre_grupo))

    conn = None
    cursor = None
    try:
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
        except MySQLError as e:
            print(f"ERROR: no se pudo conectar a MySQL: {e}")
            sys.exit(1)

        cursor = conn.cursor()

        # Grupos: TODOS los grupos de la tabla `grupos`, tengan o no clientes.
        cursor.execute("SELECT nombre FROM grupos")
        grupos_en_bd = {fila[0] for fila in cursor.fetchall()}

        # Clientes: join con grupos, igual que antes.
        cursor.execute(
            """
            SELECT c.nombre, c.ip, g.nombre
            FROM clientes c
            JOIN grupos g ON g.id = c.grupo_id
            """
        )
        clientes_en_bd = set(cursor.fetchall())

    except MySQLError as e:
        print(f"ERROR de MySQL durante la verificación: {e}")
        sys.exit(1)
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

    # --- Comparación de grupos (incluyendo vacíos) ---
    grupos_faltantes = grupos_esperados - grupos_en_bd
    grupos_sobrantes = grupos_en_bd - grupos_esperados

    # --- Comparación de clientes ---
    clientes_faltantes = clientes_esperados - clientes_en_bd
    clientes_sobrantes = clientes_en_bd - clientes_esperados

    print(f"Grupos esperados (JSON): {len(grupos_esperados)} | en BD: {len(grupos_en_bd)}")
    print(f"Clientes esperados (JSON): {len(clientes_esperados)} | en BD: {len(clientes_en_bd)}\n")

    todo_ok = not (grupos_faltantes or grupos_sobrantes or clientes_faltantes or clientes_sobrantes)

    if todo_ok:
        print("✔ Todo coincide (grupos y clientes). Migración verificada correctamente.")
    else:
        if grupos_faltantes:
            print("Grupos faltantes en la BD:")
            for g in sorted(grupos_faltantes):
                print(f"  - {g}")
        if grupos_sobrantes:
            print("Grupos sobrantes en la BD (no estaban en el JSON):")
            for g in sorted(grupos_sobrantes):
                print(f"  - {g}")
        if clientes_faltantes:
            print("Clientes faltantes en la BD:")
            for c in sorted(clientes_faltantes):
                print(f"  - {c}")
        if clientes_sobrantes:
            print("Clientes sobrantes en la BD (no estaban en el JSON):")
            for c in sorted(clientes_sobrantes):
                print(f"  - {c}")
        sys.exit(1)


if __name__ == "__main__":
    main()