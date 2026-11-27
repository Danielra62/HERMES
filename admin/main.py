import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

from flask import Flask, render_template

from admin.app import api
from admin.core.image_processing import MAX_UPLOAD_BYTES
from admin.core.heartbeat_listener import iniciar_listener_heartbeat
from admin.core.order_delivery import iniciar_worker_ordenes
from admin.core.scheduler import iniciar_scheduler


app = Flask(
    __name__,
    template_folder="ui",
    static_folder="ui",
    static_url_path="/static",
)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
app.register_blueprint(api)

URL_LOCAL = "http://127.0.0.1:8080"


@app.get("/")
def index():
    return render_template("index.html")


@app.errorhandler(413)
def archivo_demasiado_grande(_error):
    return {"ok": False, "error": "La solicitud supera el máximo permitido de 20 MB"}, 413


def _abrir_navegador_cuando_listo(timeout: float = 30) -> None:
    """Abre el dashboard cuando el servidor local ya responde."""
    limite = time.monotonic() + timeout
    ultimo_error: OSError | urllib.error.URLError | None = None
    while time.monotonic() < limite:
        try:
            with urllib.request.urlopen(f"{URL_LOCAL}/api/iconos", timeout=1) as respuesta:
                if respuesta.status == 200:
                    if not webbrowser.open(URL_LOCAL):
                        print("[ADMIN][WARN] No se pudo abrir el navegador predeterminado")
                    return
        except (OSError, urllib.error.URLError) as exc:
            ultimo_error = exc
        time.sleep(0.25)

    print(
        "[ADMIN][ERROR] El servidor no respondió; abre "
        f"{URL_LOCAL} manualmente. Último error: {ultimo_error}"
    )


def _iniciar_apertura_navegador() -> None:
    threading.Thread(
        target=_abrir_navegador_cuando_listo,
        name="HermesAdminBrowser",
        daemon=True,
    ).start()


def main():
    iniciar_listener_heartbeat()
    iniciar_scheduler()
    iniciar_worker_ordenes()
    if getattr(sys, "frozen", False):
        _iniciar_apertura_navegador()
    app.run(host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()