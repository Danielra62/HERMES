# =============================================================
#  HERMES — admin/core/clients.py
#  Gestión de la lista de PCs clientes
#
#  Las IPs se guardan en clientes.json en la raíz del proyecto.
#  Puede editarse manualmente o desde la interfaz del admin.
# =============================================================

import os
import json

# Ruta del archivo JSON — vive en la raíz del proyecto
ARCHIVO_CLIENTES = os.path.join(os.path.dirname(__file__), "..", "..", "clientes.json")
ARCHIVO_CLIENTES = os.path.normpath(ARCHIVO_CLIENTES)


def _leer_json() -> dict:
    """Lee el archivo JSON y retorna su contenido."""
    if not os.path.exists(ARCHIVO_CLIENTES):
        return {"clientes": []}
    with open(ARCHIVO_CLIENTES, "r") as f:
        return json.load(f)


def _escribir_json(data: dict):
    """Escribe el contenido en el archivo JSON con formato legible."""
    with open(ARCHIVO_CLIENTES, "w") as f:
        json.dump(data, f, indent=4)


def obtener_clientes() -> list[str]:
    """Retorna la lista de IPs registradas."""
    return _leer_json().get("clientes", [])


def agregar_cliente(ip: str) -> dict:
    """
    Agrega una IP a la lista.
    Retorna {"ok": True} o {"ok": False, "error": "..."}
    """
    ip = ip.strip()

    if not ip:
        return {"ok": False, "error": "La IP no puede estar vacía"}

    data = _leer_json()
    clientes = data.get("clientes", [])

    if ip in clientes:
        return {"ok": False, "error": f"{ip} ya está en la lista"}

    clientes.append(ip)
    data["clientes"] = clientes
    _escribir_json(data)

    return {"ok": True}


def eliminar_cliente(ip: str) -> dict:
    """
    Elimina una IP de la lista.
    Retorna {"ok": True} o {"ok": False, "error": "..."}
    """
    ip = ip.strip()
    data = _leer_json()
    clientes = data.get("clientes", [])

    if ip not in clientes:
        return {"ok": False, "error": f"{ip} no está en la lista"}

    clientes.remove(ip)
    data["clientes"] = clientes
    _escribir_json(data)

    return {"ok": True}


def limpiar_clientes() -> dict:
    """Elimina todas las IPs de la lista."""
    _escribir_json({"clientes": []})
    return {"ok": True}


def total_clientes() -> int:
    """Retorna la cantidad de clientes registrados."""
    return len(obtener_clientes())