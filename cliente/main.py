from cliente.core.listener import iniciar_listener
from cliente.core.auth import conectar_recurso

def main():
    print("=== CLIENTE HERMES ===")

    # 🔐 Conectar al recurso compartido al iniciar
    conectado = conectar_recurso()

    if not conectado:
        print("[WARN] Continuando sin acceso a carpeta compartida")
        while True:
            if conectar_recurso():
                break
            print("Reintentando en 5s...")
            time.sleep(5)
    # 📡 Iniciar listener
    iniciar_listener()


if __name__ == "__main__":
    main()