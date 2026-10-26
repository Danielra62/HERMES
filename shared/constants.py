# =============================================================
#  HERMES — Configuración global
#  Editar este archivo antes de desplegar en producción
# =============================================================

# ── Red ───────────────────────────────────────────────────────
PUERTO = 5005                        # Puerto TCP para comunicación admin ↔ cliente
TIMEOUT = 5                          # Segundos antes de considerar un cliente inaccesible

# ── Comandos (protocolo interno) ─────────────────────────────
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