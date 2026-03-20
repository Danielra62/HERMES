# 🪽 HERMES
### Sistema de Administración Remota en Red Local

> Hermes permite a un administrador controlar de forma centralizada los fondos de pantalla
> y enviar mensajes a todas las PCs de una red local, sin depender de internet.

---

## ¿Qué hace?

Desde una sola PC, el administrador puede:

- 🖼️ **Cambiar el fondo de pantalla** en todas las PCs de la red simultáneamente
- 💬 **Enviar mensajes emergentes** a todas las PCs o a una en específico
- 🖥️ **Gestionar la lista de clientes** (PCs conectadas) desde una interfaz gráfica

---

## Arquitectura

```
[Admin PC]
    │
    ├─── Copia imagen ──────────→  \\ADMIN-PC\wallpapers\  (carpeta compartida)
    │                                        ↑
    └─── Envía orden por socket ──→  [PC-101] [PC-102] [PC-103] ...
                                        └── Cada una lee la carpeta
                                            y aplica el cambio
```

La comunicación se hace por **sockets TCP** en la red local.
La imagen se distribuye a través de una **carpeta compartida en red** (sin depender de internet).

---

## Tecnologías

| Componente | Tecnología |
|---|---|
| Lógica de red | Python 3 + sockets |
| Interfaz del admin | PyWebView + HTML / CSS / JS |
| Mensajes emergentes | Windows MessageBox (ctypes) |
| Fondo de pantalla | Windows SystemParametersInfo (ctypes) |
| Distribución | PyInstaller (.exe) |

---

## Estructura del proyecto

```
HERMES/
│
├── admin/                  # Aplicación del administrador
│   ├── main.py             # Entry point, arranca PyWebView
│   ├── app.py              # Puente entre Python y el frontend JS
│   ├── core/
│   │   ├── network.py      # Envío de órdenes por socket
│   │   ├── wallpaper.py    # Publicar imagen en carpeta compartida
│   │   ├── messaging.py    # Construir y enviar mensajes
│   │   └── clients.py      # Gestión de la lista de PCs clientes
│   └── ui/
│       ├── index.html
│       ├── css/styles.css
│       └── js/
│           ├── app.js      # Lógica del frontend
│           └── api.js      # Llamadas a funciones Python
│
├── cliente/                # Script que corre en cada PC
│   ├── main.py             # Entry point, arranca el listener
│   └── core/
│       ├── listener.py     # Servidor de sockets, escucha órdenes
│       ├── wallpaper.py    # Aplica el fondo de pantalla
│       └── messaging.py    # Muestra el MessageBox
│
├── shared/
│   └── constants.py        # Puerto, comandos, configuración global
│
├── assets/                 # Íconos y recursos visuales
├── build/                  # Output de PyInstaller (auto-generado)
├── requirements.txt
└── README.md
```

---

## Protocolo de comunicación

Los mensajes entre admin y cliente son strings simples enviados por TCP:

| Orden | Formato | Descripción |
|---|---|---|
| Cambiar fondo | `CAMBIAR_FONDO` | El cliente lee la imagen de la carpeta compartida |
| Enviar mensaje | `MENSAJE\|titulo\|texto\|icono` | Muestra un MessageBox en el cliente |

**Íconos disponibles:** `info` · `alerta` · `error` · `pregunta`

---

## Cómo correr y probar en desarrollo

> [!WARNING]
> Dado que este sistema utiliza bibliotecas nativas de Windows (`ctypes.windll`, conectores a red de Windows `net use`), **el programa Cliente sólo puede ejecutarse en Windows**. Puedes probar el *Admin* en Linux interactuando con su interfaz, pero las copias de archivos por red dispararán un error a menos que lo levantes en Windows.

### 1. Instalar dependencias
Asegúrate de estar en un entorno virtual e instala los requerimientos:
```bash
pip install -r requirements.txt
```

*(Si pruebas el Admin en Linux, es posible que necesites las dependencias de webkit para PyWebView: `sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1`).*

### 2. Configuración Inicial Básica (Para pruebas)
Antes de nada, revisa `shared/constants.py` y asegúrate de que **IP_SERVIDOR**, **SERVIDOR_USUARIO**, etc., apunten a una ruta que realmente exista en tu red. 
Para tu primera prueba local, no necesitas tocar nada más que agregar tu IP local (ej. `127.0.0.1`) en la pestaña de "Clientes" del admin.

### 3. Correr la interfaz del Administrador
Abre una terminal en la raíz del proyecto y arranca la interfaz premium.
```bash
python admin/main.py
```

### 4. Correr el Cliente (Simples Pruebas)
En otra computadora **Windows** (o en la misma, para simulación pura de red, sabiendo que el cambio de Wallpaper aplicará a ti mismo):
```bash
python cliente/main.py
```

---

## Cómo compilar a `.exe`

```bash
# Admin (con interfaz gráfica)
pyinstaller --onefile --windowed --icon=assets/icon.ico admin/main.py

# Cliente (sin ventana, corre en segundo plano)
pyinstaller --onefile --noconsole --icon=assets/icon.ico cliente/main.py
```

Los ejecutables quedan en la carpeta `build/`.

---

## Configuración inicial

Antes de usar el sistema, editar `shared/constants.py`:

```python
PUERTO      = 5005          # Puerto TCP (debe ser el mismo en admin y cliente)
NOMBRE_IMG  = "wallpaper.jpg"
CARPETA_RED = r"\\ADMIN-PC\wallpapers"  # Ruta UNC de la carpeta compartida
```

También agregar las IPs de los clientes desde la interfaz del admin.

---

## Requisitos

- Windows 10 / 11 en las PCs clientes
- Python 3.10+ en desarrollo
- Red local (LAN) con acceso entre las PCs
- Carpeta compartida con permisos de lectura para todos los clientes

---

## Autores

Proyecto desarrollado internamente para administración de red local.

---

*El nombre Hermes viene del mensajero de los dioses griegos —
 porque este sistema entrega mensajes y cambia lo que se ve en pantalla.*
