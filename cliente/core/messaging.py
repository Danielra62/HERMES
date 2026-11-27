import ctypes
import threading
from ctypes import wintypes

from shared.constants import ICONOS

MB_SETFOREGROUND = 0x00010000
MB_TOPMOST = 0x00040000
HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040


def _buscar_ventana_del_hilo(user32, thread_id: int, titulo: str):
    ventanas: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HWND,
        wintypes.LPARAM,
    )

    def revisar(hwnd: int, lparam: int) -> bool:
        del lparam
        longitud = user32.GetWindowTextLengthW(hwnd)
        texto = ctypes.create_unicode_buffer(longitud + 1)
        user32.GetWindowTextW(hwnd, texto, len(texto))
        if texto.value == titulo:
            ventanas.append(hwnd)
            return False
        return True

    user32.EnumThreadWindows(thread_id, callback_type(revisar), 0)
    return ventanas[0] if ventanas else None


def _mantener_mensaje_encima(
    thread_id: int,
    titulo: str,
    detener: threading.Event,
) -> None:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HWND,
        wintypes.LPARAM,
    )
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [
        wintypes.HWND,
        wintypes.LPWSTR,
        ctypes.c_int,
    ]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.EnumThreadWindows.argtypes = [
        wintypes.DWORD,
        callback_type,
        wintypes.LPARAM,
    ]
    user32.EnumThreadWindows.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL

    while not detener.is_set():
        hwnd = _buscar_ventana_del_hilo(user32, thread_id, titulo)
        if hwnd is not None:
            ctypes.set_last_error(0)
            aplicado = user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
            )
            if not aplicado:
                error = ctypes.get_last_error()
                print(
                    "[ERROR] No se pudo mantener el mensaje encima "
                    f"(SetWindowPos, error {error})"
                )
            return
        detener.wait(0.05)


def mostrar_mensaje(titulo, texto, icono):
    tipo = ICONOS.get(icono, 0x40)
    tipo |= MB_SETFOREGROUND | MB_TOPMOST

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.MessageBoxW.argtypes = [
        wintypes.HWND,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.UINT,
    ]
    user32.MessageBoxW.restype = ctypes.c_int
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD

    detener = threading.Event()
    thread_id = kernel32.GetCurrentThreadId()
    vigilante = threading.Thread(
        target=_mantener_mensaje_encima,
        args=(thread_id, titulo, detener),
        name="HermesMessageTopmost",
        daemon=True,
    )
    vigilante.start()
    try:
        user32.MessageBoxW(None, texto, titulo, tipo)
    finally:
        detener.set()
        vigilante.join(timeout=1)