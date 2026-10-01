from flask import Flask, render_template

from admin.app import api


app = Flask(
    __name__,
    template_folder="ui",
    static_folder="ui",
    static_url_path="/static",
)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
app.register_blueprint(api)


@app.get("/")
def index():
    return render_template("index.html")


@app.errorhandler(413)
def archivo_demasiado_grande(_error):
    return {"ok": False, "error": "El archivo supera el máximo permitido de 32 MB"}, 413


def main():
    app.run(host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()