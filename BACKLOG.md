# HERMES — Backlog del proyecto

Backlog consolidado a partir del tablero **Plan para migrar HERMES** y del estado
conocido del repositorio al 26 de octubre de 2026. Los números identifican épicas
y tareas; no necesariamente indican el orden global de ejecución.

## Estado general

- **Completado:** base de datos, protocolo TCP v2, envío de mensajes, envío de
  imágenes y fondos por TCP, e interfaz web unificada.
- **Completado:** consolidar el transporte de fondos e imágenes en TCP v2.
- **Pendiente:** disponibilidad/heartbeat, cola de órdenes pendientes,
  empaquetado del admin con Docker y pruebas integrales del despliegue.

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

- [ ] **2.1 — Recibir heartbeats en el admin.**
  - Definir si se usa un puerto dedicado o un tipo de orden en el protocolo v2.
  - Escuchar pings y marcar como disponible al cliente conocido, registrando la
    hora de última conexión.
  - Ignorar IPs no registradas; no crear clientes automáticamente.
- [ ] **2.2 — Enviar un ping desde el cliente al arrancar.**
  - Avisar al admin que el cliente está disponible.
  - Un fallo o ausencia del admin no debe impedir que arranque el listener.
- [ ] **2.3 — Iniciar el cliente mediante el Programador de tareas de Windows.**
  - Ejecutarlo al iniciar sesión del usuario, no como tarea sin sesión
    interactiva, para que las ventanas puedan mostrarse.
  - Probar el arranque automático después de reiniciar Windows.
  - Depende también de 1.6: el cliente debe funcionar sin carpeta de red.
- [ ] **2.4 — Sondear clientes no disponibles periódicamente.**
  - Cada 30 minutos, comprobar los clientes marcados como no disponibles.
  - Actualizar el estado de los que respondan y evitar conflictos concurrentes
    con el listener de heartbeats.

## Épica 3 — Cola de órdenes pendientes

- [ ] **3.1 — Registrar órdenes fallidas.**
  - Si falla el envío a un cliente, guardar en `ordenes_pendientes` el
    destinatario, tipo, datos necesarios para reconstruir la orden y estado.
  - Usar los estados `pendiente`, `enviada` y `fallida`.
- [ ] **3.2 — Reenviar órdenes al recuperar disponibilidad.**
  - Cuando un cliente vuelva a estar disponible, buscar órdenes pendientes
    dirigidas a él o a sus grupos y reenviarlas por TCP.
  - Marcar como enviada si tiene éxito; si falla, conservarla como pendiente.
  - Evitar que dos ejecuciones reenvíen la misma orden simultáneamente.
- [ ] **3.3 — Administrar órdenes pendientes desde la interfaz.**
  - Mostrar destinatario, tipo y fecha de creación.
  - Permitir eliminar una orden que ya no deba enviarse.

## Épica 4 — Dockerización del admin

- [x] **4.1 — Convertir el admin a una aplicación web.** Flask sirve la interfaz
  y la API HTTP; se accede desde el navegador.
- [ ] **4.2 — Crear un Dockerfile para el admin.**
  - Instalar las dependencias y ejecutar la aplicación web en el contenedor.
  - Construir la imagen y comprobar que el admin responde.
- [ ] **4.3 — Orquestar admin, MySQL/MariaDB y phpMyAdmin.**
  - Definir los servicios en `docker-compose.yml` y conectarlos en una red
    interna.
  - Configurar el admin para conectar por nombre de servicio.
  - Persistir los datos de la base de datos y publicar los puertos necesarios.
  - No incluir un servidor compartido de archivos.
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
- La base de datos es MySQL/MariaDB. `ordenes_pendientes` existe en el esquema,
  pero aún falta implementar su escritura y procesamiento.
- El cliente inicia el listener TCP directamente.
