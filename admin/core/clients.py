# =============================================================
#  HERMES — admin/core/clients.py
#  Gestión de clientes organizados por grupos
# =============================================================

import os
import json

ARCHIVO_CLIENTES = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "clientes.json")
)

GRUPOS_DEFAULT = ["LABORATORIO1", "LABORATORIO2", "AULAS"]


def _leer_json() -> dict:
    if not os.path.exists(ARCHIVO_CLIENTES):
        return {"grupos": {g: [] for g in GRUPOS_DEFAULT}}
    with open(ARCHIVO_CLIENTES, "r") as f:
        return json.load(f)


def _escribir_json(data: dict):
    with open(ARCHIVO_CLIENTES, "w") as f:
        json.dump(data, f, indent=4)


def obtener_grupos() -> dict:
    """Retorna todos los grupos con sus clientes."""
    return _leer_json().get("grupos", {})


def obtener_clientes() -> list[str]:
    """Retorna todas las IPs de todos los grupos (para envío masivo)."""
    grupos = _leer_json().get("grupos", {})
    return [c["ip"] for clientes in grupos.values() for c in clientes]


def total_clientes() -> int:
    return len(obtener_clientes())


def agregar_cliente(grupo: str, nombre: str, ip: str) -> dict:
    """Agrega un cliente (nombre+ip) a un grupo."""
    nombre, ip = nombre.strip(), ip.strip()
    if not nombre or not ip:
        return {"ok": False, "error": "El nombre y la IP no pueden estar vacíos"}

    data = _leer_json()
    grupos = data.setdefault("grupos", {g: [] for g in GRUPOS_DEFAULT})
    clientes = grupos.setdefault(grupo, [])

    if any(c["ip"] == ip for c in clientes):
        return {"ok": False, "error": f"{ip} ya está en {grupo}"}

    clientes.append({"nombre": nombre, "ip": ip})
    _escribir_json(data)
    return {"ok": True}


def eliminar_cliente(grupo: str, ip: str) -> dict:
    """Elimina un cliente por IP dentro de un grupo."""
    data = _leer_json()
    clientes = data.get("grupos", {}).get(grupo, [])
    nueva_lista = [c for c in clientes if c["ip"] != ip]

    if len(nueva_lista) == len(clientes):
        return {"ok": False, "error": f"{ip} no encontrado en {grupo}"}

    data["grupos"][grupo] = nueva_lista
    _escribir_json(data)
    return {"ok": True}


def editar_cliente(grupo: str, ip_original: str, nuevo_nombre: str, nueva_ip: str) -> dict:
    """Edita el nombre y/o IP de un cliente existente."""
    nuevo_nombre, nueva_ip = nuevo_nombre.strip(), nueva_ip.strip()
    if not nuevo_nombre or not nueva_ip:
        return {"ok": False, "error": "Nombre e IP no pueden estar vacíos"}

    data = _leer_json()
    clientes = data.get("grupos", {}).get(grupo, [])

    for c in clientes:
        if c["ip"] == ip_original:
            c["nombre"] = nuevo_nombre
            c["ip"] = nueva_ip
            _escribir_json(data)
            return {"ok": True}

    return {"ok": False, "error": f"{ip_original} no encontrado en {grupo}"}


def limpiar_clientes() -> dict:
    _escribir_json({"grupos": {g: [] for g in GRUPOS_DEFAULT}})
    return {"ok": True}

def agregar_grupo(nombre: str) -> dict:
    """Crea un nuevo grupo vacío."""
    nombre = nombre.strip().upper()
    if not nombre:
        return {"ok": False, "error": "El nombre del grupo no puede estar vacío"}

    data = _leer_json()
    grupos = data.setdefault("grupos", {})

    if nombre in grupos:
        return {"ok": False, "error": f"El grupo '{nombre}' ya existe"}

    grupos[nombre] = []
    _escribir_json(data)
    return {"ok": True, "nombre": nombre}


def eliminar_grupo(nombre: str) -> dict:
    """Elimina un grupo y todos sus clientes."""
    data = _leer_json()
    grupos = data.get("grupos", {})

    if nombre not in grupos:
        return {"ok": False, "error": f"El grupo '{nombre}' no existe"}

    del grupos[nombre]
    _escribir_json(data)
    return {"ok": True}