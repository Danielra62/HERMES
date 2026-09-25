"""
migrar_json_a_bd.py

Migra clientes.json (grupos + clientes) a la base de datos MySQL 'hermes',
reusando la capa de repositorio de 0.3 (admin/core/clients.py) en vez de
hacer SQL directo. Así el script también sirve como primera prueba real
de que esa capa funciona.

Corresponde a la tarjeta 0.4 del backlog. Debe correrse UNA VEZ contra
la base de desarrollo, después de que 0.2 (schema) y 0.3 (repositorio)
estén listos.

Se asume que agregar_grupo() y agregar_cliente() devuelven un dict con
una convención de éxito/error (ej. {"ok": True, ...} o {"error": "..."}).
Si tu convención real es distinta, ajusta es_exitoso() más abajo -- el
script imprime el dict completo en cada paso para que sea fácil verificar.

USO (desde la raíz del proyecto, con el venv activo):
    python migrar_json_a_bd.py [--ruta-json clientes.json]
"""

import argparse
import json
import sys
from pathlib import Path

# Ajusta este import si el módulo vive en otra ruta dentro del proyecto.
from admin.core import clients


def cargar_json(ruta: Path) -> dict:
    if not ruta.exists():
        print(f"ERROR: no se encontró el archivo {ruta}")
        sys.exit(1)
    with ruta.open("r", encoding="utf-8") as f:
        return json.load(f)


def es_exitoso(resultado: dict) -> bool:
    """
    Heurística para detectar éxito/error en los dict que devuelve clients.py.
    Cubre las convenciones más comunes: {"ok": True/False} o {"error": "..."}.
    Ajusta esto si tu convención real es otra.
    """
    if "error" in resultado:
        return False
    if "ok" in resultado:
        return bool(resultado["ok"])
    # Si no hay ninguna de las dos claves, asumimos éxito por defecto.
    return True


def migrar(datos: dict) -> tuple[int, int, list[str]]:
    """
    Inserta grupos y clientes vía la capa de repositorio.
    Devuelve (grupos_ok, clientes_ok, errores).
    """
    grupos_ok = 0
    clientes_ok = 0
    errores = []

    grupos = datos.get("grupos", {})

    for nombre_grupo, lista_clientes in grupos.items():
        resultado = clients.agregar_grupo(nombre_grupo)
        print(f"  agregar_grupo({nombre_grupo!r}) -> {resultado}")

        if not es_exitoso(resultado):
            errores.append(f"Grupo '{nombre_grupo}': {resultado}")
            print(f"    SALTADO: no se pudieron agregar sus clientes.")
            continue

        grupos_ok += 1

        for cliente in lista_clientes:
            resultado_c = clients.agregar_cliente(
                grupo=nombre_grupo,
                nombre=cliente["nombre"],
                ip=cliente["ip"],
            )
            print(f"    agregar_cliente({cliente['nombre']!r}, {cliente['ip']!r}) -> {resultado_c}")

            if es_exitoso(resultado_c):
                clientes_ok += 1
            else:
                errores.append(f"Cliente '{cliente['nombre']}' ({cliente['ip']}): {resultado_c}")

    return grupos_ok, clientes_ok, errores


def main():
    parser = argparse.ArgumentParser(description="Migra clientes.json a MySQL vía admin.core.clients")
    parser.add_argument(
        "--ruta-json",
        default="clientes.json",
        help="Ruta al archivo clientes.json (default: clientes.json en la raíz)",
    )
    args = parser.parse_args()

    ruta = Path(args.ruta_json)
    print(f"Leyendo {ruta}...")
    datos = cargar_json(ruta)

    total_json_grupos = len(datos.get("grupos", {}))
    total_json_clientes = sum(len(c) for c in datos.get("grupos", {}).values())
    print(f"Encontrados en JSON: {total_json_grupos} grupos, {total_json_clientes} clientes\n")

    print("Iniciando migración vía admin.core.clients...\n")
    grupos_ok, clientes_ok, errores = migrar(datos)

    print(f"\nMigración terminada: {grupos_ok}/{total_json_grupos} grupos, "
          f"{clientes_ok}/{total_json_clientes} clientes insertados con éxito.")

    if errores:
        print(f"\n{len(errores)} error(es) durante la migración:")
        for e in errores:
            print(f"  - {e}")
        print(
            "\nSi los errores son por duplicados, probablemente el script "
            "ya se corrió antes. Revisa con verificar_migracion.py antes "
            "de volver a intentarlo."
        )
        sys.exit(1)
    else:
        print("Sin errores. ✔")


if __name__ == "__main__":
    main()