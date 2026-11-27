import os
import sqlite3
import tempfile
import unittest
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

from admin.core import clients, network, order_delivery, orders
from admin.main import app
from admin.core.order_schema import migrar_esquema_ordenes
from tests.test_order_schema import crear_base_legacy


class OrderDeliveryTests(unittest.TestCase):
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

    def _crear_fondo(self, image_id: str, destinatario: int = 1) -> dict:
        ruta_imagen = Path(self.directorio.name) / f"{image_id}.jpg"
        ruta_imagen.write_bytes(b"jpeg")
        with ExitStack() as stack:
            stack.enter_context(patch(
                "admin.core.orders.buscar_imagen_comprimida",
                return_value=ruta_imagen,
            ))
            return orders.crear_orden(
                "CAMBIAR_FONDO",
                {"tipo": "fondo"},
                [destinatario],
                destino_tipo="equipo",
                destino_etiqueta="PC1",
                ttl_segundos=86400,
                image_id=image_id,
            )

    def _entrega(self, orden_id: int) -> tuple:
        conexion = sqlite3.connect(self.ruta)
        try:
            return conexion.execute(
                """
                SELECT e.id, e.estado, e.intentos, e.resultado_incierto,
                       e.proximo_intento_en, e.detalle
                FROM entregas AS e
                WHERE e.orden_id = ?
                """,
                (orden_id,),
            ).fetchone()
        finally:
            conexion.close()

    def test_preconnect_failure_is_queued_and_reported(self):
        with patch(
            "admin.core.order_delivery.network.enviar_orden_v2_a_uno",
            return_value={
                "ip": "192.0.2.10",
                "ok": False,
                "conectado": False,
                "error": "RECHAZADO",
            },
        ):
            resultado = order_delivery.crear_y_entregar(
                tipo="MENSAJE",
                payload={"titulo": "Aviso", "texto": "Prueba", "icono": "info"},
                destino_tipo="equipo",
                destino_etiqueta="192.0.2.10",
            )

        respuesta = order_delivery.respuesta_masiva(resultado)
        entrega = self._entrega(resultado["orden_id"])
        self.assertEqual(respuesta["total"], 1)
        self.assertEqual(respuesta["fallidos"], 1)
        self.assertEqual(respuesta["encoladas"], 1)
        self.assertEqual(respuesta["inciertas"], 0)
        self.assertEqual(entrega[1:4], ("pendiente", 1, 0))
        self.assertIsNotNone(entrega[4])

    def test_message_failure_after_connect_is_uncertain_and_not_retried(self):
        with patch(
            "admin.core.order_delivery.network.enviar_orden_v2_a_uno",
            return_value={
                "ip": "192.0.2.10",
                "ok": False,
                "conectado": True,
                "error": "TIMEOUT",
            },
        ):
            resultado = order_delivery.crear_y_entregar(
                tipo="MENSAJE",
                payload={"titulo": "Aviso", "texto": "Prueba", "icono": "info"},
                destino_tipo="equipo",
                destino_etiqueta="192.0.2.10",
            )

        respuesta = order_delivery.respuesta_individual(resultado)
        entrega = self._entrega(resultado["orden_id"])
        self.assertFalse(respuesta["ok"])
        self.assertEqual(respuesta["encoladas"], 0)
        self.assertEqual(respuesta["inciertas"], 1)
        self.assertEqual(entrega[1:5], ("fallida", 1, 1, None))

    def test_wallpaper_uncertainty_can_retry_and_be_confirmed(self):
        image_id = "a" * 32
        ruta_imagen = Path(self.directorio.name) / f"{image_id}.jpg"
        ruta_imagen.write_bytes(b"jpeg")
        with ExitStack() as stack:
            stack.enter_context(patch(
                "admin.core.orders.buscar_imagen_comprimida",
                return_value=ruta_imagen,
            ))
            stack.enter_context(patch(
                "admin.core.order_delivery.image_processing.buscar_imagen_comprimida",
                return_value=ruta_imagen,
            ))
            with patch(
                "admin.core.order_delivery.network.enviar_orden_v2_a_uno",
                return_value={
                    "ip": "192.0.2.10",
                    "ok": False,
                    "conectado": True,
                    "error": "ACK ausente",
                },
            ):
                resultado = order_delivery.crear_y_entregar(
                    tipo="CAMBIAR_FONDO",
                    payload={"tipo": "fondo"},
                    destino_tipo="equipo",
                    destino_etiqueta="192.0.2.10",
                    image_id=image_id,
                )

            primera = self._entrega(resultado["orden_id"])
            self.assertEqual(primera[1:4], ("pendiente", 1, 1))

            orders.adelantar_reintentos_cliente("192.0.2.10")
            with patch(
                "admin.core.order_delivery.network.enviar_orden_v2_a_uno",
                return_value={
                    "ip": "192.0.2.10",
                    "ok": True,
                    "conectado": True,
                    "respuesta": "OK",
                },
            ):
                order_delivery.procesar_entregas_pendientes(
                    cliente_ip="192.0.2.10"
                )

        segunda = self._entrega(resultado["orden_id"])
        self.assertEqual(segunda[1:4], ("confirmada", 2, 0))

    def test_new_wallpaper_cancels_only_older_pending_wallpaper(self):
        image_id_1 = "b" * 32
        image_id_2 = "c" * 32
        primera = self._crear_fondo(image_id_1)
        segunda = self._crear_fondo(image_id_2)

        conexion = sqlite3.connect(self.ruta)
        try:
            estados = conexion.execute(
                """
                SELECT o.id, e.estado
                FROM ordenes AS o
                JOIN entregas AS e ON e.orden_id = o.id
                ORDER BY o.id
                """
            ).fetchall()
        finally:
            conexion.close()
        self.assertEqual(
            estados,
            [(primera["orden_id"], "cancelada"), (segunda["orden_id"], "pendiente")],
        )

    def test_restart_recovers_interrupted_message_as_uncertain(self):
        orden = orders.crear_orden(
            "MENSAJE",
            {"titulo": "Aviso", "texto": "Prueba", "icono": "info"},
            [1],
            destino_tipo="equipo",
            destino_etiqueta="PC1",
            ttl_segundos=3600,
        )
        entrega = orders.reclamar_entregas(limite=1)[0]

        self.assertEqual(
            orders.recuperar_entregas_interrumpidas(
                order_delivery.MAX_INTENTOS,
                order_delivery.RETRASOS_REINTENTO_SEGUNDOS,
            ),
            1,
        )
        estado = self._entrega(orden["orden_id"])
        conexion = sqlite3.connect(self.ruta)
        try:
            intento = conexion.execute(
                "SELECT resultado FROM intentos WHERE id = ?",
                (entrega["intento_id"],),
            ).fetchone()
        finally:
            conexion.close()
        self.assertEqual(estado[1:4], ("fallida", 1, 1))
        self.assertEqual(intento, ("interrumpido",))

    def test_restart_retries_interrupted_wallpaper(self):
        imagen_id = "d" * 32
        self._crear_fondo(imagen_id)
        orders.reclamar_entregas(limite=1)

        orders.recuperar_entregas_interrumpidas(
            order_delivery.MAX_INTENTOS,
            order_delivery.RETRASOS_REINTENTO_SEGUNDOS,
        )

        estado = self._entrega(1)
        self.assertEqual(estado[1:4], ("pendiente", 1, 1))
        self.assertIsNotNone(estado[4])

    def test_network_classifies_connect_and_post_connect_failures(self):
        sin_conexion = MagicMock()
        sin_conexion.__enter__.return_value = sin_conexion
        sin_conexion.connect.side_effect = ConnectionRefusedError()
        with patch(
            "admin.core.network.socket.socket",
            return_value=sin_conexion,
        ):
            resultado_sin_conexion = network.enviar_orden_v2_a_uno(
                "192.0.2.10", 1, b"{}"
            )

        conectado = MagicMock()
        conectado.__enter__.return_value = conectado
        conectado.sendall.side_effect = OSError("send falló")
        with patch(
            "admin.core.network.socket.socket",
            return_value=conectado,
        ):
            resultado_incierto = network.enviar_orden_v2_a_uno(
                "192.0.2.10", 1, b"{}"
            )

        self.assertFalse(resultado_sin_conexion["conectado"])
        self.assertTrue(resultado_incierto["conectado"])

    def test_concurrent_workers_claim_a_delivery_only_once(self):
        orden = orders.crear_orden(
            "MENSAJE",
            {"titulo": "Aviso", "texto": "Prueba", "icono": "info"},
            [1],
            destino_tipo="equipo",
            destino_etiqueta="PC1",
            ttl_segundos=3600,
        )
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    lambda _: orders.reclamar_entregas(limite=1),
                    range(2),
                )
            )

        entregas_reclamadas = [entrega for lote in results for entrega in lote]
        self.assertEqual(len(entregas_reclamadas), 1)
        self.assertEqual(
            entregas_reclamadas[0]["entrega_id"],
            orders.obtener_entregas_ids(orden["orden_id"])[0],
        )

    def test_preconnect_failures_stop_after_six_attempts(self):
        fallo = {
            "ip": "192.0.2.10",
            "ok": False,
            "conectado": False,
            "error": "RECHAZADO",
        }
        with patch(
            "admin.core.order_delivery.network.enviar_orden_v2_a_uno",
            return_value=fallo,
        ):
            resultado = order_delivery.crear_y_entregar(
                tipo="MENSAJE",
                payload={"titulo": "Aviso", "texto": "Prueba", "icono": "info"},
                destino_tipo="equipo",
                destino_etiqueta="192.0.2.10",
            )
            for _ in range(order_delivery.MAX_INTENTOS - 1):
                conexion = sqlite3.connect(self.ruta)
                try:
                    conexion.execute(
                        """
                        UPDATE entregas
                        SET proximo_intento_en = NULL
                        WHERE orden_id = ?
                        """,
                        (resultado["orden_id"],),
                    )
                    conexion.commit()
                finally:
                    conexion.close()
                order_delivery.procesar_entregas_pendientes()

        entrega = self._entrega(resultado["orden_id"])
        self.assertEqual(entrega[1:4], ("fallida", 6, 0))

    def test_queue_rejects_unmigrated_mysql_backend_explicitly(self):
        with patch.dict(os.environ, {"HERMES_USE_MYSQL": "true"}):
            with self.assertRaisesRegex(RuntimeError, "requiere SQLite"):
                order_delivery.crear_y_entregar(
                    tipo="MENSAJE",
                    payload={"titulo": "Aviso", "texto": "Prueba", "icono": "info"},
                    destino_tipo="todos",
                    destino_etiqueta=None,
                )

    def test_mysql_backend_keeps_admin_startup_available_without_queue_worker(self):
        with patch.dict(os.environ, {"HERMES_USE_MYSQL": "true"}):
            self.assertIsNone(order_delivery.iniciar_worker_ordenes())

    def test_network_uses_distinct_32_bit_ids_per_attempt(self):
        sock = MagicMock()
        sock.__enter__.return_value = sock
        sock.recv.return_value = b"OK"
        with (
            patch("admin.core.network.socket.socket", return_value=sock),
            patch(
                "admin.core.network.empacar_header",
                wraps=network.empacar_header,
            ) as empaquetar,
        ):
            first = network.enviar_orden_v2_a_uno(
                "192.0.2.10", 1, b"{}"
            )
            second = network.enviar_orden_v2_a_uno(
                "192.0.2.10", 1, b"{}"
            )

        order_ids = [call.args[2] for call in empaquetar.call_args_list]
        self.assertTrue(first["ok"] and second["ok"])
        self.assertNotEqual(order_ids[0], order_ids[1])
        self.assertTrue(all(1 <= order_id <= 0xFFFFFFFF for order_id in order_ids))

    def test_message_api_persists_and_reports_queue_counts(self):
        with patch(
            "admin.core.order_delivery.network.enviar_orden_v2_a_uno",
            return_value={
                "ip": "192.0.2.10",
                "ok": True,
                "conectado": True,
                "respuesta": "OK",
            },
        ):
            respuesta = app.test_client().post(
                "/api/mensajes",
                json={
                    "titulo": "Aviso",
                    "texto": "Prueba",
                    "icono": "info",
                },
            )

        datos = respuesta.get_json()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(datos["total"], 2)
        self.assertEqual(datos["exitosos"], 2)
        self.assertEqual(datos["encoladas"], 0)
        conexion = sqlite3.connect(self.ruta)
        try:
            self.assertEqual(
                conexion.execute("SELECT COUNT(*) FROM ordenes").fetchone()[0],
                1,
            )
            self.assertEqual(
                conexion.execute(
                    "SELECT COUNT(*) FROM entregas WHERE estado = 'confirmada'"
                ).fetchone()[0],
                2,
            )
        finally:
            conexion.close()

    def test_initial_attempt_covers_all_recipients_in_parallel(self):
        conexion = sqlite3.connect(self.ruta)
        try:
            conexion.executemany(
                """
                INSERT INTO clientes (nombre, ip, grupo_id)
                VALUES (?, ?, 1)
                """,
                [
                    (f"PC{numero}", f"192.0.2.{numero}")
                    for numero in range(12, 44)
                ],
            )
            conexion.commit()
        finally:
            conexion.close()

        def enviar_ok(ip, tipo, payload, *, timeout_total):
            del tipo, payload, timeout_total
            return {
                "ip": ip,
                "ok": True,
                "conectado": True,
                "respuesta": "OK",
            }

        with patch(
            "admin.core.order_delivery.network.enviar_orden_v2_a_uno",
            side_effect=enviar_ok,
        ) as enviar:
            resultado = order_delivery.crear_y_entregar(
                tipo="MENSAJE",
                payload={"titulo": "Aviso", "texto": "Prueba", "icono": "info"},
                destino_tipo="todos",
                destino_etiqueta=None,
            )

        resumen = order_delivery.respuesta_masiva(resultado)
        self.assertEqual(resumen["total"], 34)
        self.assertEqual(resumen["exitosos"], 34)
        self.assertEqual(resumen["encoladas"], 0)
        self.assertEqual(enviar.call_count, 34)

    def test_image_api_persists_reference_and_delivers_compressed_bytes(self):
        image_id = "e" * 32
        ruta_imagen = Path(self.directorio.name) / f"{image_id}.jpg"
        ruta_imagen.write_bytes(b"jpeg")
        with (
            patch(
                "admin.app.image_processing.buscar_imagen_comprimida",
                return_value=ruta_imagen,
            ),
            patch(
                "admin.core.orders.buscar_imagen_comprimida",
                return_value=ruta_imagen,
            ),
            patch(
                "admin.core.order_delivery.network.enviar_orden_v2_a_uno",
                return_value={
                    "ip": "192.0.2.10",
                    "ok": True,
                    "conectado": True,
                    "respuesta": "OK",
                },
            ) as enviar,
        ):
            respuesta = app.test_client().post(
                "/api/imagenes/enviar",
                json={
                    "image_id": image_id,
                    "tipo": "imagen",
                    "destino": "equipo",
                    "ip": "192.0.2.10",
                },
            )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.get_json()["exitosos"], 1)
        self.assertEqual(enviar.call_args.args[2], b"jpeg")
        conexion = sqlite3.connect(self.ruta)
        try:
            self.assertEqual(
                conexion.execute(
                    "SELECT image_id FROM ordenes"
                ).fetchone()[0],
                image_id,
            )
        finally:
            conexion.close()


if __name__ == "__main__":
    unittest.main()
