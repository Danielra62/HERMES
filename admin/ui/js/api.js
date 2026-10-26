/** HERMES - cliente HTTP para la API Flask. */

async function requestJSON(url, options = {}) {
    const response = await fetch(url, options);
    let resultado;
    try {
        resultado = await response.json();
    } catch {
        resultado = {};
    }
    if (!response.ok && !resultado.error) {
        resultado.error = `Error HTTP ${response.status}`;
    }
    return resultado;
}

function jsonOptions(method, body) {
    return {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    };
}

async function uploadImage(file) {
    const formData = new FormData();
    formData.append('imagen', file);
    return requestJSON('/api/imagenes/subir', {
        method: 'POST',
        body: formData,
    });
}

const api = {
    // Clientes
    getClientes: () => requestJSON('/api/clientes'),
    getTotalClientes: () => requestJSON('/api/clientes/total'),
    addCliente: (grupo, nombre, ip) => requestJSON(
        '/api/clientes', jsonOptions('POST', { grupo, nombre, ip })
    ),
    removeCliente: (grupo, ip) => requestJSON(
        `/api/clientes/${encodeURIComponent(ip)}`,
        jsonOptions('DELETE', { grupo })
    ),
    editCliente: (grupo, ipOriginal, nuevoNombre, nuevaIp) => requestJSON(
        `/api/clientes/${encodeURIComponent(ipOriginal)}`,
        jsonOptions('PUT', {
            grupo,
            nuevo_nombre: nuevoNombre,
            nueva_ip: nuevaIp,
        })
    ),
    addGrupo: (nombre) => requestJSON('/api/grupos', jsonOptions('POST', { nombre })),
    removeGrupo: (nombre) => requestJSON(
        `/api/grupos/${encodeURIComponent(nombre)}`,
        { method: 'DELETE' }
    ),

    // Imágenes v2
    subirImagen: (file) => uploadImage(file),
    enviarImagen: (body) => requestJSON(
        '/api/imagenes/enviar', jsonOptions('POST', body)
    ),

    // Mensajes
    mensajeTodos: (titulo, texto, icono) => requestJSON(
        '/api/mensajes', jsonOptions('POST', { titulo, texto, icono })
    ),
    mensajeUno: (ip, titulo, texto, icono) => requestJSON(
        '/api/mensajes/cliente', jsonOptions('POST', { ip, titulo, texto, icono })
    ),
    mensajeGrupo: (grupo, titulo, texto, icono) => requestJSON(
        '/api/mensajes/grupo', jsonOptions('POST', { grupo, titulo, texto, icono })
    ),
    getIconos: () => requestJSON('/api/iconos'),
};

window.hermesApi = api;
