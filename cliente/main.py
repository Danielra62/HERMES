from cliente.core.listener import iniciar_listener
from cliente.core.auth import conectar_recurso


def main():
    print("=== CLIENTE HERMES ===")

    if not conectar_recurso():
        print("[WARN] Iniciando sin acceso a SMB; el flujo antiguo de fondo no estará disponible")

    iniciar_listener()


if __name__ == "__main__":
    main()