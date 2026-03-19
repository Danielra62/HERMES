/**
 * HERMES - Wrapper de la API Python a JS
 * Todas las llamadas a pywebview.api se encapsulan aquí.
 */

const api = {
    // Clientes
    getClientes: async () => {
        return await window.pywebview.api.get_clientes();
    },
    getTotalClientes: async () => {
        return await window.pywebview.api.get_total_clientes();
    },
    addCliente: async (ip) => {
        return await window.pywebview.api.add_cliente(ip);
    },
    removeCliente: async (ip) => {
        return await window.pywebview.api.remove_cliente(ip);
    },

    // Wallpaper
    seleccionarImagen: async () => {
        return await window.pywebview.api.seleccionar_imagen();
    },
    cambiarFondo: async (ruta) => {
        return await window.pywebview.api.cambiar_fondo(ruta);
    },

    // Mensajes
    mensajeTodos: async (titulo, texto, icono) => {
        return await window.pywebview.api.mensaje_todos(titulo, texto, icono);
    },
    mensajeUno: async (ip, titulo, texto, icono) => {
        return await window.pywebview.api.mensaje_uno(ip, titulo, texto, icono);
    },
    getIconos: async () => {
        return await window.pywebview.api.get_iconos();
    }
};

// Exportamos api globalmente en app.js no usamos módulos ES6
window.hermesApi = api;
