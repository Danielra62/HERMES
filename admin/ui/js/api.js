/** HERMES - cliente HTTP para la API Flask. */

let archivoWallpaper = null;

async function requestJSON(url, options = {}) {
    const response = await fetch(url, options);
    const resultado = await response.json();
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

async function uploadAndApply(endpoint, ruta, extra = {}) {
    if (!archivoWallpaper || ruta !== archivoWallpaper.name) {
        return {
            publicacion: { ok: false, error: 'Selecciona una imagen antes de continuar' },
            envio: null,
        };
    }

    const formData = new FormData();
    formData.append('imagen', archivoWallpaper);
    const subida = await requestJSON('/api/fondo/subir', {
        method: 'POST',
        body: formData,
    });
    if (!subida.ok) {
        return { publicacion: subida, envio: null };
    }

    const resultado = await requestJSON(endpoint, jsonOptions('POST', {
        ...extra,
        upload_id: subida.upload_id,
    }));
    if (resultado.publicacion?.ok) {
        archivoWallpaper = null;
        document.getElementById('wp-file').value = '';
    }
    return resultado;
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

    // Fondos
    seleccionarImagen: () => new Promise((resolve) => {
        const input = document.getElementById('wp-file');
        const limpiarEventos = () => {
            input.removeEventListener('change', alCambiar);
            input.removeEventListener('cancel', alCancelar);
        };
        const alCambiar = () => {
            limpiarEventos();
            archivoWallpaper = input.files[0] || null;
            resolve(archivoWallpaper
                ? { ok: true, ruta: archivoWallpaper.name }
                : { ok: false, error: 'Selección cancelada' });
        };
        const alCancelar = () => {
            limpiarEventos();
            resolve({ ok: false, error: 'Selección cancelada' });
        };
        input.value = '';
        input.addEventListener('change', alCambiar, { once: true });
        input.addEventListener('cancel', alCancelar, { once: true });
        input.click();
    }),
    cambiarFondo: (ruta) => uploadAndApply('/api/fondo', ruta),
    cambiarFondoGrupo: (grupo, ruta) => uploadAndApply(
        '/api/fondo/grupo', ruta, { grupo }
    ),
    cambiarFondoUno: (ip, ruta) => uploadAndApply(
        '/api/fondo/cliente', ruta, { ip }
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
