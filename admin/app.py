"""Endpoints HTTP del administrador HERMES."""

import ipaddress
import uuid

from flask import Blueprint, jsonify, request

from admin.core import clients, image_processing, messaging, network
from shared.constants import ICONOS
from shared.protocol import TipoOrden


api = Blueprint("api", __name__, url_prefix="/api")


def _datos_json() -> dict:
    return request.get_json(silent=True) or {}


@api.get("/clientes")
def get_clientes():
    return jsonify(clients.obtener_grupos())


@api.get("/clientes/total")
def get_total_clientes():
    return jsonify(clients.total_clientes())


@api.post("/clientes")
def add_cliente():
    datos = _datos_json()
    resultado = clients.agregar_cliente(
        datos.get("grupo", ""),
        datos.get("nombre", ""),
        datos.get("ip", ""),
    )
    return jsonify(resultado)


@api.delete("/clientes/<ip>")
def remove_cliente(ip):
    datos = _datos_json()
    grupo = datos.get("grupo", request.args.get("grupo", ""))
    return jsonify(clients.eliminar_cliente(grupo, ip))


@api.put("/clientes/<ip_original>")
def edit_cliente(ip_original):
    datos = _datos_json()
    resultado = clients.editar_cliente(
        datos.get("grupo", ""),
        ip_original,
        datos.get("nuevo_nombre", ""),
        datos.get("nueva_ip", ""),
    )
    return jsonify(resultado)


@api.post("/grupos")
def add_grupo():
    return jsonify(clients.agregar_grupo(_datos_json().get("nombre", "")))


@api.delete("/grupos/<nombre>")
def remove_grupo(nombre):
    return jsonify(clients.eliminar_grupo(nombre))


@api.get("/iconos")
def get_iconos():
    return jsonify(list(ICONOS.keys()))


@api.post("/mensajes")
def mensaje_todos():
    datos = _datos_json()
    titulo = datos.get("titulo", "")
    texto = datos.get("texto", "")
    icono = datos.get("icono", "info")
    if not titulo or not texto:
        return jsonify({
            "total": 0,
            "exitosos": 0,
            "fallidos": 0,
            "fallos": [{"ip": "local", "error": "Campos vacíos"}],
        })
    return jsonify(messaging.enviar_mensaje_todos(titulo, texto, icono))


@api.post("/mensajes/cliente")
def mensaje_uno():
    datos = _datos_json()
    return jsonify(messaging.enviar_mensaje_uno(
        datos.get("ip", ""),
        datos.get("titulo", ""),
        datos.get("texto", ""),
        datos.get("icono", "info"),
    ))


@api.post("/mensajes/grupo")
def mensaje_grupo():
    datos = _datos_json()
    titulo = datos.get("titulo", "")
    texto = datos.get("texto", "")
    if not titulo or not texto:
        return jsonify({
            "total": 0,
            "exitosos": 0,
            "fallidos": 0,
            "fallos": [{"ip": "local", "error": "Campos vacíos"}],
        })
    return jsonify(messaging.enviar_mensaje_grupo(
        datos.get("grupo", ""),
        titulo,
        texto,
        datos.get("icono", "info"),
    ))


@api.post("/imagenes/subir")
def subir_imagen_v2():
    archivo = request.files.get("imagen")
    if archivo is None or not archivo.filename:
        return jsonify({"ok": False, "error": "No se recibió una imagen"}), 400

    try:
        datos = archivo.stream.read(image_processing.MAX_UPLOAD_BYTES + 1)
        imagen_comprimida = image_processing.preparar_imagen(datos)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except OSError as exc:
        return jsonify({
            "ok": False,
            "error": f"No se pudo leer la imagen subida: {exc}",
        }), 400

    image_id = uuid.uuid4().hex
    try:
        image_processing.guardar_imagen_comprimida(imagen_comprimida, image_id)
    except OSError as exc:
        return jsonify({
            "ok": False,
            "error": f"No se pudo guardar la imagen comprimida: {exc}",
        }), 500
    return jsonify({"ok": True, "image_id": image_id})


@api.post("/imagenes/enviar")
def enviar_imagen_v2():
    datos = _datos_json()
    image_id = datos.get("image_id")
    tipo = datos.get("tipo")
    destino = datos.get("destino")
    if not isinstance(image_id, str):
        return jsonify({"ok": False, "error": "Falta el identificador de imagen"}), 400
    if tipo not in ("fondo", "imagen"):
        return jsonify({
            "ok": False,
            "error": "Tipo inválido. Usa 'fondo' o 'imagen'",
        }), 400
    if destino not in ("todos", "grupo", "equipo"):
        return jsonify({
            "ok": False,
            "error": "Destino inválido. Usa 'todos', 'grupo' o 'equipo'",
        }), 400

    grupo = datos.get("grupo")
    ip = datos.get("ip")
    if destino == "grupo" and (
        not isinstance(grupo, str) or not grupo.strip()
    ):
        return jsonify({"ok": False, "error": "Indica el grupo de destino"}), 400
    if destino == "equipo":
        if not isinstance(ip, str) or not ip.strip():
            return jsonify({"ok": False, "error": "Indica la IP del equipo"}), 400
        try:
            ipaddress.IPv4Address(ip.strip())
        except ValueError:
            return jsonify({"ok": False, "error": "La IP del equipo no es válida"}), 400

    ruta_imagen = image_processing.buscar_imagen_comprimida(image_id)
    if ruta_imagen is None:
        return jsonify({
            "ok": False,
            "error": "El identificador de imagen no existe",
        }), 404

    try:
        payload = ruta_imagen.read_bytes()
    except OSError as exc:
        return jsonify({
            "ok": False,
            "error": f"No se pudo leer la imagen almacenada: {exc}",
        }), 500

    if destino == "todos":
        ips = clients.obtener_clientes()
    elif destino == "grupo":
        grupos = clients.obtener_grupos()
        if grupo not in grupos:
            return jsonify({
                "ok": False,
                "error": f"El grupo '{grupo}' no existe",
            }), 404
        ips = [cliente["ip"] for cliente in grupos[grupo]]
    else:
        ips = [ip.strip()]

    tipo_orden = (
        TipoOrden.CAMBIAR_FONDO if tipo == "fondo" else TipoOrden.IMAGEN
    )
    resultados = network.enviar_payload_v2_a_lista(tipo_orden, payload, ips)
    return jsonify(network.resumen(resultados))