# =============================================================
#  HERMES — Configuración global
#  Editar este archivo antes de desplegar en producción
# =============================================================

# ── Red ───────────────────────────────────────────────────────
PUERTO = 5005                        # Puerto TCP para comunicación admin ↔ cliente
TIMEOUT = 5                          # Segundos antes de considerar un cliente inaccesible

# ── Servidor de archivos ─────────────────────────────────────
# Servidor central donde se alojan imágenes, documentos e instaladores.
# IP estática — aquí también se guarda el wallpaper activo.
IP_SERVIDOR          = "172.16.20.196"
SERVIDOR_USUARIO     = "usuario"
SERVIDOR_PASSWORD    = "usuario"

# ── Carpeta compartida ────────────────────────────────────────
CARPETA_COMPARTIDA  = f"\\\\{IP_SERVIDOR}\\Wallpapers"
NOMBRE_IMAGEN       = "fondo.jpeg"

# ── Comandos (protocolo interno) ─────────────────────────────
CMD_CAMBIAR_FONDO = "CAMBIAR_FONDO"
CMD_MENSAJE       = "MENSAJE"        # Formato completo: "MENSAJE|titulo|texto|icono"

# ── Íconos disponibles para MessageBox ───────────────────────
ICONOS = {
    "info":      0x40,   # ℹ️  Información
    "pregunta":  0x20,   # ❓ Pregunta
    "alerta":    0x30,   # ⚠️  Advertencia
    "error":     0x10,   # ❌ Error
}

# ── Versión ───────────────────────────────────────────────────
VERSION = "0.1.0"
APP_NOMBRE = "Hermes"