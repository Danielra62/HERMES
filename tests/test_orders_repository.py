import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from admin.core import clients
from admin.core.order_schema import migrar_esquema_ordenes
from admin.core.orders import crear_orden

from tests.test_order_schema import crear_base_legacy


class OrderRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.directorio = tempfile.TemporaryDirectory()
        self.ruta = Path(self.directorio.name) / "hermes.db"
        crear_base_legacy(self.ruta)
        migrar_esquema_ordenes(self.ruta)
        self.patcher_db = patch.object(clients, "RUTA_SQLITE", self.ruta)
        self.patcher_db.start()
        self.patcher_mysql = patch.dict(os.environ, {"HERMES_USE_MYSQL": "false"})
        self.patcher_mysql.start()

    def tearDown(self):
        self.patcher_mysql.stop()
        self.patcher_db.stop()
        self.directorio.cleanup()

    def test_creates_order_and_freezes_recipient_snapshots_atomically(self):
        creado = crear_orden(
            "MENSAJE",
            {"titulo": "Aviso", "texto": "Prueba", "icono": "info"},
            [
                {"id": 1, "nombre": "Nombre obsoleto", "ip": "198.51.100.1"},
                {"id": 2, "nombre": "Nombre obsoleto", "ip": "198.51.100.2"},
            ],
            destino_tipo="grupo",
            destino_etiqueta="LABORATORIO1",
            ttl_segundos=3600,
            ahora=datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(creado["total"], 2)
        self.assertEqual(creado["creada_en"], "2026-11-17T12:00:00Z")
        self.assertEqual(creado["expira_en"], "2026-11-17T13:00:00Z")
        conexion = sqlite3.connect(self.ruta)
        orden = conexion.execute(
            "SELECT tipo, payload, destino_tipo, destino_etiqueta "
            "FROM ordenes WHERE id = ?",
            (creado["orden_id"],),
        ).fetchone()
        self.assertEqual(
            orden,
            (
                "MENSAJE",
                '{"titulo":"Aviso","texto":"Prueba","icono":"info"}',
                "grupo",
                "LABORATORIO1",
            ),
        )
        entregas = conexion.execute(
            "SELECT cliente_id, nombre_snapshot, ip_snapshot, estado "
            "FROM entregas WHERE orden_id = ? ORDER BY cliente_id",
            (creado["orden_id"],),
        ).fetchall()
        self.assertEqual(
            entregas,
            [
                (1, "PC1", "192.0.2.10", "pendiente"),
                (2, "PC2", "192.0.2.11", "pendiente"),
            ],
        )
        conexion.close()

    def test_rejects_duplicate_or_missing_recipients_without_partial_order(self):
        destinatario = {"id": 1, "nombre": "PC1", "ip": "192.0.2.10"}
        with self.assertRaisesRegex(ValueError, "duplicado"):
            crear_orden(
                "MENSAJE",
                {},
                [destinatario, destinatario],
                destino_tipo="todos",
                destino_etiqueta=None,
                ttl_segundos=60,
            )
        with self.assertRaisesRegex(ValueError, "sin destinatarios"):
            crear_orden(
                "MENSAJE",
                {},
                [],
                destino_tipo="todos",
                destino_etiqueta=None,
                ttl_segundos=60,
            )

        conexion = sqlite3.connect(self.ruta)
        self.assertEqual(conexion.execute("SELECT COUNT(*) FROM ordenes").fetchone()[0], 0)
        conexion.close()

    def test_rejects_invalid_image_id_and_unknown_client_without_partial_order(self):
        with self.assertRaisesRegex(ValueError, "image_id"):
            crear_orden(
                "IMAGEN",
                {},
                [{"id": 1, "nombre": "PC1", "ip": "192.0.2.10"}],
                destino_tipo="equipo",
                destino_etiqueta="PC1",
                ttl_segundos=3600,
                image_id="../invalid",
            )

        with self.assertRaisesRegex(ValueError, "No existen los clientes"):
            crear_orden(
                "MENSAJE",
                {},
                [
                    {"id": 1, "nombre": "PC1", "ip": "192.0.2.10"},
                    {"id": 999, "nombre": "Desconocido", "ip": "192.0.2.99"},
                ],
                destino_tipo="grupo",
                destino_etiqueta="LABORATORIO1",
                ttl_segundos=3600,
            )

        conexion = sqlite3.connect(self.ruta)
        self.assertEqual(conexion.execute("SELECT COUNT(*) FROM ordenes").fetchone()[0], 0)
        self.assertEqual(conexion.execute("SELECT COUNT(*) FROM entregas").fetchone()[0], 0)
        conexion.close()

    def test_accepts_image_order_and_stores_only_image_reference(self):
        image_id = "a" * 32
        with patch(
            "admin.core.orders.buscar_imagen_comprimida",
            return_value=Path(self.directorio.name) / f"{image_id}.jpg",
        ):
            creado = crear_orden(
                "CAMBIAR_FONDO",
                {"tipo": "fondo"},
                [{"id": 1, "nombre": "PC1", "ip": "192.0.2.10"}],
                destino_tipo="equipo",
                destino_etiqueta="PC1",
                ttl_segundos=86400,
                image_id=image_id,
            )
        conexion = sqlite3.connect(self.ruta)
        orden = conexion.execute(
            "SELECT image_id, payload FROM ordenes WHERE id = ?",
            (creado["orden_id"],),
        ).fetchone()
        self.assertEqual(orden[0], image_id)
        self.assertEqual(json.loads(orden[1]), {"tipo": "fondo"})
        conexion.close()


if __name__ == "__main__":
    unittest.main()
