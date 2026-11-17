"""Registra el equipo instalado en el inventario compartido de HERMES."""

from __future__ import annotations

import ctypes
import ipaddress
import json
import os
import socket
import struct
import sys
import tempfile
import tkinter as tk
from ctypes import wintypes
from pathlib import Path
from tkinter import messagebox, ttk


GRUPO = "LABORATORIO1"
RUTA_COMPARTIDA = r"\\172.16.20.196\compartirV\pa Hermes"
NOMBRE_JSON = "inventario_hermes.json"
RECURSO_SMB = r"\\172.16.20.196\compartirV"

ERROR_INSUFFICIENT_BUFFER = 122
RESOURCETYPE_DISK = 1
CONNECT_TEMPORARY = 4


class _NetResource(ctypes.Structure):
    _fields_ = [
        ("dwScope", wintypes.DWORD),
        ("dwType", wintypes.DWORD),
        ("dwDisplayType", wintypes.DWORD),
        ("dwUsage", wintypes.DWORD),
        ("lpLocalName", wintypes.LPWSTR),
        ("lpRemoteName", wintypes.LPWSTR),
        ("lpComment", wintypes.LPWSTR),
        ("lpProvider", wintypes.LPWSTR),
    ]


class _MibIpAddrRow(ctypes.Structure):
    _fields_ = [
        ("dwAddr", wintypes.DWORD),
        ("dwIndex", wintypes.DWORD),
        ("dwMask", wintypes.DWORD),
        ("dwBCastAddr", wintypes.DWORD),
        ("dwReasmSize", wintypes.DWORD),
        ("unused1", wintypes.WORD),
        ("unused2", wintypes.WORD),
    ]


def listar_ipv4_locales() -> list[str]:
    """Enumera IPv4 configuradas en Windows sin depender de paquetes externos."""
    if sys.platform != "win32":
        candidatas = {
            resultado[4][0]
            for resultado in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
        }
    else:
        iphlpapi = ctypes.WinDLL("iphlpapi")
        obtener_tabla = iphlpapi.GetIpAddrTable
        obtener_tabla.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.ULONG),
            wintypes.BOOL,
        ]
        obtener_tabla.restype = wintypes.ULONG

        tamano = wintypes.ULONG()
        resultado = obtener_tabla(None, ctypes.byref(tamano), False)
        if resultado not in (0, ERROR_INSUFFICIENT_BUFFER):
            raise OSError(resultado, "No se pudieron consultar las IPv4 locales")

        buffer = ctypes.create_string_buffer(tamano.value)
        resultado = obtener_tabla(buffer, ctypes.byref(tamano), False)
        if resultado != 0:
            raise OSError(resultado, "No se pudieron consultar las IPv4 locales")

        cantidad = ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD)).contents.value
        inicio_filas = ctypes.addressof(buffer) + ctypes.sizeof(wintypes.DWORD)
        candidatas = set()
        for indice in range(cantidad):
            fila = _MibIpAddrRow.from_address(
                inicio_filas + indice * ctypes.sizeof(_MibIpAddrRow)
            )
            candidatas.add(socket.inet_ntoa(struct.pack("<I", fila.dwAddr)))

    resultado = []
    for texto in candidatas:
        direccion = ipaddress.ip_address(texto)
        if not (direccion.is_loopback or direccion.is_link_local or direccion.is_unspecified):
            resultado.append(str(direccion))
    return sorted(set(resultado), key=lambda valor: tuple(map(int, valor.split("."))))


def actualizar_inventario(
    ruta_json: str | os.PathLike[str],
    nombre: str,
    ip: str,
    grupo: str = GRUPO,
) -> None:
    """Agrega el equipo o actualiza la entrada de la misma IP sin perder datos."""
    ruta = Path(ruta_json)
    if ruta.exists():
        with ruta.open("r", encoding="utf-8-sig") as archivo:
            datos = json.load(archivo)
        if not isinstance(datos, dict):
            raise ValueError("El inventario existente debe ser un objeto JSON")
        instalaciones = datos.get("instalaciones")
        if not isinstance(instalaciones, list):
            raise ValueError(
                "El JSON existe, pero no tiene una lista 'instalaciones' válida. "
                "No se modificó el archivo."
            )
    else:
        datos = {"instalaciones": []}
        instalaciones = datos["instalaciones"]

    equipo = {"nombre": nombre, "ip": ip, "grupo": grupo}
    for indice, existente in enumerate(instalaciones):
        if not isinstance(existente, dict):
            raise ValueError(
                f"La entrada {indice + 1} del inventario no es un objeto JSON. "
                "No se modificó el archivo."
            )
        if existente.get("ip") == ip:
            instalaciones[indice] = {**existente, **equipo}
            break
    else:
        instalaciones.append(equipo)

    descriptor, ruta_temporal = tempfile.mkstemp(
        prefix=f".{NOMBRE_JSON}.",
        suffix=".tmp",
        dir=str(ruta.parent),
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as archivo:
            json.dump(datos, archivo, ensure_ascii=False, indent=2)
            archivo.write("\n")
            archivo.flush()
            os.fsync(archivo.fileno())
        os.replace(ruta_temporal, ruta)
    except Exception:
        try:
            os.remove(ruta_temporal)
        except FileNotFoundError:
            pass
        raise


def _conectar_smb(usuario: str, contrasena: str) -> None:
    recurso = _NetResource()
    recurso.dwType = RESOURCETYPE_DISK
    recurso.lpRemoteName = RECURSO_SMB

    mpr = ctypes.WinDLL("mpr")
    conectar = mpr.WNetAddConnection2W
    conectar.argtypes = [
        ctypes.POINTER(_NetResource),
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
    ]
    conectar.restype = wintypes.DWORD
    resultado = conectar(
        ctypes.byref(recurso),
        contrasena,
        usuario,
        CONNECT_TEMPORARY,
    )
    if resultado != 0:
        if resultado == 1219:
            raise OSError(
                resultado,
                "Windows ya tiene una conexión a este servidor con otras "
                "credenciales. Cierra esa conexión e inténtalo de nuevo.",
            )
        raise OSError(resultado, f"No se pudo conectar al recurso compartido (código {resultado})")


def _desconectar_smb() -> None:
    mpr = ctypes.WinDLL("mpr")
    desconectar = mpr.WNetCancelConnection2W
    desconectar.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL]
    desconectar.restype = wintypes.DWORD
    resultado = desconectar(RECURSO_SMB, 0, True)
    if resultado not in (0, 2250):
        raise OSError(resultado, f"No se pudo cerrar la conexión SMB (código {resultado})")


class RegistroInventario:
    def __init__(self, raiz: tk.Tk) -> None:
        self.raiz = raiz
        raiz.title("Registro del cliente HERMES")
        raiz.resizable(False, False)

        marco = ttk.Frame(raiz, padding=16)
        marco.grid(sticky="nsew")
        marco.columnconfigure(1, weight=1)

        ttk.Label(marco, text="Nombre del equipo:").grid(
            row=0, column=0, sticky="w", padx=(0, 10), pady=5
        )
        self.nombre = ttk.Entry(marco, width=36)
        self.nombre.grid(row=0, column=1, sticky="ew", pady=5)

        ttk.Label(marco, text="Dirección IPv4:").grid(
            row=1, column=0, sticky="w", padx=(0, 10), pady=5
        )
        self.ip = ttk.Combobox(marco, width=33, state="normal")
        self.ip.grid(row=1, column=1, sticky="ew", pady=5)
        try:
            ips = listar_ipv4_locales()
        except OSError as exc:
            ips = []
            messagebox.showwarning(
                "No se pudieron detectar las IP",
                f"Elige o escribe manualmente la IPv4 correcta.\n\n{exc}",
                parent=raiz,
            )
        self.ip["values"] = ips
        if ips:
            self.ip.current(0)

        ttk.Label(marco, text="Grupo:").grid(
            row=2, column=0, sticky="w", padx=(0, 10), pady=5
        )
        ttk.Label(marco, text=GRUPO).grid(row=2, column=1, sticky="w", pady=5)

        ttk.Separator(marco).grid(row=3, column=0, columnspan=2, sticky="ew", pady=10)
        ttk.Label(marco, text="Credenciales de la carpeta compartida").grid(
            row=4, column=0, columnspan=2, sticky="w", pady=5
        )
        ttk.Label(marco, text="Usuario:").grid(
            row=5, column=0, sticky="w", padx=(0, 10), pady=5
        )
        self.usuario = ttk.Entry(marco, width=36)
        self.usuario.grid(row=5, column=1, sticky="ew", pady=5)

        ttk.Label(marco, text="Contraseña:").grid(
            row=6, column=0, sticky="w", padx=(0, 10), pady=5
        )
        self.contrasena = ttk.Entry(marco, width=36, show="*")
        self.contrasena.grid(row=6, column=1, sticky="ew", pady=5)

        ttk.Label(
            marco,
            text=f"Se conservarán las demás entradas de {NOMBRE_JSON}.",
            wraplength=420,
        ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(8, 4))

        botones = ttk.Frame(marco)
        botones.grid(row=8, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(botones, text="Cancelar", command=self.cancelar).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(botones, text="Registrar", command=self.registrar).pack(
            side="right"
        )
        raiz.protocol("WM_DELETE_WINDOW", self.cancelar)

    def cancelar(self) -> None:
        self.raiz.destroy()
        raise SystemExit(1)

    def registrar(self) -> None:
        nombre = self.nombre.get().strip()
        ip = self.ip.get().strip()
        usuario = self.usuario.get().strip()
        contrasena = self.contrasena.get()
        if not nombre or not ip or not usuario or not contrasena:
            messagebox.showerror(
                "Faltan datos",
                "Completa el nombre, la IPv4 y las credenciales del recurso compartido.",
                parent=self.raiz,
            )
            return
        try:
            direccion = ipaddress.ip_address(ip)
            if (
                direccion.version != 4
                or direccion.is_loopback
                or direccion.is_link_local
                or direccion.is_unspecified
            ):
                raise ValueError("Selecciona una dirección IPv4 válida de la red.")
        except ValueError as exc:
            messagebox.showerror("IPv4 no válida", str(exc), parent=self.raiz)
            return

        ruta_json = os.path.join(RUTA_COMPARTIDA, NOMBRE_JSON)
        conectado = False
        try:
            _conectar_smb(usuario, contrasena)
            conectado = True
            actualizar_inventario(ruta_json, nombre, ip)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            messagebox.showerror(
                "No se pudo actualizar el inventario",
                f"{exc}\n\nNo se confirmó el registro del cliente. "
                "El archivo existente se conserva.",
                parent=self.raiz,
            )
            return
        finally:
            if conectado:
                try:
                    _desconectar_smb()
                except OSError as exc:
                    messagebox.showwarning(
                        "Aviso de conexión",
                        f"El inventario se actualizó, pero Windows no cerró la "
                        f"conexión SMB temporal:\n{exc}",
                        parent=self.raiz,
                    )

        self.contrasena.delete(0, tk.END)
        messagebox.showinfo(
            "Registro completado",
            f"{nombre} ({ip}) quedó registrado en el grupo {GRUPO}.",
            parent=self.raiz,
        )
        self.raiz.destroy()


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("El registro SMB está disponible únicamente en Windows.")
    raiz = tk.Tk()
    RegistroInventario(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    main()
