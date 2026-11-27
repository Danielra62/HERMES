import sqlite3
import tempfile
import unittest
from pathlib import Path

from admin.core.order_schema import (
    MigracionOrdenesError,
    migrar_esquema_ordenes,
)


def crear_base_legacy(ruta: Path, *, con_orden: bool = False) -> None:
    conexion = sqlite3.connect(ruta)
    conexion.executescript(
        """
        PRAGMA foreign_keys = OFF;
        CREATE TABLE grupos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL
        );
        CREATE TABLE clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            ip TEXT NOT NULL,
            grupo_id INTEGER NOT NULL REFERENCES grupos(id) ON DELETE CASCADE
        );
        CREATE TABLE ordenes_pendientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER DEFAULT 'NULL',
            grupo_id INTEGER DEFAULT 'NULL',
            tipo_orden TEXT NOT NULL,
            payload TEXT NOT NULL,
            fecha_creacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            estado TEXT NOT NULL DEFAULT '''pendiente''',
            FOREIGN KEY (cliente_id) REFERENCES clientes_migracion(id),
            FOREIGN KEY (grupo_id) REFERENCES grupos(id)
        );
        INSERT INTO grupos (nombre) VALUES ('LABORATORIO1');
        INSERT INTO clientes (nombre, ip, grupo_id) VALUES
            ('PC1', '192.0.2.10', 1),
            ('PC2', '192.0.2.11', 1);
        """
    )
    if con_orden:
        conexion.execute(
            """
            INSERT INTO ordenes_pendientes (cliente_id, tipo_orden, payload)
            VALUES (1, 'MENSAJE', '{}')
            """
        )
    conexion.commit()
    conexion.close()


class OrderSchemaMigrationTests(unittest.TestCase):
    def test_migration_creates_valid_schema_and_backup(self):
        with tempfile.TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "hermes.db"
            crear_base_legacy(ruta)

            respaldo = migrar_esquema_ordenes(ruta)

            self.assertIsNotNone(respaldo)
            self.assertTrue(respaldo.is_file())
            conexion = sqlite3.connect(ruta)
            self.assertEqual(
                conexion.execute("PRAGMA user_version").fetchone()[0],
                1,
            )
            self.assertEqual(
                conexion.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='ordenes_pendientes'"
                ).fetchone(),
                None,
            )
            foreign_keys = {
                (tabla, fila[2])
                for tabla in ("entregas", "intentos")
                for fila in conexion.execute(f'PRAGMA foreign_key_list("{tabla}")')
            }
            self.assertEqual(
                foreign_keys,
                {
                    ("entregas", "ordenes"),
                    ("entregas", "clientes"),
                    ("intentos", "entregas"),
                },
            )
            self.assertEqual(conexion.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(
                conexion.execute("PRAGMA integrity_check").fetchone()[0],
                "ok",
            )
            columnas = {
                fila[1]: fila[4]
                for fila in conexion.execute("PRAGMA table_info(entregas)")
            }
            self.assertEqual(columnas["estado"], "'pendiente'")
            conexion.close()

            self.assertIsNone(migrar_esquema_ordenes(ruta))

    def test_migration_refuses_to_drop_legacy_rows(self):
        with tempfile.TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "hermes.db"
            crear_base_legacy(ruta, con_orden=True)

            with self.assertRaisesRegex(MigracionOrdenesError, "contiene 1 filas"):
                migrar_esquema_ordenes(ruta)

            conexion = sqlite3.connect(ruta)
            self.assertEqual(
                conexion.execute("SELECT COUNT(*) FROM ordenes_pendientes").fetchone()[0],
                1,
            )
            self.assertEqual(conexion.execute("PRAGMA user_version").fetchone()[0], 0)
            conexion.close()

    def test_migration_refuses_partially_created_schema(self):
        with tempfile.TemporaryDirectory() as directorio:
            ruta = Path(directorio) / "hermes.db"
            crear_base_legacy(ruta)
            conexion = sqlite3.connect(ruta)
            conexion.execute("CREATE TABLE ordenes (id INTEGER PRIMARY KEY)")
            conexion.commit()
            conexion.close()

            with self.assertRaisesRegex(MigracionOrdenesError, "user_version"):
                migrar_esquema_ordenes(ruta)


if __name__ == "__main__":
    unittest.main()
