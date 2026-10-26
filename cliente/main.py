import threading

from cliente.core.heartbeat import enviar_ping_disponibilidad
from cliente.core.listener import iniciar_listener


def main():
    print("=== CLIENTE HERMES ===")
    threading.Thread(
        target=enviar_ping_disponibilidad,
        name="HermesInitialHeartbeat",
        daemon=True,
    ).start()
    iniciar_listener()


if __name__ == "__main__":
    main()