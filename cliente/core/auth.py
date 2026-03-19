import os
from shared.constants import CARPETA_COMPARTIDA, SERVIDOR_USUARIO, SERVIDOR_PASSWORD

def conectar_recurso():
    comando = f'net use {CARPETA_COMPARTIDA} /user:{SERVIDOR_USUARIO} {SERVIDOR_PASSWORD}'
    resultado = os.system(comando)

    if resultado == 0:
        print("[OK] Conectado al recurso compartido")
        return True
    else:
        print("[ERROR] No se pudo conectar al recurso compartido")
        return False