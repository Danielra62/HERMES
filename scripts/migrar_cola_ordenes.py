"""Migra el esquema SQLite de órdenes pendientes.

Uso desde la raíz del proyecto:
    python -m scripts.migrar_cola_ordenes
"""

from admin.core.clients import RUTA_SQLITE, _usar_mysql
from admin.core.order_schema import migrar_esquema_ordenes


def main() -> None:
    if _usar_mysql():
        raise RuntimeError(
            "La migración de la cola en esta fase está implementada para SQLite. "
            "Desactiva HERMES_USE_MYSQL o prepara la migración MySQL antes de usar "
            "la cola con ese backend."
        )

    respaldo = migrar_esquema_ordenes(RUTA_SQLITE)
    if respaldo is None:
        print("El esquema de órdenes ya está migrado y validado.")
    else:
        print(f"Migración de órdenes completada: {RUTA_SQLITE}")
        print(f"Respaldo previo conservado en: {respaldo}")


if __name__ == "__main__":
    main()
