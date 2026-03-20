import os
import webview
from admin.app import Api

def main():
    # Instanciar nuestra clase API
    api = Api()
    
    # Construir la ruta absoluta al archivo index.html
    current_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(current_dir, "ui", "index.html")
    file_url = f"file://{html_path}"

    # Crear ventana de pywebview
    window = webview.create_window(
        title='HERMES Admin',
        url=file_url,
        js_api=api,
        width=1000,
        height=720,
        min_size=(800, 600)
    )
    
    # Proveer la ventana a la API para crear diálogos
    api._window = window
    
    # Inicializar aplicación
    webview.start(gui='edgechromium')

if __name__ == '__main__':
    main()