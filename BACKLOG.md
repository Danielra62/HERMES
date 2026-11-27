# HERMES — Backlog del proyecto

Backlog consolidado a partir del tablero **Plan para migrar HERMES** y del estado
conocido del repositorio al 17 de noviembre de 2026. Los números identifican
épicas y tareas; no necesariamente indican el orden global de ejecución.

## Estado general

- **Completado:** base de datos, protocolo TCP v2, envío de mensajes, envío de
  imágenes y fondos por TCP, e interfaz web unificada.
- **Completado:** consolidar el transporte de fondos e imágenes en TCP v2.
- **Completado:** disponibilidad, heartbeat y sondeo periódico de clientes.
- **Pendiente:** cola persistente de órdenes, validación del instalador en el
  laboratorio, empaquetado del admin con Docker y pruebas integrales.

### Convenciones

- `[x]` Completado.
- `[ ]` Pendiente.
- `[~]` En curso.

## Épica 0 — Base técnica

- [x] **0.1 — Preparar MySQL/MariaDB para desarrollo.** Motor accesible para el
  equipo y configuración local documentada.
- [x] **0.2 — Definir el esquema de la base de datos.** Tablas para grupos,
  clientes y órdenes pendientes, con claves e índices.
- [x] **0.3 — Usar MySQL desde la capa de repositorio.** Conservar las funciones
  de acceso a grupos y clientes mientras se cambia el almacenamiento.
- [x] **0.4 — Migrar `clientes.json` a la base de datos.**
- [x] **0.5 — Definir el protocolo TCP v2.** Header fijo, tipos de orden,
  longitud, `order_id` y recepción exacta de bytes.
- [x] **0.6 — Migrar MENSAJE a TCP v2.**
- [x] **0.7 — Separar los requisitos del admin y del cliente.**
- [x] **0.0 — Corregir el arranque del cliente.** El listener TCP inicia
  directamente.

## Épica 1 — Imágenes y fondos por TCP

- [x] **1.1 — Hacer multihilo el listener del cliente.** Una ventana o conexión
  no bloquea la aceptación de órdenes nuevas.
- [x] **1.2 — Recibir y guardar payloads binarios.** El cliente lee el payload
  completo y lo guarda temporalmente.
- [x] **1.3 — Mostrar imágenes o aplicar fondos en el cliente.** Las imágenes se
  muestran en una ventana; los fondos se convierten y aplican desde una ruta
  local. Incluye validación, límites y limpieza de temporales.
- [x] **1.4 — Unificar la interfaz de envío de imágenes.** La vista permite
  enviar una imagen como fondo o ventana emergente a todos, un grupo o un equipo;
  muestra resultados y confirma la eliminación de grupos.
- [x] **1.5 — Enviar imágenes y fondos desde el admin por TCP v2.** Incluye
  validación/compresión de imágenes, almacenamiento local configurable y reporte
  por cliente.
- [x] **1.6 — Consolidar el transporte de fondos en TCP v2.** El cliente inicia
  directamente, el fondo se aplica desde un archivo local y el administrador
  solo conserva los endpoints de imagen/fondo binario v2.

## Épica 2 — Disponibilidad de clientes

- [x] **2.1 — Recibir heartbeats en el admin.** Listener v2 multihilo en el
  puerto dedicado `5006`; actualiza estado y última conexión de clientes
  registrados, ignora IPs desconocidas sin crear registros y confirma con ACK.
- [x] **2.2 — Enviar un ping desde el cliente al arrancar.** El cliente aprende
  la IP del admin al recibir una orden/sondeo en TCP y luego envía heartbeats
  periódicos sin configuración manual; el fallo no bloquea el listener.
- [~] **2.3 — Iniciar automáticamente el cliente desde el instalador Windows.**
  - El instalador ofrece el inicio al iniciar sesión para todos los usuarios,
    manteniendo el cliente en una sesión interactiva para mostrar ventanas.
  - Validar en un equipo de laboratorio la instalación, el inicio tras cerrar
    sesión/reiniciar y la eliminación del acceso de inicio al desinstalar.
  - No requiere el Programador de tareas de Windows.
- [x] **2.4 — Sondear clientes no disponibles periódicamente.** El admin hace
  un sondeo inmediato al arrancar y lo repite cada 30 minutos; marca disponibles
  a los que responden y usa actualizaciones SQL atómicas concurrentes con los
  heartbeats entrantes.

## Épica 3 — Cola de órdenes pendientes

- [x] **3.1 — Migrar el esquema y registrar órdenes persistentes por destinatario.**
  - En la revisión del 17-11-2026, `ordenes_pendientes` no tenía filas ni
    código consumidor, su FK `cliente_id` apuntaba a `clientes_migracion`
    (inexistente) y su valor por defecto de `estado` no coincidía con el
    `CHECK`. Se respaldó y migró la base SQLite; se conservaron los clientes y
    grupos y se verificó la integridad referencial.
  - Guardar la orden y una entrega por cada cliente destinatario antes del
    primer intento. Congelar los destinatarios de grupo/todos al crearla.
  - Conservar los datos necesarios para reconstruir la orden. Para imágenes y
    fondos, referenciar el `image_id` y conservar el archivo en `admin/storage`
    mientras existan entregas activas.
  - Usar estados de entrega `pendiente`, `enviando`, `confirmada`, `fallida`,
    `expirada` y `cancelada`; registrar los intentos de red por separado.
  - Implementados el comando de migración SQLite y el repositorio transaccional
    que crea una orden y sus entregas con los destinatarios congelados. La
    escritura quedó conectada al flujo de entrega en 3.2.
- [x] **3.2 — Entregar y reintentar órdenes al recuperar disponibilidad.**
  - Hacer un intento inmediato con límite total inicial propuesto de 10 s; los
    reintentos posteriores se ejecutan en segundo plano. La API conserva el
    patrón de respuesta actual y añade conteos de órdenes en cola e inciertas.
  - Activar el drenaje de la cola cuando heartbeat o sondeo confirmen un
    cliente; también recuperar y barrer pendientes al arrancar/periódicamente.
  - Reclamar entregas atómicamente, sin mantener transacciones abiertas durante
    operaciones de red, y recuperar entregas que queden `enviando` al reiniciar.
  - Un fallo antes de conectar es reintentable. Cualquier fallo después de
    conectar o iniciar el envío, incluido un error de `sendall`, es incierto.
    No reintentar automáticamente MENSAJE/IMAGEN inciertos; CAMBIAR_FONDO puede
    reintentarse porque aplicar el mismo fondo es idempotente.
  - El `order_id` enviado por TCP debe caber en el entero sin signo de 32 bits
    del header. Usar un ID distinto por intento en esta primera versión; no
    prometer entrega exactamente una vez ni deduplicación del lado cliente.
  - Valores iniciales: TTL de MENSAJE/IMAGEN 8 h,
    CAMBIAR_FONDO 7 días; reintentos tras 15 s, 1 min, 5 min, 15 min y 1 h,
    máximo 6 intentos; nueva orden de fondo cancela fondos anteriores
    pendientes del mismo equipo.
  - Las claves foráneas eliminan las entregas al borrar su cliente o su grupo.
    La advertencia de órdenes afectadas antes de borrar se incluye en 3.3.
  - Implementados el intento inmediato acotado a 10 s por equipo, el worker de
    reintentos, el drenaje por heartbeat/sondeo y la recuperación de envíos
    interrumpidos al arrancar. Todos los destinatarios se intentan en paralelo
    durante la petición; los intentos posteriores se procesan en lotes con un
    máximo de 32 conexiones simultáneas. Los intentos tienen IDs TCP distintos
    y las respuestas incluyen `encoladas` e `inciertas`. El worker se inicia
    desde `python -m admin.main`; la cola requiere SQLite y un solo proceso
    admin.
- [ ] **3.3 — Administrar órdenes pendientes desde la interfaz.**
  - Mostrar destinatario, tipo, fecha, estado, intentos y último error.
  - Permitir cancelar/eliminar una pendiente y reintentar manualmente una
    entrega fallida o incierta, advirtiendo que puede producirse un duplicado.
  - Advertir cuántas entregas pendientes serán eliminadas al borrar un
    cliente o un grupo.
  - Distinguir “confirmada por el cliente” de “vista por el usuario”; el ACK
    actual no garantiza que un popup haya sido visto.

## Épica 4 — Dockerización del admin

- [x] **4.1 — Convertir el admin a una aplicación web.** Flask sirve la interfaz
  y la API HTTP; se accede desde el navegador.
- [ ] **4.2 — Crear un Dockerfile para el admin.**
  - Instalar las dependencias y ejecutar la aplicación web en el contenedor.
  - Construir la imagen y comprobar que el admin responde.
- [ ] **4.3 — Desplegar el admin Dockerizado con almacenamiento persistente.**
  - Configurar el backend SQLite actual y persistir `hermes.db` en un volumen
    Docker; persistir también `admin/storage`.
  - No incluir MySQL/MariaDB, phpMyAdmin ni un servidor compartido de archivos
    salvo que una decisión posterior cambie el backend.
  - Publicar los puertos necesarios y documentar las reglas de firewall.
- [ ] **4.4 — Documentar el despliegue.**
  - Incluir puertos y reglas de firewall, variables de entorno y pasos para
    desplegar en un servidor desde cero.

## Épica 5 — Pruebas de Docker y red

- [ ] **5.1 — Probar la conectividad de un cliente Windows con el admin en LAN.**
  - Conectar desde un equipo Windows distinto del host Docker.
  - Registrar la dirección y los puertos que funcionen.
- [ ] **5.2 — Probar el envío de fondos e imágenes de extremo a extremo.**
  - Enviar desde el admin dockerizado a un cliente Windows real.
  - Comprobar integridad de los bytes y visualización correcta.
- [ ] **5.3 — Probar el ciclo de órdenes pendientes.**
  - Apagar o desconectar un cliente, enviarle una orden, restaurar su
    disponibilidad y verificar el reenvío automático.
- [ ] **5.4 — Probar el envío paralelo a los clientes registrados.**
  - Confirmar que todos reciben la orden y registrar el tiempo total.
- [ ] **5.5 — Automatizar las pruebas del despliegue.**
  - Agregar un servicio `test-runner` al Compose para ejecutar las pruebas de
    integración con un solo comando.

## Decisiones técnicas vigentes

- El admin se ejecuta como aplicación web; el cliente es un proceso Windows y no
  se incluye en Docker.
- El transporte final de imágenes y fondos es TCP v2.
- SQLite en `hermes.db` es el backend predeterminado del repositorio; MySQL
  permanece como opción mediante `HERMES_USE_MYSQL=true`.
- El esquema SQLite de órdenes ya está migrado y respaldado. El repositorio de
  persistencia existe, pero los endpoints aún no lo usan; eso corresponde a 3.2.
- El cliente inicia el listener TCP directamente.
- El admin usa un solo proceso para los listeners/schedulers actuales; revisar
  este supuesto antes de desplegar con varios workers web.
