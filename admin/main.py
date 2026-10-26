from flask import Flask, render_template

from admin.app import api
from admin.core.image_processing import MAX_UPLOAD_BYTES
from admin.core.heartbeat_listener import iniciar_listener_heartbeat


app = Flask(
    __name__,
    template_folder="ui",
    static_folder="ui",
    static_url_path="/static",
)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
app.register_blueprint(api)


@app.get("/")
def index():
    return render_template("index.html")


@app.errorhandler(413)
def archivo_demasiado_grande(_error):
    return {"ok": False, "error": "La solicitud supera el máximo permitido de 20 MB"}, 413


def main():
    iniciar_listener_heartbeat()
    app.run(host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()