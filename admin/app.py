"""Endpoints HTTP del administrador HERMES."""

import os
import re
import tempfile
import uuid

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from admin.core import clients, messaging, network, wallpaper
from shared.constants import CMD_CAMBIAR_FONDO, ICONOS


api = Blueprint("api", __name__, url_prefix="/api")
CARPETA_SUBIDAS = os.path.join(tempfile.gettempdir(), "hermes-wallpaper-uploads")
EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".bmp"}
PATRON_ID_SUBIDA = re.compile(r"^[0-9a-f]{32}$")


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


@api.post("/fondo/subir")
def subir_fondo():
    archivo = request.files.get("imagen")
    if archivo is None or not archivo.filename:
        return jsonify({"ok": False, "error": "No se recibió una imagen"}), 400

    extension = os.path.splitext(secure_filename(archivo.filename))[1].lower()
    if extension not in EXTENSIONES_IMAGEN:
        return jsonify({"ok": False, "error": "Formato no soportado. Usa JPG, PNG o BMP"}), 400

    os.makedirs(CARPETA_SUBIDAS, exist_ok=True)
    upload_id = uuid.uuid4().hex
    archivo.save(os.path.join(CARPETA_SUBIDAS, upload_id + extension))
    return jsonify({"ok": True, "upload_id": upload_id})


def _ruta_subida(upload_id: str) -> str | None:
    if not PATRON_ID_SUBIDA.fullmatch(upload_id):
        return None
    for extension in EXTENSIONES_IMAGEN:
        ruta = os.path.join(CARPETA_SUBIDAS, upload_id + extension)
        if os.path.isfile(ruta):
            return ruta
    return None


def _aplicar_fondo(upload_id: str, destino: str, grupo: str = "", ip: str = "") -> dict:
    ruta_imagen = _ruta_subida(upload_id)
    if ruta_imagen is None:
        return {
            "publicacion": {"ok": False, "error": "La imagen subida no existe o ya expiró"},
            "envio": None,
        }

    try:
        resultado_publicacion = wallpaper.publicar_wallpaper(ruta_imagen)
        if not resultado_publicacion.get("ok"):
            return {"publicacion": resultado_publicacion, "envio": None}

        if destino == "todos":
            resultados = network.enviar_a_todos(CMD_CAMBIAR_FONDO)
        elif destino == "grupo":
            ips = [cliente["ip"] for cliente in clients.obtener_grupos().get(grupo, [])]
            resultados = network.enviar_a_lista(CMD_CAMBIAR_FONDO, ips)
        else:
            resultados = network.enviar_a_lista(CMD_CAMBIAR_FONDO, [ip])

        return {
            "publicacion": {"ok": True},
            "envio": network.resumen(resultados),
        }
    finally:
        try:
            os.remove(ruta_imagen)
        except OSError:
            pass


@api.post("/fondo")
def cambiar_fondo():
    return jsonify(_aplicar_fondo(_datos_json().get("upload_id", ""), "todos"))


@api.post("/fondo/grupo")
def cambiar_fondo_grupo():
    datos = _datos_json()
    return jsonify(_aplicar_fondo(
        datos.get("upload_id", ""),
        "grupo",
        grupo=datos.get("grupo", ""),
    ))


@api.post("/fondo/cliente")
def cambiar_fondo_uno():
    datos = _datos_json()
    return jsonify(_aplicar_fondo(
        datos.get("upload_id", ""),
        "uno",
        ip=datos.get("ip", ""),
    ))