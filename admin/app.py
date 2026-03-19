import os
import webview
from admin.core import clients, wallpaper, messaging, network
from shared.constants import ICONOS, CMD_CAMBIAR_FONDO

class Api:
    def __init__(self):
        self._window = None

    def get_clientes(self):
        """Retorna la lista de IPs de los clientes."""
        return clients.obtener_clientes()

    def get_total_clientes(self):
        """Retorna la cantidad de clientes registrados."""
        return clients.total_clientes()

    def add_cliente(self, ip):
        """Añade un cliente a la lista."""
        return clients.agregar_cliente(ip)

    def remove_cliente(self, ip):
        """Elimina un cliente de la lista."""
        return clients.eliminar_cliente(ip)

    def seleccionar_imagen(self):
        """Abre un diálogo nativo para elegir una imagen."""
        if not self._window:
            return {"ok": False, "error": "Ventana no inicializada"}

        file_types = ('Imágenes (*.jpg;*.jpeg;*.png;*.bmp)', 'Todos los archivos (*.*)')
        result = self._window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=file_types)
        
        if result and len(result) > 0:
            return {"ok": True, "ruta": result[0]}
        
        return {"ok": False, "error": "Selección cancelada"}

    def cambiar_fondo(self, ruta_imagen):
        """
        1. Copia la imagen a la carpeta compartida.
        2. Si fue exitoso, envía el comando CMB_CAMBIAR_FONDO a todos los clientes.
        """
        # publicacion
        res_pub = wallpaper.publicar_wallpaper(ruta_imagen)
        if not res_pub.get("ok"):
            return {
                "publicacion": res_pub,
                "envio": None
            }
        
        # envio
        res_envio = network.enviar_a_todos(CMD_CAMBIAR_FONDO)
        resumen = network.resumen(res_envio)
        return {
            "publicacion": {"ok": True},
            "envio": resumen
        }

    def mensaje_todos(self, titulo, texto, icono):
        """Envía un mensaje emergente a todos los clientes."""
        if not titulo or not texto:
             return {"total": 0, "exitosos": 0, "fallidos": 0, "fallos": [{"ip": "local", "error": "Campos vacíos"}]}
        return messaging.enviar_mensaje_todos(titulo, texto, icono)

    def mensaje_uno(self, ip, titulo, texto, icono):
        """Envía un mensaje emergente a un cliente."""
        return messaging.enviar_mensaje_uno(ip, titulo, texto, icono)

    def get_iconos(self):
        """Retorna una lista con los nombres de íconos disponibles."""
        return list(ICONOS.keys())