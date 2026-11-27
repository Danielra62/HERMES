# HERMES

Sistema de administracion remota para una red local. El administrador permite
enviar mensajes emergentes e imagenes, y cambiar el fondo de pantalla de los
equipos cliente mediante sockets TCP.

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
- Envio de imagenes y fondos por TCP v2 desde la interfaz web del admin.
- Persistencia de clientes y grupos en SQLite por defecto; MySQL/MariaDB sigue
  disponible como alternativa.
- Órdenes persistidas por destinatario con reintentos cuando un cliente vuelve
  a estar disponible.
- Envio paralelo de ordenes TCP y resumen de equipos exitosos y fallidos.

No hay autenticacion entre el administrador y los clientes. La aplicacion
debe ejecutarse en una red confiable y el puerto TCP debe estar permitido en el
firewall de los equipos cliente.

## Arquitectura

```text
[Administrador] -- TCP v2, puerto 5005 --> [Clientes Windows]
[Administrador] <-- HEARTBEAT v2, puerto 5006 -- [Clientes Windows]
```

Los mensajes, imagenes emergentes y cambios de fondo se envian por TCP. Los
fondos se transportan exclusivamente como payload binario mediante el protocolo
TCP v2; el cliente los guarda localmente y aplica el archivo local convertido
a BMP.

## Estructura

```text
HERMES/
|
|-- admin/
|   |-- main.py              # Servidor Flask y archivos estaticos
|   |-- app.py               # Endpoints HTTP del frontend
|   |-- core/
|   |   |-- clients.py       # Acceso SQLite/MySQL a clientes y grupos
|   |   |-- heartbeat_listener.py # Listener TCP v2 para disponibilidad
|   |   |-- image_processing.py # Validacion, compresion y almacenamiento
|   |   |-- messaging.py     # Construccion de mensajes
|   |   |-- network.py       # Envio TCP paralelo
|   |   `-- scheduler.py     # Sondeo periódico de clientes no disponibles
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
|       |-- heartbeat.py    # Heartbeats periódicos al admin aprendido
|       |-- listener.py     # Servidor TCP
|       |-- messaging.py     # MessageBox de Windows
|       `-- wallpaper.py     # Fondo de Windows
|
|-- shared/constants.py     # Puerto, comandos y version
|-- scripts/pruebas/         # Pruebas manuales de protocolo y red
|-- hermes.db                # Base de datos SQLite local
|-- requirements.txt
`-- README.md
```

## Requisitos

- Windows 10 u 11 para ejecutar el cliente.
- Python 3.12.x.
- Python instalado y un entorno virtual activo.
- Red local con conectividad entre administrador y clientes.
- SQLite se usa por defecto. Para MySQL/MariaDB, configurar el backend en `.env`.
- Puerto TCP `5005` permitido en los clientes.
- Puerto TCP `5006` permitido en el administrador para recibir heartbeats.

El administrador puede iniciarse en otros sistemas para probar la interfaz;
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

Revisa `shared/constants.py` antes de usar el sistema en la red real:

```python
PUERTO = 5005
TIMEOUT = 5
PUERTO_HEARTBEAT = 5006
```

No es necesario configurar la dirección del admin en cada cliente. Cuando el
cliente recibe una orden o sondeo en `5005`, aprende la IP de origen y empieza
a enviar heartbeats a esa IP en el puerto `5006`.

Los clientes y grupos se administran desde la vista **Clientes** y se guardan
en `hermes.db` por defecto. El backend MySQL/MariaDB es opcional.

## Ejecucion

Los comandos deben ejecutarse desde la raiz del proyecto y con el entorno
virtual activo.

### Administrador

```powershell
python -m admin.main
```

Luego abre `http://localhost:8080` en el navegador. Flask escucha en
`0.0.0.0:8080` para permitir el acceso desde otros equipos o contenedores.

### Administrador portable para Windows

Con PyInstaller instalado globalmente y las dependencias del proyecto en `venv`,
ejecuta desde la raíz:

```powershell
.\scripts\build_admin_portable.ps1
```

El script crea `HermesAdmin-portable` en el Escritorio o actualiza su programa
si ya existe, conservando `data\hermes.db`, `data\storage` e inventario. La
carpeta incluye un ejecutable PyInstaller `onedir`, un acceso directo con icono,
el código fuente de `admin`, `shared` y `scripts`, y una copia SQLite segura
de `hermes.db`.
El ejecutable usa `data\hermes.db` y `data\storage` junto a la aplicación; no
necesita Python instalado. La base incluida conserva los registros existentes
y `inventario_hermes.json`, si está en el Escritorio, se copia como referencia
pero no se importa automáticamente. No se incluye `.env`.

El acceso directo inicia la consola minimizada y abre automáticamente el
navegador predeterminado cuando Flask responde; si no se abre, visita
`http://127.0.0.1:8080`. Para acceder desde otros equipos, permite en el
firewall TCP `8080` (interfaz web) y `5006`
(heartbeats entrantes); el admin envía órdenes a los clientes por TCP `5005`.
La cola portable utiliza SQLite, aunque el código fuente conserve el backend
MySQL/MariaDB opcional.

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

El cliente inicia directamente el listener y escucha en `0.0.0.0:5005`. Debe
iniciarse en cada PC que vaya a recibir ordenes.

## Protocolo TCP

El administrador envia texto UTF-8. El cliente responde `OK` despues de
procesar una orden v1. El protocolo binario v2 se describe abajo.

El formato textual `MENSAJE|titulo|texto|icono` se conserva en el cliente para
compatibilidad con clientes anteriores, pero el administrador actual envia los
mensajes mediante el framing v2 descrito a continuacion. Los cambios de fondo
no tienen un camino textual: se envian exclusivamente como `CAMBIAR_FONDO`
v2 con payload binario.

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

El listener del administrador recibe `HEARTBEAT` (`4`) con payload vacío en
el puerto `5006`. La IP de origen se usa para marcar como disponible solo un
cliente que ya esté registrado; el admin responde `OK` incluso si la IP no
existe en la base de datos, sin crear un registro. El listener se inicia en un
hilo daemon junto con la aplicación Flask.

Al arrancar, el admin sondea inmediatamente a los clientes cuyo estado es
`no_disponible`, y repite el sondeo cada 30 minutos. La verificación es un
`HEARTBEAT` v2 enviado al puerto de órdenes `5005`; el cliente aprende la IP
remota del admin, confirma la verificación y comienza a enviar heartbeats
periódicos al puerto `5006`. El cliente escucha y responde a la verificación
aunque el admin no esté disponible para recibir su heartbeat posterior.

Con el admin activo, se puede enviar un heartbeat de prueba desde la misma PC:

```powershell
python -m scripts.pruebas.prueba_envio_heartbeat
```

Desde otra PC, indica la IP del servidor admin:

```powershell
python -m scripts.pruebas.prueba_envio_heartbeat --host 192.168.1.10
```

El listener recibe completamente el payload v2 con `recv_exact`. `MENSAJE`
viaja como JSON UTF-8. `IMAGEN` se valida y se guarda temporalmente; despues del ACK se
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
`admin/storage`; configura esa ruta como volumen persistente en Docker. La
vista Fondos de la interfaz usa estos endpoints.

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

## Migrar MariaDB a SQLite

El script `scripts/migrar_a_sqlite.py` clona las tablas base, columnas, claves
foraneas, índices y filas del esquema MariaDB configurado en `.env` a
`hermes.db` en la raíz del proyecto. La migración conserva los IDs y los
contadores `AUTO_INCREMENT`; traduce los tipos a afinidades compatibles con
SQLite y valida las relaciones antes de publicar el archivo.

Desde la raíz y con el entorno virtual activo:

```powershell
python -m scripts.migrar_a_sqlite
```

El script no sobrescribe un `hermes.db` existente. La base generada está
excluida de Git porque contiene datos locales de clientes. Esta operación crea
una copia para migración/inspección. El admin usa SQLite por defecto; MySQL/
MariaDB sigue disponible como opción para clientes y grupos mediante
`HERMES_USE_MYSQL=true`.

## Preparar el esquema de órdenes pendientes

Después de respaldar la base, migra el esquema SQLite existente desde la raíz:

```powershell
python -m scripts.migrar_cola_ordenes
```

La migración conserva un respaldo `hermes.db.pre-orders-<UTC>.bak`, reemplaza
la tabla legacy vacía `ordenes_pendientes` por `ordenes`, `entregas` e
`intentos`, y valida las claves foráneas. Si la tabla legacy contiene filas o
el esquema no está en el estado esperado, la migración se detiene sin borrarlas.
Este paso prepara el esquema que utiliza la cola de órdenes. Los endpoints
persisten cada orden antes del primer intento; los fallos de conexión se
reintentan en segundo plano y heartbeat/sondeo adelantan el envío. El worker
se inicia con `python -m admin.main`. Todos los destinatarios se intentan en
paralelo durante la petición; los reintentos se procesan en segundo plano, en
lotes de hasta 32 conexiones simultáneas. La política actual conserva MENSAJE e
IMAGEN con resultado incierto sin reintento automático; esos tipos y los fondos
sí reintentan fallos ocurridos antes de conectar, hasta seis intentos. Los
fondos también pueden reintentar un resultado incierto porque aplicar el mismo
fondo es idempotente. El TTL es de 7 días para fondos y 8 horas para MENSAJE e
IMAGEN. La cola solo está soportada con SQLite y un único proceso admin;
MySQL/MariaDB aún no tiene migración para este esquema. Con MySQL el admin
puede gestionar clientes/grupos, pero el worker queda deshabilitado y los
endpoints de órdenes informan que requieren SQLite.

Para una prueba local de red, registra `127.0.0.1` como cliente y ejecuta el
cliente en otra terminal. El cliente Windows puede recibir el fondo por TCP v2
sin depender de recursos compartidos de archivos.

## Estado conocido

- El cliente usa APIs de Windows (`ctypes.windll`) y no es portable a Linux o
  macOS.
- El cliente se ejecuta en segundo plano, pero muestra ventanas tkinter para
  imagenes recibidas por v2.
- El listener no registra clientes automaticamente: el administrador debe
  tener sus IPs registradas en `hermes.db`.
- El control de acceso y el cifrado de las ordenes aun no estan implementados.

## Instalador del cliente Windows

El cliente se empaqueta como aplicacion Windows independiente con PyInstaller;
no requiere Python instalado en los equipos destino. PyInstaller es una
herramienta de desarrollo y no se agrega a los requisitos de ejecucion del
proyecto. Inno Setup genera el instalador con desinstalador.

En la PC de desarrollo, instala Inno Setup 6 y PyInstaller fuera del entorno
virtual del proyecto. Luego, desde PowerShell en la raiz:

```powershell
.\installer\compilar_instalador.ps1
```

El instalador final se genera en `dist\instalador`. Durante la instalacion,
`HermesRegistro.exe` solicita un nombre, permite elegir una IPv4, pide las
credenciales SMB en campos protegidos, no las guarda y cierra la conexión
temporal al terminar. Registra el equipo en
`\\172.16.20.196\compartirV\pa Hermes\inventario_hermes.json`. El inventario
usa la forma `{"instalaciones": [...]}`; reinstalar una IP actualiza su entrada
y no elimina los demas equipos. Si el JSON existe pero no se puede leer o su
estructura no es valida, el archivo no se reemplaza y la instalacion muestra
que el registro quedó pendiente.

Al compilar una nueva version, se conserva el mismo `AppId` y se incrementa
`VERSION`. Ejecutar el nuevo instalador sobre una instalacion existente
actualiza los archivos en su carpeta previa y conserva la selección de inicio
automatico. El registro con `HermesRegistro.exe` vuelve a aparecer durante la
actualizacion; se puede cancelar sin desinstalar el cliente actualizado.

El instalador instala el cliente bajo `Program Files`, ofrece inicio
automatico al iniciar sesion para todos los usuarios y agrega un acceso directo
para reintentar el registro del inventario. La desinstalacion elimina el
programa y ese inicio automatico, pero no borra el inventario compartido. La
regla de firewall TCP 5005 debe configurarse conforme a las politicas de TI.