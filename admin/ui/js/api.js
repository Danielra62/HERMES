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
    addCliente: async (grupo, nombre, ip) => {
        return await window.pywebview.api.add_cliente(grupo, nombre, ip);
    },
    removeCliente: async (grupo, ip) => {
        return await window.pywebview.api.remove_cliente(grupo, ip);
    },
    editCliente: async (grupo, ipOriginal, nuevoNombre, nuevaIp) => {
        return await window.pywebview.api.edit_cliente(grupo, ipOriginal, nuevoNombre, nuevaIp);
    },
    addGrupo: async (nombre) => {
    return await window.pywebview.api.add_grupo(nombre);
    },
    removeGrupo: async (nombre) => {
        return await window.pywebview.api.remove_grupo(nombre);
    },

    // Wallpaper
    seleccionarImagen: async () => {
        return await window.pywebview.api.seleccionar_imagen();
    },
    cambiarFondo: async (ruta) => {
        return await window.pywebview.api.cambiar_fondo(ruta);
    },

    cambiarFondoGrupo: async (grupo, ruta) => {
        return await window.pywebview.api.cambiar_fondo_grupo(grupo, ruta);
    },
    cambiarFondoUno: async (ip, ruta) => {
        return await window.pywebview.api.cambiar_fondo_uno(ip, ruta);
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
    },
    mensajeGrupo: async (grupo, titulo, texto, icono) => {
        return await window.pywebview.api.mensaje_grupo(grupo, titulo, texto, icono);
    },
};

// Exportamos api globalmente en app.js no usamos módulos ES6
window.hermesApi = api;
