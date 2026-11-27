"""Diagnostica el foco y el orden visual del cuadro de mensaje de HERMES."""

import argparse
import ctypes
import os
import sys
import threading
import time
from pathlib import Path
from ctypes import wintypes


if os.name != "nt":
    raise SystemExit("Esta prueba solo se puede ejecutar en Windows.")

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
if str(RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROYECTO))

from cliente.core import messaging


user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [
    wintypes.HWND,
    wintypes.LPWSTR,
    ctypes.c_int,
]
user32.GetWindowTextW.restype = ctypes.c_int
user32.EnumWindows.argtypes = [
    ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM),
    wintypes.LPARAM,
]
user32.EnumWindows.restype = wintypes.BOOL
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
get_window_long_ptr = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
get_window_long_ptr.argtypes = [wintypes.HWND, ctypes.c_int]
get_window_long_ptr.restype = ctypes.c_ssize_t

GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
TITULO = f"HERMES - Diagnostico primer plano ({os.getpid()})"


def _titulo_ventana(hwnd: int) -> str:
    longitud = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(longitud + 1)
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value


def _ventanas_en_orden() -> list[int]:
    ventanas: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def agregar(hwnd: int, lparam: int) -> bool:
        del lparam
        ventanas.append(hwnd)
        return True

    callback = callback_type(agregar)
    if not user32.EnumWindows(callback, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    return ventanas


def _describir_hwnd(hwnd: int) -> str:
    titulo = _titulo_ventana(hwnd) or "(sin título)"
    return f"0x{hwnd or 0:X} — {titulo}"


def _registrar_estado(hwnd_mensaje: int) -> None:
    ventanas = _ventanas_en_orden()
    hwnd_frente = user32.GetForegroundWindow()
    estilo = get_window_long_ptr(hwnd_mensaje, GWL_EXSTYLE)
    indice_mensaje = ventanas.index(hwnd_mensaje) if hwnd_mensaje in ventanas else None
    indice_frente = ventanas.index(hwnd_frente) if hwnd_frente in ventanas else None

    print(f"Ventana del mensaje: {_describir_hwnd(hwnd_mensaje)}")
    print(f"Ventana activa:      {_describir_hwnd(hwnd_frente)}")
    print(f"Estilo extendido:    0x{estilo:X}")
    print(f"WS_EX_TOPMOST:       {'Sí' if estilo & WS_EX_TOPMOST else 'No'}")
    print(f"Índice Z del mensaje: {indice_mensaje} (menor = más arriba)")
    print(f"Índice Z de la activa: {indice_frente} (menor = más arriba)")
    if indice_mensaje is not None and indice_frente is not None:
        posicion = "encima" if indice_mensaje < indice_frente else "detrás"
        print(f"Posición respecto a la ventana activa: {posicion}")


def _aplicar_topmost_sin_activar(hwnd: int) -> bool:
    ctypes.set_last_error(0)
    resultado = bool(
        user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )
    )
    codigo_error = ctypes.get_last_error()
    print(
        "SetWindowPos(HWND_TOPMOST, SWP_NOACTIVATE): "
        f"{'éxito' if resultado else f'falló (error {codigo_error})'}"
    )
    return resultado


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--aplicar-topmost",
        action="store_true",
        help="Prueba colocar el cuadro encima sin quitar el foco a otra ventana.",
    )
    args = parser.parse_args()

    print("Prueba el cuadro de mensaje real de cliente.core.messaging.")
    print(f"Módulo cargado: {messaging.__file__}")
    print(
        "Flags solicitados: "
        f"MB_SETFOREGROUND=0x{messaging.MB_SETFOREGROUND:X}, "
        f"MB_TOPMOST=0x{messaging.MB_TOPMOST:X}"
    )
    print("En los próximos 8 segundos, deja al frente Word, Explorer o el navegador.")
    print("No vuelvas a hacer clic en la terminal hasta cerrar el mensaje.")
    for segundos in range(8, 0, -1):
        print(f"El mensaje aparecerá en {segundos}...")
        time.sleep(1)

    hilo_mensaje = threading.Thread(
        target=messaging.mostrar_mensaje,
        args=(
            TITULO,
            "Prueba de foco y estilo topmost de HERMES.",
            "info",
        ),
        name="HermesForegroundProbe",
        daemon=True,
    )
    hilo_mensaje.start()

    limite = time.monotonic() + 10
    estado_registrado = False
    while hilo_mensaje.is_alive() and time.monotonic() < limite:
        ventanas = _ventanas_en_orden()
        hwnd_mensaje = next(
            (hwnd for hwnd in ventanas if _titulo_ventana(hwnd) == TITULO),
            None,
        )
        if hwnd_mensaje is not None:
            for muestra in range(1, 4):
                time.sleep(0.5)
                ventanas = _ventanas_en_orden()
                hwnd_mensaje = next(
                    (hwnd for hwnd in ventanas if _titulo_ventana(hwnd) == TITULO),
                    None,
                )
                if hwnd_mensaje is None:
                    break
                print(f"\nEstado del cuadro ({muestra}/3):")
                _registrar_estado(hwnd_mensaje)
                estado_registrado = True
            break
        time.sleep(0.1)

    if not estado_registrado:
        if hilo_mensaje.is_alive():
            print("No se encontró el cuadro por título durante los primeros 10 s.")
            print("Déjalo abierto; la llamada sigue esperando a que lo cierres.")
        else:
            print("El cuadro se cerró antes de poder registrar su estado.")

    if args.aplicar_topmost and estado_registrado and hilo_mensaje.is_alive():
        if hwnd_mensaje is not None and _aplicar_topmost_sin_activar(hwnd_mensaje):
            time.sleep(0.5)
            ventanas = _ventanas_en_orden()
            hwnd_mensaje = next(
                (hwnd for hwnd in ventanas if _titulo_ventana(hwnd) == TITULO),
                None,
            )
            if hwnd_mensaje is not None:
                print("\nEstado tras SetWindowPos:")
                _registrar_estado(hwnd_mensaje)

    hilo_mensaje.join()
    print("Prueba terminada.")


if __name__ == "__main__":
    main()
