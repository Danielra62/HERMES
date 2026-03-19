import socket
from shared.constants import PUERTO, CMD_CAMBIAR_FONDO, CMD_MENSAJE

from cliente.core.wallpaper import cambiar_fondo
from cliente.core.messaging import mostrar_mensaje

HOST = "0.0.0.0"

def manejar_comando(data):
    print(f"[CMD] {data}")

    if data == CMD_CAMBIAR_FONDO:
        cambiar_fondo()

    elif data.startswith(CMD_MENSAJE):
        try:
            _, titulo, texto, icono = data.split("|")
            mostrar_mensaje(titulo, texto, icono)
        except Exception as e:
            print("[ERROR] Formato de mensaje inválido:", e)


def iniciar_listener():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PUERTO))
    server.listen()

    print(f"[LISTENER] Escuchando en {HOST}:{PUERTO}")

    while True:
        conn, addr = server.accept()
        print(f"[CONEXION] {addr}")

        try:
            data = conn.recv(1024).decode().strip()
            if data:
                manejar_comando(data)
                conn.sendall("OK".encode("utf-8"))
        except Exception as e:
            print("[ERROR] leyendo datos:", e)

        conn.close()