import os
import webview
from admin.core import clients, wallpaper, messaging, network
from shared.constants import ICONOS, CMD_CAMBIAR_FONDO

class Api:
    def __init__(self):
        self._window = None

    def get_clientes(self):
        """Retorna todos los grupos con sus clientes."""
        return clients.obtener_grupos()

    def get_total_clientes(self):
        return clients.total_clientes()

    def add_cliente(self, grupo, nombre, ip):
        return clients.agregar_cliente(grupo, nombre, ip)

    def remove_cliente(self, grupo, ip):
        return clients.eliminar_cliente(grupo, ip)

    def edit_cliente(self, grupo, ip_original, nuevo_nombre, nueva_ip):
        return clients.editar_cliente(grupo, ip_original, nuevo_nombre, nueva_ip)

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
    
    def cambiar_fondo_grupo(self, grupo, ruta_imagen):
        """Copia la imagen y la envía solo a los clientes de un grupo."""
        res_pub = wallpaper.publicar_wallpaper(ruta_imagen)
        if not res_pub.get("ok"):
            return {"publicacion": res_pub, "envio": None}

        ips = [c["ip"] for c in clients.obtener_grupos().get(grupo, [])]
        res_envio = network.enviar_a_lista(CMD_CAMBIAR_FONDO, ips)
        return {"publicacion": {"ok": True}, "envio": network.resumen(res_envio)}

    def cambiar_fondo_uno(self, ip, ruta_imagen):
        """Copia la imagen y la envía a un solo cliente."""
        res_pub = wallpaper.publicar_wallpaper(ruta_imagen)
        if not res_pub.get("ok"):
            return {"publicacion": res_pub, "envio": None}

        res_envio = network.enviar_a_lista(CMD_CAMBIAR_FONDO, [ip])
        return {"publicacion": {"ok": True}, "envio": network.resumen(res_envio)}

    def mensaje_todos(self, titulo, texto, icono):
        """Envía un mensaje emergente a todos los clientes."""
        if not titulo or not texto:
             return {"total": 0, "exitosos": 0, "fallidos": 0, "fallos": [{"ip": "local", "error": "Campos vacíos"}]}
        return messaging.enviar_mensaje_todos(titulo, texto, icono)

    def mensaje_uno(self, ip, titulo, texto, icono):
        """Envía un mensaje emergente a un cliente."""
        return messaging.enviar_mensaje_uno(ip, titulo, texto, icono)
    
    def mensaje_grupo(self, grupo, titulo, texto, icono):
        """Envía un mensaje a todos los clientes de un grupo."""
        if not titulo or not texto:
            return {"total": 0, "exitosos": 0, "fallidos": 0, "fallos": [{"ip": "local", "error": "Campos vacíos"}]}
        return messaging.enviar_mensaje_grupo(grupo, titulo, texto, icono)

    def get_iconos(self):
        """Retorna una lista con los nombres de íconos disponibles."""
        return list(ICONOS.keys())
    def add_grupo(self, nombre):
        """Crea un nuevo grupo."""
        return clients.agregar_grupo(nombre)

    def remove_grupo(self, nombre):
        """Elimina un grupo y todos sus clientes."""
        return clients.eliminar_grupo(nombre)