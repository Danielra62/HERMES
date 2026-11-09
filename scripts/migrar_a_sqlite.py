"""Clona las tablas, filas e índices de MariaDB a hermes.db.

Uso desde la raíz del proyecto:
    python -m scripts.migrar_a_sqlite

El archivo de destino no se sobrescribe. Si ya existe, elimínalo o respáldalo
manualmente antes de volver a ejecutar la migración.
"""

from __future__ import annotations

import os
import re
import sqlite3
import tempfile
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any

from admin.core.clients import _conexion


RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
RUTA_DESTINO = RAIZ_PROYECTO / "hermes.db"

_TIPOS_ENTEROS = {
    "bigint",
    "int",
    "integer",
    "mediumint",
    "smallint",
    "tinyint",
    "year",
}
_TIPOS_REALES = {"double", "float", "real"}
_TIPOS_NUMERICOS = {"dec", "decimal", "numeric"}
_TIPOS_BINARIOS = {"binary", "blob", "longblob", "mediumblob", "tinyblob", "varbinary"}
_TIPOS_FECHA = {"date", "datetime", "time", "timestamp"}


def _identificador(nombre: str) -> str:
    return '"' + nombre.replace('"', '""') + '"'


def _literal_sql(valor: Any) -> str:
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return str(valor)
    if isinstance(valor, bool):
        return "1" if valor else "0"
    return "'" + str(valor).replace("'", "''") + "'"


def _tipo_sqlite(columna: dict[str, Any]) -> str:
    tipo = columna["DATA_TYPE"].lower()
    if tipo in _TIPOS_ENTEROS:
        return "INTEGER"
    if tipo in _TIPOS_REALES:
        return "REAL"
    if tipo in _TIPOS_NUMERICOS:
        return "NUMERIC"
    if tipo in _TIPOS_BINARIOS:
        return "BLOB"
    if tipo in _TIPOS_FECHA:
        return "DATETIME" if tipo in {"datetime", "timestamp"} else "TEXT"
    return "TEXT"


def _valores_enum(column_type: str) -> list[str]:
    valores = re.findall(r"'((?:[^'\\]|\\.|'')*)'", column_type)
    return [
        valor.replace("''", "'").replace("\\'", "'").replace("\\\\", "\\")
        for valor in valores
    ]


def _ddl_columna(columna: dict[str, Any]) -> str:
    nombre = _identificador(columna["COLUMN_NAME"])
    tipo_mysql = columna["DATA_TYPE"].lower()
    tipo = _tipo_sqlite(columna)
    definicion = f"{nombre} {tipo}"

    if columna["IS_NULLABLE"] == "NO":
        definicion += " NOT NULL"

    extra = (columna.get("EXTRA") or "").lower()
    if "auto_increment" in extra:
        if tipo != "INTEGER":
            raise ValueError(
                f"AUTO_INCREMENT requiere INTEGER en SQLite: "
                f"{columna['COLUMN_NAME']}"
            )
        definicion += " PRIMARY KEY AUTOINCREMENT"
    elif columna["COLUMN_DEFAULT"] is not None:
        default = columna["COLUMN_DEFAULT"]
        if isinstance(default, str) and default.upper() in {
            "CURRENT_TIMESTAMP",
            "CURRENT_TIMESTAMP()",
        }:
            definicion += " DEFAULT CURRENT_TIMESTAMP"
        else:
            valor_default = default
            if isinstance(valor_default, str) and len(valor_default) >= 2:
                if valor_default[0] == valor_default[-1] == "'":
                    valor_default = valor_default[1:-1].replace("''", "'")
            definicion += f" DEFAULT {_literal_sql(valor_default)}"

    if tipo_mysql == "enum":
        valores = _valores_enum(columna["COLUMN_TYPE"])
        if not valores:
            raise ValueError(
                f"No se pudieron interpretar los valores ENUM de "
                f"{columna['COLUMN_NAME']}"
            )
        opciones = ", ".join(_literal_sql(valor) for valor in valores)
        definicion += f" CHECK ({nombre} IN ({opciones}))"
    elif tipo_mysql in {"varchar", "char"}:
        coincidencia = re.search(r"\((\d+)\)", columna["COLUMN_TYPE"])
        if coincidencia:
            definicion += f" CHECK ({nombre} IS NULL OR length({nombre}) <= {coincidencia.group(1)})"

    return definicion


def _obtener_tablas(cursor: Any, esquema: str) -> list[str]:
    cursor.execute(
        """
        SELECT TABLE_NAME
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
        """,
        (esquema,),
    )
    return [fila["TABLE_NAME"] for fila in cursor.fetchall()]


def _obtener_columnas(cursor: Any, esquema: str, tabla: str) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT COLUMN_NAME, DATA_TYPE, COLUMN_TYPE, IS_NULLABLE,
               COLUMN_DEFAULT, EXTRA, ORDINAL_POSITION
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        ORDER BY ORDINAL_POSITION
        """,
        (esquema, tabla),
    )
    return cursor.fetchall()


def _obtener_claves(cursor: Any, esquema: str, tabla: str) -> tuple[list[str], list[dict[str, Any]]]:
    cursor.execute(
        """
        SELECT tc.CONSTRAINT_TYPE, tc.CONSTRAINT_NAME,
               kcu.COLUMN_NAME, kcu.ORDINAL_POSITION,
               kcu.REFERENCED_TABLE_NAME, kcu.REFERENCED_COLUMN_NAME,
               rc.UPDATE_RULE, rc.DELETE_RULE
        FROM information_schema.TABLE_CONSTRAINTS AS tc
        JOIN information_schema.KEY_COLUMN_USAGE AS kcu
          ON kcu.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA
         AND kcu.TABLE_NAME = tc.TABLE_NAME
         AND kcu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
        LEFT JOIN information_schema.REFERENTIAL_CONSTRAINTS AS rc
          ON rc.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA
         AND rc.TABLE_NAME = tc.TABLE_NAME
         AND rc.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
        WHERE tc.TABLE_SCHEMA = %s AND tc.TABLE_NAME = %s
          AND tc.CONSTRAINT_TYPE IN ('PRIMARY KEY', 'FOREIGN KEY')
        ORDER BY tc.CONSTRAINT_NAME, kcu.ORDINAL_POSITION
        """,
        (esquema, tabla),
    )
    filas = cursor.fetchall()
    primarias = [fila for fila in filas if fila["CONSTRAINT_TYPE"] == "PRIMARY KEY"]
    foranea = [fila for fila in filas if fila["CONSTRAINT_TYPE"] == "FOREIGN KEY"]

    columnas_pk = []
    for fila in primarias:
        if fila["COLUMN_NAME"] not in columnas_pk:
            columnas_pk.append(fila["COLUMN_NAME"])

    grupos: dict[str, list[dict[str, Any]]] = {}
    for fila in foranea:
        grupos.setdefault(fila["CONSTRAINT_NAME"], []).append(fila)
    return columnas_pk, list(grupos.values())


def _ddl_tabla(
    cursor: Any,
    esquema: str,
    tabla: str,
    columnas: list[dict[str, Any]],
) -> str:
    primarias, foraneas = _obtener_claves(cursor, esquema, tabla)
    definiciones = [_ddl_columna(columna) for columna in columnas]
    pk_auto_incremental = any(
        "auto_increment" in (columna.get("EXTRA") or "").lower()
        for columna in columnas
    )
    if primarias and not pk_auto_incremental:
        columnas_pk = ", ".join(_identificador(nombre) for nombre in primarias)
        definiciones.append(f"PRIMARY KEY ({columnas_pk})")

    for grupo in foraneas:
        primero = grupo[0]
        columnas_locales = ", ".join(
            _identificador(fila["COLUMN_NAME"]) for fila in grupo
        )
        columnas_remotas = ", ".join(
            _identificador(fila["REFERENCED_COLUMN_NAME"]) for fila in grupo
        )
        referencia = (
            f"FOREIGN KEY ({columnas_locales}) "
            f"REFERENCES {_identificador(primero['REFERENCED_TABLE_NAME'])} "
            f"({columnas_remotas})"
        )
        if primero["UPDATE_RULE"]:
            referencia += f" ON UPDATE {primero['UPDATE_RULE']}"
        if primero["DELETE_RULE"]:
            referencia += f" ON DELETE {primero['DELETE_RULE']}"
        definiciones.append(referencia)

    cuerpo = ",\n    ".join(definiciones)
    return f"CREATE TABLE {_identificador(tabla)} (\n    {cuerpo}\n)"


def _crear_indices(
    cursor_mysql: Any,
    conexion_sqlite: sqlite3.Connection,
    esquema: str,
    tablas: list[str],
) -> None:
    nombres_usados: set[str] = set()
    cursor_sqlite = conexion_sqlite.cursor()
    try:
        for tabla in tablas:
            cursor_mysql.execute(f"SHOW INDEX FROM `{tabla.replace('`', '``')}`")
            indices: dict[str, list[dict[str, Any]]] = {}
            for fila in cursor_mysql.fetchall():
                nombre = fila["Key_name"]
                if nombre == "PRIMARY":
                    continue
                if fila.get("Sub_part") is not None or fila.get("Column_name") is None:
                    raise ValueError(
                        f"El índice {nombre} de {tabla} usa una expresión o "
                        "un prefijo que no se puede clonar directamente a SQLite"
                    )
                indices.setdefault(nombre, []).append(fila)

            for nombre, filas in indices.items():
                filas.sort(key=lambda fila: fila["Seq_in_index"])
                nombre_sqlite = nombre
                if nombre_sqlite in nombres_usados:
                    nombre_sqlite = f"{tabla}_{nombre}"
                nombres_usados.add(nombre_sqlite)
                columnas = ", ".join(
                    _identificador(fila["Column_name"]) for fila in filas
                )
                es_unico = int(filas[0]["Non_unique"]) == 0
                unica = "UNIQUE " if es_unico else ""
                cursor_sqlite.execute(
                    f"CREATE {unica}INDEX {_identificador(nombre_sqlite)} "
                    f"ON {_identificador(tabla)} ({columnas})"
                )
    finally:
        cursor_sqlite.close()


def _valor_sqlite(valor: Any) -> Any:
    if isinstance(valor, (datetime, date, time)):
        return valor.isoformat(sep=" ") if isinstance(valor, datetime) else valor.isoformat()
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, memoryview):
        return valor.tobytes()
    if isinstance(valor, bytearray):
        return bytes(valor)
    return valor


def _copiar_filas(
    cursor_mysql: Any,
    conexion_sqlite: sqlite3.Connection,
    esquema: str,
    tablas: list[str],
) -> dict[str, int]:
    conteos: dict[str, int] = {}
    cursor_sqlite = conexion_sqlite.cursor()
    try:
        for tabla in tablas:
            columnas = _obtener_columnas(cursor_mysql, esquema, tabla)
            nombres = [columna["COLUMN_NAME"] for columna in columnas]
            nombres_sql = ", ".join(_identificador(nombre) for nombre in nombres)
            placeholders = ", ".join("?" for _ in nombres)
            cursor_mysql.execute(
                f"SELECT {', '.join(f'`{nombre.replace('`', '``')}`' for nombre in nombres)} "
                f"FROM `{tabla.replace('`', '``')}`"
            )
            filas = cursor_mysql.fetchall()
            cursor_sqlite.executemany(
                f"INSERT INTO {_identificador(tabla)} ({nombres_sql}) "
                f"VALUES ({placeholders})",
                [
                    tuple(_valor_sqlite(fila[nombre]) for nombre in nombres)
                    for fila in filas
                ],
            )
            conteos[tabla] = len(filas)
    finally:
        cursor_sqlite.close()
    return conteos


def _restaurar_contadores(
    cursor_mysql: Any,
    conexion_sqlite: sqlite3.Connection,
    esquema: str,
    tablas: list[str],
) -> None:
    cursor_mysql.execute(
        """
        SELECT TABLE_NAME, AUTO_INCREMENT
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
        """,
        (esquema,),
    )
    contadores = {
        fila["TABLE_NAME"]: fila["AUTO_INCREMENT"]
        for fila in cursor_mysql.fetchall()
        if fila["AUTO_INCREMENT"] is not None
    }
    cursor_sqlite = conexion_sqlite.cursor()
    try:
        for tabla in tablas:
            siguiente = contadores.get(tabla)
            if siguiente is None:
                continue
            cursor_sqlite.execute(
                "UPDATE sqlite_sequence SET seq = ? WHERE name = ?",
                (max(0, int(siguiente) - 1), tabla),
            )
            if cursor_sqlite.rowcount == 0:
                cursor_sqlite.execute(
                    "INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)",
                    (tabla, max(0, int(siguiente) - 1)),
                )
    finally:
        cursor_sqlite.close()


def migrar() -> dict[str, int]:
    """Migra el esquema y los datos a un archivo nuevo en la raíz del repo."""
    if RUTA_DESTINO.exists():
        raise FileExistsError(
            f"El destino ya existe y no se sobrescribirá: {RUTA_DESTINO}"
        )

    conexion_mysql = _conexion()
    cursor_mysql = conexion_mysql.cursor(dictionary=True)
    descriptor, ruta_temporal = tempfile.mkstemp(
        prefix=".hermes-migration-",
        suffix=".tmp",
        dir=RAIZ_PROYECTO,
    )
    os.close(descriptor)
    os.remove(ruta_temporal)
    conexion_sqlite: sqlite3.Connection | None = None
    try:
        cursor_mysql.execute("SELECT DATABASE() AS nombre")
        esquema = cursor_mysql.fetchone()["nombre"]
        tablas = _obtener_tablas(cursor_mysql, esquema)
        if not tablas:
            raise RuntimeError(f"No se encontraron tablas en el esquema {esquema!r}")

        conexion_sqlite = sqlite3.connect(ruta_temporal)
        conexion_sqlite.execute("PRAGMA foreign_keys = ON")
        for tabla in tablas:
            columnas = _obtener_columnas(cursor_mysql, esquema, tabla)
            ddl = _ddl_tabla(cursor_mysql, esquema, tabla, columnas)
            conexion_sqlite.execute(ddl)

        conexion_sqlite.execute("PRAGMA defer_foreign_keys = ON")
        conexion_sqlite.execute("BEGIN")
        conteos = _copiar_filas(cursor_mysql, conexion_sqlite, esquema, tablas)
        _crear_indices(cursor_mysql, conexion_sqlite, esquema, tablas)
        _restaurar_contadores(cursor_mysql, conexion_sqlite, esquema, tablas)
        errores_fk = conexion_sqlite.execute("PRAGMA foreign_key_check").fetchall()
        if errores_fk:
            raise RuntimeError(f"Falló la verificación de claves foráneas: {errores_fk}")
        conexion_sqlite.commit()
        conexion_sqlite.close()
        conexion_sqlite = None
        cursor_mysql.close()
        cursor_mysql = None
        conexion_mysql.close()
        conexion_mysql = None

        if RUTA_DESTINO.exists():
            raise FileExistsError(
                f"El destino apareció durante la migración y no se sobrescribirá: "
                f"{RUTA_DESTINO}"
            )
        os.replace(ruta_temporal, RUTA_DESTINO)
        return conteos
    except Exception:
        if conexion_sqlite is not None:
            conexion_sqlite.close()
        if os.path.exists(ruta_temporal):
            os.remove(ruta_temporal)
        raise
    finally:
        if cursor_mysql is not None:
            cursor_mysql.close()
        if conexion_mysql is not None and conexion_mysql.is_connected():
            conexion_mysql.close()


def main() -> None:
    conteos = migrar()
    total = sum(conteos.values())
    print(f"Migración completada: {RUTA_DESTINO}")
    for tabla, cantidad in conteos.items():
        print(f"  {tabla}: {cantidad} filas")
    print(f"Total: {total} filas en {len(conteos)} tablas")


if __name__ == "__main__":
    main()
