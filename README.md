# HERMES

Sistema de administracion remota para una red local. El administrador permite
enviar mensajes emergentes y cambiar el fondo de pantalla de los equipos
cliente mediante sockets TCP y una carpeta compartida de Windows.

## Estado actual

Version configurada en el proyecto: `0.1.0`.

Actualmente estan implementadas estas funciones:

- Interfaz web servida por Flask en el puerto `8080`.
- Dashboard con el total de clientes registrados.
- Registro, edicion y eliminacion de clientes.
- Organizacion de clientes por grupos.
- Creacion y eliminacion de grupos.
- Cambio de fondo para todos los clientes, un grupo o un equipo.
- Mensajes emergentes para todos los clientes, un grupo o un equipo.
- Envio de imagenes y fondos por TCP v2 desde los endpoints backend del admin;
  la interfaz web para esos endpoints queda pendiente.
- Persistencia de clientes y grupos en MySQL/MariaDB.
- Envio paralelo de ordenes TCP y resumen de equipos exitosos y fallidos.

No hay autenticacion entre el administrador y los clientes. La aplicacion
debe ejecutarse en una red confiable y el puerto TCP debe estar permitido en el
firewall de los equipos cliente.

## Arquitectura

```text
[Administrador] -- TCP v1/v2, puerto 5005 --> [Clientes Windows]
      |
      +-- SMB (solo fondo v1 antiguo) --> [Servidor SMB]
                                              ^
                                              | lectura del fondo v1
                                       [Clientes Windows]
```

El flujo antiguo del administrador copia la imagen seleccionada a la carpeta
compartida como `fondo.jpeg` y envia `CAMBIAR_FONDO` por v1. Los endpoints
backend v2 comprimen las imagenes en el admin y envian sus bytes directamente
al listener del cliente por TCP; la interfaz web todavia usa el flujo antiguo
hasta integrar estos endpoints en la tarjeta 1.4.

## Estructura

```text
HERMES/
|
|-- admin/
|   |-- main.py              # Servidor Flask y archivos estaticos
|   |-- app.py               # Endpoints HTTP del frontend
|   |-- core/
|   |   |-- clients.py       # Acceso MySQL a clientes y grupos
|   |   |-- image_processing.py # Validacion, compresion y almacenamiento
|   |   |-- messaging.py     # Construccion de mensajes
|   |   |-- network.py       # Envio TCP paralelo
|   |   `-- wallpaper.py     # Conexion SMB y copia de imagenes
|   `-- ui/
|       |-- index.html
|       |-- css/styles.css
|       `-- js/
|           |-- api.js       # Cliente fetch para la API HTTP
|           `-- app.js       # Logica de la interfaz
|
|-- cliente/
|   |-- main.py              # Arranque del cliente
|   `-- core/
|       |-- auth.py          # Conexion con net use
|       |-- listener.py      # Servidor TCP
|       |-- messaging.py     # MessageBox de Windows
|       `-- wallpaper.py     # Fondo de Windows
|
|-- shared/constants.py     # Puerto, ruta SMB, comandos y version
|-- clientes.json            # Clientes y grupos registrados
|-- requirements.txt
`-- README.md
```

## Requisitos

- Windows 10 u 11 para ejecutar el cliente.
- Python 3.10 o posterior.
- Python instalado y un entorno virtual activo.
- Red local con conectividad entre administrador y clientes.
- MySQL/MariaDB disponible y configurado en `.env`.
- Carpeta compartida `Wallpapers` con permisos de lectura para los clientes y
  permisos de escritura para el administrador.
- Puerto TCP `5005` permitido en los clientes.

El administrador puede iniciarse en otros sistemas para probar la interfaz.
En Linux, la publicacion del fondo se simula y no copia el archivo realmente;
las conexiones TCP a los clientes siguen siendo reales.

## Instalacion

Desde la raiz del proyecto:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Si PowerShell bloquea la activacion del entorno para esta terminal, se puede
usar:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1
```

## Configuracion

Editar `shared/constants.py` antes de usar el sistema en la red real:

```python
PUERTO = 5005
TIMEOUT = 5
IP_SERVIDOR = "172.16.20.196"
SERVIDOR_USUARIO = "usuario"
SERVIDOR_PASSWORD = "usuario"
CARPETA_COMPARTIDA = r"\\172.16.20.196\Wallpapers"
NOMBRE_IMAGEN = "fondo.jpeg"
```

La configuracion actual contiene credenciales de ejemplo en texto plano.
Deben reemplazarse antes de desplegar el sistema.

Los clientes y grupos se administran desde la vista **Clientes** y se guardan
en la base de datos `hermes`.

## Ejecucion

Los comandos deben ejecutarse desde la raiz del proyecto y con el entorno
virtual activo.

### Administrador

```powershell
python -m admin.main
```

Luego abre `http://localhost:8080` en el navegador. Flask escucha en
`0.0.0.0:8080` para permitir el acceso desde otros equipos o contenedores.

La interfaz tiene estas vistas:

- **Dashboard**: total de equipos registrados.
- **Fondos**: seleccion de imagen y destino masivo, por grupo o individual.
- **Mensajes**: titulo, texto, icono y destino del mensaje.
- **Clientes**: gestion de equipos y grupos.

### Cliente

En cada PC cliente Windows:

```powershell
python -m cliente.main
```

El cliente intenta conectar la carpeta compartida con `net use` y despues
escucha en `0.0.0.0:5005`. Debe iniciarse en cada PC que vaya a recibir
ordenes.

## Protocolo TCP

El administrador envia texto UTF-8. El cliente responde `OK` despues de
procesar una orden.

| Orden | Formato | Accion |
|---|---|---|
| Cambio de fondo | `CAMBIAR_FONDO` | Aplica `\\servidor\Wallpapers\fondo.jpeg`. |

El formato textual `MENSAJE|titulo|texto|icono` se conserva en el cliente para
compatibilidad v1, pero el administrador actual ya envia los mensajes mediante
el framing v2 descrito a continuacion.

Iconos disponibles: `info`, `pregunta`, `alerta` y `error`.

## Protocolo TCP v2

El modulo compartido `shared/protocol.py` define el framing binario. El header
tiene tamaño fijo de 10 bytes y usa
el formato `!BBII` (orden de bytes de red):

| Campo | Tamaño en bytes | Tipo | Descripcion |
|---|---:|---|---|
| `version` | 1 | unsigned byte | Version del formato binario del header; actualmente `1`, independiente de la etiqueta de migracion `v2`. |
| `tipo_orden` | 1 | unsigned byte | Codigo numerico del tipo de orden. |
| `order_id` | 4 | unsigned int | Identificador de la orden. |
| `longitud_payload` | 4 | unsigned int | Cantidad de bytes que siguen al header. |

Los tipos definidos son `MENSAJE` (`1`), `CAMBIAR_FONDO` (`2`), `IMAGEN`
(`3`) y `HEARTBEAT` (`4`). El payload se transporta como bytes; cada tipo de
orden determina si quien lo recibe lo interpreta como JSON UTF-8 o como bytes
crudos.

El listener distingue v1 de v2 inspeccionando el primer byte de cada conexion
y recibe completamente el payload v2 con `recv_exact`. `MENSAJE` viaja como
JSON UTF-8. `IMAGEN` se valida y se guarda temporalmente; despues del ACK se
muestra en una ventana y el archivo temporal se elimina al cerrarla.
`CAMBIAR_FONDO` v2 se guarda temporalmente, se convierte a
`%LOCALAPPDATA%\Temp\HermesTemp\fondo_actual.bmp` y se aplica con
`SystemParametersInfoW`; el ACK se envia solo si se aplico. El BMP se conserva
porque Windows mantiene su ruta. Los payloads `hermes_imagen_*.bin` de mas de
siete dias se limpian al arrancar el listener y al recibir ordenes v2.

El backend del admin expone `POST /api/imagenes/subir` (multipart, campo
`imagen`) para validar y comprimir una foto, y `POST /api/imagenes/enviar`
para enviar el `image_id` resultante. Este ultimo recibe `tipo` (`fondo` o
`imagen`) y `destino` (`todos`, `grupo` con `grupo`, o `equipo` con `ip`).
Los JPEG comprimidos se guardan en `HERMES_STORAGE_DIR`, que por defecto es
`admin/storage`; configura esa ruta como volumen persistente en Docker. El
endpoint existente `POST /api/fondo/subir` y los endpoints v1 de fondo siguen
disponibles hasta la tarjeta 1.6. Estos endpoints nuevos aun no estan
conectados a la interfaz web.

```powershell
python -m scripts.pruebas.prueba_envio_imagen_v2 --tipo imagen --archivo "C:\ruta\foto.jpg"
python -m scripts.pruebas.prueba_envio_imagen_v2 --tipo fondo --archivo "C:\ruta\foto.jpg"
```

## Pruebas rapidas

Comprobar imports y sintaxis desde la raiz:

```powershell
python -c "import admin.main; import cliente.main; print('entry points: OK')"
python -m compileall -q admin cliente shared
```

Para una prueba local de red, registra `127.0.0.1` como cliente y ejecuta el
cliente en otra terminal. El cambio de fondo solo funcionara si la carpeta
compartida configurada es accesible y el cliente es Windows.

## Estado conocido

- El cliente usa APIs de Windows (`ctypes.windll`) y no es portable a Linux o
  macOS.
- La copia del fondo depende de SMB, credenciales validas y permisos de red.
- El cliente se ejecuta en segundo plano, pero muestra ventanas tkinter para
  imagenes recibidas por v2.
- El listener no registra clientes automaticamente: el administrador debe
  tener sus IPs en `clientes.json`.
- El flujo de reintento de conexion del cliente cuando falla `net use` esta
  pendiente de ajuste antes de usarlo en un despliegue real.
- El control de acceso y el cifrado de las ordenes aun no estan implementados.

## Compilacion

PyInstaller puede generar los ejecutables desde la raiz:

```powershell
pyinstaller --onefile --windowed --name HermesAdmin admin/main.py
pyinstaller --onefile --noconsole --name HermesCliente cliente/main.py
```

Los archivos generados aparecen en `dist/`. Antes de distribuirlos, verifica
la configuracion de red, las credenciales SMB y las reglas del firewall.