# HERMES

Sistema de administracion remota para una red local. El administrador permite
enviar mensajes emergentes y cambiar el fondo de pantalla de los equipos
cliente mediante sockets TCP y una carpeta compartida de Windows.

## Estado actual

Version configurada en el proyecto: `0.1.0`.

Actualmente estan implementadas estas funciones:

- Interfaz grafica de escritorio con PyWebView.
- Dashboard con el total de clientes registrados.
- Registro, edicion y eliminacion de clientes.
- Organizacion de clientes por grupos.
- Creacion y eliminacion de grupos.
- Cambio de fondo para todos los clientes, un grupo o un equipo.
- Mensajes emergentes para todos los clientes, un grupo o un equipo.
- Persistencia de clientes y grupos en `clientes.json`.
- Envio paralelo de ordenes TCP y resumen de equipos exitosos y fallidos.

No hay autenticacion entre el administrador y los clientes. La aplicacion
debe ejecutarse en una red confiable y el puerto TCP debe estar permitido en el
firewall de los equipos cliente.

## Arquitectura

```text
[Administrador]
     |
     | TCP, puerto 5005
     v
[Clientes Windows]
     |
     | leen el fondo desde la carpeta compartida
     v
[Servidor SMB: \\172.16.20.196\Wallpapers]
```

El administrador copia la imagen seleccionada a la carpeta compartida con el
nombre `fondo.jpeg` y despues envia la orden `CAMBIAR_FONDO`. Cada cliente
construye la ruta de esa imagen y la aplica con `SystemParametersInfoW`.

## Estructura

```text
HERMES/
|
|-- admin/
|   |-- main.py              # Arranque de la interfaz PyWebView
|   |-- app.py               # API Python expuesta al frontend
|   |-- core/
|   |   |-- clients.py       # Clientes y grupos en clientes.json
|   |   |-- messaging.py     # Construccion de mensajes
|   |   |-- network.py       # Envio TCP paralelo
|   |   `-- wallpaper.py     # Conexion SMB y copia de imagenes
|   `-- ui/
|       |-- index.html
|       |-- css/styles.css
|       `-- js/
|           |-- api.js       # Wrapper de la API PyWebView
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
- WebView2 instalado para PyWebView en el equipo administrador.
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

Los clientes registrados actualmente estan en `clientes.json`, agrupados en:
`LABORATORIO1`, `LABORATORIO2` y `AULAS`. Tambien se pueden administrar desde
la vista **Clientes** de la interfaz.

## Ejecucion

Los comandos deben ejecutarse desde la raiz del proyecto y con el entorno
virtual activo.

### Administrador

```powershell
python -m admin.main
```

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
| Mensaje | `MENSAJE\|titulo\|texto\|icono` | Muestra un MessageBox de Windows. |

Iconos disponibles: `info`, `pregunta`, `alerta` y `error`.

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
- El cliente no ofrece una interfaz grafica; se ejecuta en segundo plano desde
  una terminal o mediante un ejecutable.
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