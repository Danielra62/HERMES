import json
import os
import queue
import socket
import tempfile
import threading
import time
import ctypes
import tkinter as tk
from ctypes import wintypes
from dataclasses import dataclass, field
from tkinter import ttk

from PIL import Image, ImageTk

from shared.constants import PUERTO, CMD_CAMBIAR_FONDO, CMD_MENSAJE
from shared.constants import TIMEOUT
from shared.protocol import VERSION_PROTOCOLO, TipoOrden, recibir_orden

from cliente.core.wallpaper import aplicar_fondo, cambiar_fondo
from cliente.core.messaging import mostrar_mensaje

HOST = "0.0.0.0"
CARPETA_IMAGENES_TEMP = os.path.join(tempfile.gettempdir(), "HermesTemp")
RUTA_FONDO_ACTUAL = os.path.join(CARPETA_IMAGENES_TEMP, "fondo_actual.bmp")
_LOCK_FONDO = threading.Lock()
_LOCK_INTERFAZ = threading.Lock()
_HILO_INTERFAZ: threading.Thread | None = None
_INTERFAZ_LISTA = threading.Event()
MAX_PIXELES = 40_000_000


@dataclass
class _ImagenEncolada:
    ruta: str
    confirmada: threading.Event = field(default_factory=threading.Event)
    mostrar: bool = False


_COLA_IMAGENES: queue.Queue[_ImagenEncolada] = queue.Queue()


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


def manejar_orden_v2(tipo_orden, payload) -> tuple[str, str, str]:
    """Valida y extrae los campos de una orden MENSAJE v2."""
    if tipo_orden != TipoOrden.MENSAJE:
        raise ValueError(f"Tipo de orden v2 no soportado: {tipo_orden}")

    mensaje = json.loads(payload.decode("utf-8"))
    titulo = mensaje["titulo"]
    texto = mensaje["texto"]
    icono = mensaje["icono"]
    print(f"[CMD v2] MENSAJE: {titulo}")
    return titulo, texto, icono


def _guardar_imagen(order_id: int, payload: bytes) -> str:
    """Guarda el payload binario con un nombre derivado del ID de orden."""
    os.makedirs(CARPETA_IMAGENES_TEMP, exist_ok=True)
    ruta = os.path.join(CARPETA_IMAGENES_TEMP, f"hermes_imagen_{order_id}.bin")
    archivo = open(ruta, "xb")
    try:
        with archivo:
            escritos = archivo.write(payload)
            if escritos != len(payload):
                raise OSError(
                    f"Escritura incompleta: {escritos} de {len(payload)} bytes"
                )
            archivo.flush()
            os.fsync(archivo.fileno())
    except Exception:
        _eliminar_archivo(ruta)
        raise
    return ruta


def _eliminar_archivo(ruta: str) -> None:
    try:
        os.remove(ruta)
    except FileNotFoundError:
        pass
    except OSError as exc:
        print(f"[ERROR] No se pudo borrar {ruta}: {exc}")


def limpiar_temporales(max_edad_dias: int = 7) -> None:
    """Elimina únicamente payloads de imagen antiguos, nunca el fondo persistente."""
    limite = time.time() - max_edad_dias * 24 * 60 * 60
    try:
        rutas = [
            os.path.join(CARPETA_IMAGENES_TEMP, nombre)
            for nombre in os.listdir(CARPETA_IMAGENES_TEMP)
            if nombre.startswith("hermes_imagen_") and nombre.endswith(".bin")
        ]
    except FileNotFoundError:
        return
    except OSError as exc:
        print(f"[ERROR] No se pudo revisar {CARPETA_IMAGENES_TEMP}: {exc}")
        return

    for ruta in rutas:
        try:
            if os.path.isfile(ruta) and os.path.getmtime(ruta) < limite:
                os.remove(ruta)
                print(f"[TEMP] Eliminado payload antiguo: {ruta}")
        except OSError as exc:
            print(f"[ERROR] No se pudo limpiar {ruta}: {exc}")


def _comprobar_pixeles(imagen: Image.Image) -> None:
    ancho, alto = imagen.size
    if ancho * alto > MAX_PIXELES:
        raise ValueError(
            f"La imagen excede el limite de {MAX_PIXELES} pixeles: "
            f"{ancho}x{alto}"
        )


def _validar_imagen(ruta: str) -> None:
    with Image.open(ruta) as imagen:
        _comprobar_pixeles(imagen)
        imagen.verify()
    with Image.open(ruta) as imagen:
        imagen.load()


def _aplicar_fondo_v2(ruta_imagen: str, order_id: int) -> float:
    """Convierte y aplica el fondo persistente; retorna la duración en segundos."""
    ruta_temporal = os.path.join(
        CARPETA_IMAGENES_TEMP,
        f"fondo_actual_{order_id}.tmp",
    )
    inicio = time.perf_counter()
    try:
        with Image.open(ruta_imagen) as imagen:
            _comprobar_pixeles(imagen)
            imagen.load()
            imagen.convert("RGB").save(ruta_temporal, format="BMP")
        os.replace(ruta_temporal, RUTA_FONDO_ACTUAL)
        if not aplicar_fondo(RUTA_FONDO_ACTUAL):
            raise OSError("SystemParametersInfoW no pudo aplicar el fondo")
    finally:
        _eliminar_archivo(ruta_temporal)

    duracion = time.perf_counter() - inicio
    limite = f"{TIMEOUT} s"
    estado = "supera" if duracion > TIMEOUT else "queda dentro de"
    print(
        f"[FONDO v2] Conversión + aplicación: {duracion:.3f} s "
        f"({estado} {limite})"
    )
    return duracion


def _cerrar_ventana_imagen(ventana: tk.Toplevel, ruta: str) -> None:
    try:
        ventana.destroy()
    finally:
        _eliminar_archivo(ruta)


def _traer_ventana_al_frente(ventana: tk.Toplevel) -> None:
    ventana.attributes("-topmost", True)
    ventana.lift()
    ventana.focus_force()

    if os.name != "nt":
        return

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.AttachThreadInput.argtypes = [
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.BOOL,
    ]
    user32.AttachThreadInput.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD

    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    hwnd = user32.GetAncestor(wintypes.HWND(ventana.winfo_id()), 2)
    hwnd_frente = user32.GetForegroundWindow()
    if hwnd_frente == hwnd:
        return

    id_hilo_frente = user32.GetWindowThreadProcessId(hwnd_frente, None)
    id_hilo_actual = kernel32.GetCurrentThreadId()
    conectado = False
    if hwnd_frente and id_hilo_frente != id_hilo_actual:
        conectado = bool(
            user32.AttachThreadInput(id_hilo_actual, id_hilo_frente, True)
        )

    try:
        if (
            not user32.SetForegroundWindow(hwnd)
            and user32.GetForegroundWindow() != hwnd
        ):
            print("[WARN] Windows no permitió traer la ventana al frente")
    finally:
        if conectado:
            user32.AttachThreadInput(id_hilo_actual, id_hilo_frente, False)


def _mostrar_imagen(raiz: tk.Tk, ruta: str) -> None:
    try:
        with Image.open(ruta) as imagen:
            imagen.load()
            imagen.thumbnail(
                (
                    int(raiz.winfo_screenwidth() * 0.87),
                    int(raiz.winfo_screenheight() * 0.82),
                ),
                Image.Resampling.LANCZOS,
            )
            foto = ImageTk.PhotoImage(imagen, master=raiz)

        ventana = tk.Toplevel(raiz)
        ventana.title("HERMES")
        ventana.configure(background="black")
        etiqueta = ttk.Label(ventana, image=foto)
        etiqueta.image = foto
        etiqueta.pack()
        ventana.update_idletasks()
        x = max(0, (ventana.winfo_screenwidth() - ventana.winfo_width()) // 2)
        y = max(0, (ventana.winfo_screenheight() - ventana.winfo_height()) // 2)
        ventana.geometry(f"+{x}+{y}")

        cerrar = lambda _evento=None: _cerrar_ventana_imagen(ventana, ruta)
        ventana.protocol("WM_DELETE_WINDOW", cerrar)
        ventana.bind("<Button-1>", cerrar)
        ventana.bind("<Escape>", cerrar)
        _traer_ventana_al_frente(ventana)
    except Exception as exc:
        print(f"[ERROR] No se pudo mostrar {ruta}: {exc}")
        _eliminar_archivo(ruta)


def _procesar_cola_imagenes(raiz: tk.Tk) -> None:
    try:
        while True:
            try:
                imagen = _COLA_IMAGENES.get_nowait()
            except queue.Empty:
                break
            if imagen.confirmada.wait(timeout=5):
                if imagen.mostrar:
                    _mostrar_imagen(raiz, imagen.ruta)
            else:
                _eliminar_archivo(imagen.ruta)
    finally:
        raiz.after(100, _procesar_cola_imagenes, raiz)


def _asegurar_interfaz_lista(timeout: float = 2) -> bool:
    global _HILO_INTERFAZ
    with _LOCK_INTERFAZ:
        if _HILO_INTERFAZ is None or not _HILO_INTERFAZ.is_alive():
            _INTERFAZ_LISTA.clear()

            def ejecutar_interfaz() -> None:
                try:
                    raiz = tk.Tk()
                    raiz.withdraw()
                    raiz.after(100, _procesar_cola_imagenes, raiz)
                    _INTERFAZ_LISTA.set()
                    raiz.mainloop()
                except Exception as exc:
                    print(f"[ERROR] Falló el hilo de interfaz: {exc}")
                finally:
                    _INTERFAZ_LISTA.clear()

            _HILO_INTERFAZ = threading.Thread(
                target=ejecutar_interfaz,
                name="HermesTkInterface",
                daemon=True,
            )
            _HILO_INTERFAZ.start()

        hilo = _HILO_INTERFAZ

    if not _INTERFAZ_LISTA.wait(timeout=timeout):
        print(f"[ERROR] Interfaz tkinter no lista después de {timeout:.1f} s")
        return False

    with _LOCK_INTERFAZ:
        return (
            hilo is _HILO_INTERFAZ
            and hilo.is_alive()
            and _INTERFAZ_LISTA.is_set()
        )


def _manejar_conexion(conn):
    try:
        primer_byte = conn.recv(1, socket.MSG_PEEK)
        if primer_byte == bytes([VERSION_PROTOCOLO]):
            tipo_orden, order_id, payload = recibir_orden(conn)
            print(f"[ORDEN v2] id={order_id}")
            limpiar_temporales()
            if tipo_orden in (TipoOrden.IMAGEN, TipoOrden.CAMBIAR_FONDO):
                ruta_imagen = _guardar_imagen(order_id, payload)
                if tipo_orden == TipoOrden.IMAGEN:
                    entregado_a_interfaz = False
                    try:
                        _validar_imagen(ruta_imagen)
                        if not _asegurar_interfaz_lista(timeout=2):
                            raise RuntimeError(
                                "El hilo de interfaz no está disponible"
                            )
                        imagen = _ImagenEncolada(ruta_imagen)
                        with _LOCK_INTERFAZ:
                            if (
                                _HILO_INTERFAZ is None
                                or not _HILO_INTERFAZ.is_alive()
                                or not _INTERFAZ_LISTA.is_set()
                            ):
                                raise RuntimeError(
                                    "El hilo de interfaz dejó de estar listo"
                                )
                            _COLA_IMAGENES.put(imagen)
                            try:
                                conn.sendall(b"OK")
                            except Exception:
                                imagen.confirmada.set()
                                raise
                            imagen.mostrar = True
                            entregado_a_interfaz = True
                            imagen.confirmada.set()
                        print(
                            f"[IMAGEN] Recibida y encolada "
                            f"({len(payload)} bytes)"
                        )
                    except Exception as exc:
                        print(f"[ERROR] No se pudo aceptar la imagen: {exc}")
                        raise
                    finally:
                        if not entregado_a_interfaz:
                            _eliminar_archivo(ruta_imagen)
                else:
                    try:
                        with _LOCK_FONDO:
                            _aplicar_fondo_v2(ruta_imagen, order_id)
                        conn.sendall(b"OK")
                    finally:
                        _eliminar_archivo(ruta_imagen)
            elif tipo_orden == TipoOrden.MENSAJE:
                titulo, texto, icono = manejar_orden_v2(tipo_orden, payload)
                conn.sendall(b"OK")
                threading.Thread(
                    target=mostrar_mensaje,
                    args=(titulo, texto, icono),
                    daemon=True,
                ).start()
            else:
                raise ValueError(f"Tipo de orden v2 no soportado: {tipo_orden}")
        else:
            data = conn.recv(1024).decode().strip()
            if data:
                manejar_comando(data)
                conn.sendall("OK".encode("utf-8"))
    except Exception as e:
        print("[ERROR] leyendo datos:", e)
    finally:
        conn.close()


def iniciar_listener():
    limpiar_temporales()
    _asegurar_interfaz_lista()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PUERTO))
    server.listen()

    print(f"[LISTENER] Escuchando en {HOST}:{PUERTO}")

    while True:
        conn, addr = server.accept()
        print(f"[CONEXION] {addr}")

        threading.Thread(
            target=_manejar_conexion,
            args=(conn,),
            daemon=True,
        ).start()
