/**
 * HERMES - Lógica de la Interfaz del Administrador
 */

document.addEventListener('DOMContentLoaded', async () => {
    // Referencias UI (Navegación)
    const navBtnElements = document.querySelectorAll('.nav-btn');
    const viewElements = document.querySelectorAll('.view');
    const loader = document.getElementById('loader');
    let gruposActuales = {};

    loader.classList.remove('active');
    switchView('dashboard');
    await initDashboard();
    await initMessagesForm();
    await renderClientsList();
    setupEventListeners();

    // --- NAVEGACIÓN ---
    function switchView(targetId) {
        // Actualizar botones
        navBtnElements.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.target === targetId);
        });
        
        // Actualizar vistas
        viewElements.forEach(view => {
            if(view.id === targetId) {
                view.classList.remove('hidden');
            } else {
                view.classList.add('hidden');
            }
        });

        // Refrescar datos según la vista
        if (targetId === 'dashboard') initDashboard();
        if (targetId === 'clientes') renderClientsList();
    }

    // --- CARGAR DATOS INICIALES ---
    async function initDashboard() {
        const total = await window.hermesApi.getTotalClientes();
        document.getElementById('dash-total-pcs').textContent = total;
    }

    async function initMessagesForm() {
        const iconos = await window.hermesApi.getIconos();
        const select = document.getElementById('msg-icono');
        select.replaceChildren();
        iconos.forEach(ico => {
            const option = document.createElement('option');
            option.value = ico;
            option.textContent = ico.charAt(0).toUpperCase() + ico.slice(1);
            select.appendChild(option);
        });
    }

    async function renderClientsList() {
    const grupos = await window.hermesApi.getClientes();
    gruposActuales = grupos;
    const listEl = document.getElementById('cli-lista');
    const countEl = document.getElementById('cli-count');

    const total = Object.values(grupos).reduce((s, arr) => s + arr.length, 0);
    countEl.textContent = total;
    listEl.replaceChildren();

    for (const [grupo, clientes] of Object.entries(grupos)) {
        const header = document.createElement('li');
        header.className = 'group-header';
        const nombreGrupo = document.createElement('strong');
        nombreGrupo.textContent = `📁 ${grupo}`;
        const cantidadGrupo = document.createElement('span');
        cantidadGrupo.textContent = ` (${clientes.length})`;
        header.append(nombreGrupo, cantidadGrupo);
        listEl.appendChild(header);

        if (clientes.length === 0) {
            const empty = document.createElement('li');
            empty.style.cssText = 'justify-content:center; color: var(--text-muted); font-size:13px;';
            empty.textContent = 'Sin clientes en este grupo';
            listEl.appendChild(empty);
        } else {
            clientes.forEach(({ nombre, ip }) => {
                const li = document.createElement('li');
                const datosCliente = document.createElement('span');
                datosCliente.textContent = `💻 ${nombre} — ${ip}`;
                const acciones = document.createElement('div');
                acciones.className = 'client-actions';
                const editar = document.createElement('button');
                editar.className = 'btn client-action';
                editar.textContent = 'Editar';
                editar.addEventListener('click', () => window.editCliente(grupo, nombre, ip));
                const eliminar = document.createElement('button');
                eliminar.className = 'btn danger client-action';
                eliminar.textContent = 'Eliminar';
                eliminar.addEventListener('click', () => window.removeCliente(grupo, ip));
                acciones.append(editar, eliminar);
                li.append(datosCliente, acciones);
                listEl.appendChild(li);
            });
        }
    }

    // Sincronizar todos los selectores de grupo en la app
    syncGrupoSelects(Object.keys(grupos));
}

    window.removeCliente = async (grupo, ip) => {
        if (confirm(`¿Eliminar ${ip} de ${grupo}?`)) {
            const res = await window.hermesApi.removeCliente(grupo, ip);
            if (res.ok) { await renderClientsList(); await initDashboard(); }
            else alert(`Error: ${res.error}`);
        }
    };

    window.editCliente = async (grupo, nombre, ip) => {
        const nuevoNombre = prompt('Nombre del PC:', nombre);
        if (nuevoNombre === null) return;
        const nuevaIp = prompt('IP del PC:', ip);
        if (nuevaIp === null) return;

        const res = await window.hermesApi.editCliente(grupo, ip, nuevoNombre, nuevaIp);
        if (res.ok) await renderClientsList();
        else alert(`Error: ${res.error}`);
    };

    // --- EVENT LISTENERS PRINCIPALES ---
    function setupEventListeners() {
        // Navegación
        navBtnElements.forEach(btn => {
            btn.addEventListener('click', () => switchView(btn.dataset.target));
        });

        // ### WALLPAPER VIEW ###
        const inputImagen = document.getElementById('wp-file');
        const estadoSubida = document.getElementById('wp-upload-status');
        const vistaPrevia = document.getElementById('wp-preview');
        const selectorTipo = document.getElementById('wp-tipo');
        const btnAplicar = document.getElementById('btn-aplicar-fondo');
        const wpResult = document.getElementById('wp-resultados');
        const rbsWpTarget = document.getElementsByName('wp-target');
        const wpGrupoContainer = document.getElementById('wp-grupo-container');
        const wpUnoContainer = document.getElementById('wp-uno-container');
        const wpGrupoSelect = document.getElementById('wp-grupo');
        const wpClienteSelect = document.getElementById('wp-cliente-select');
        const limiteImagenBytes = 20 * 1024 * 1024;
        let imageId = null;
        let uploadingImage = false;
        let sendingImage = false;
        let previewUrl = null;

        function destinoImagenValido() {
            const destino = document.querySelector('input[name="wp-target"]:checked')?.value;
            if (destino === 'grupo') return Boolean(wpGrupoSelect.value);
            if (destino === 'equipo') return Boolean(wpClienteSelect.value);
            return destino === 'todos';
        }

        function actualizarBotonEnviar() {
            btnAplicar.disabled = !imageId
                || uploadingImage
                || sendingImage
                || !destinoImagenValido();
        }

        function mostrarErrorEnvio(mensaje) {
            wpResult.replaceChildren();
            const error = document.createElement('p');
            error.className = 'result-error';
            error.textContent = mensaje;
            wpResult.appendChild(error);
            wpResult.classList.remove('hidden');
        }

        function mostrarResultadoEnvio(resultado) {
            wpResult.replaceChildren();
            if (resultado.total === 0) {
                const aviso = document.createElement('p');
                aviso.className = 'result-warning';
                aviso.textContent = 'El destino no tiene equipos registrados; no se envió la imagen.';
                wpResult.appendChild(aviso);
                wpResult.classList.remove('hidden');
                return;
            }

            const resumen = document.createElement('p');
            if (resultado.fallidos === 0) {
                resumen.textContent = `Envío exitoso: ${resultado.exitosos} de ${resultado.total} equipos.`;
            } else if (resultado.exitosos === 0) {
                resumen.className = 'result-error';
                resumen.textContent = `Falló el envío a los ${resultado.total} equipos.`;
            } else {
                resumen.className = 'result-warning';
                resumen.textContent = `Éxito parcial: ${resultado.exitosos} de ${resultado.total} equipos; ${resultado.fallidos} fallaron.`;
            }
            wpResult.appendChild(resumen);

            if (resultado.fallos?.length) {
                const tituloFallos = document.createElement('p');
                tituloFallos.className = 'failure-title';
                tituloFallos.textContent = 'Fallos por equipo:';
                const listaFallos = document.createElement('ul');
                resultado.fallos.forEach(({ ip, error }) => {
                    const fallo = document.createElement('li');
                    fallo.textContent = `${ip}: ${error}`;
                    listaFallos.appendChild(fallo);
                });
                wpResult.append(tituloFallos, listaFallos);
            }
            wpResult.classList.remove('hidden');
        }

        inputImagen.addEventListener('change', async () => {
            const archivo = inputImagen.files[0] || null;
            imageId = null;
            actualizarBotonEnviar();
            wpResult.classList.add('hidden');
            if (previewUrl) {
                URL.revokeObjectURL(previewUrl);
                previewUrl = null;
            }
            vistaPrevia.removeAttribute('src');
            vistaPrevia.classList.add('hidden');

            if (!archivo) {
                estadoSubida.textContent = 'Selecciona una imagen (máximo 20 MB).';
                return;
            }
            previewUrl = URL.createObjectURL(archivo);
            vistaPrevia.src = previewUrl;
            vistaPrevia.classList.remove('hidden');
            if (archivo.size > limiteImagenBytes) {
                estadoSubida.textContent = 'La imagen supera el máximo permitido de 20 MB';
                inputImagen.value = '';
                return;
            }

            uploadingImage = true;
            inputImagen.disabled = true;
            estadoSubida.textContent = 'Subiendo imagen...';
            actualizarBotonEnviar();
            try {
                const resultado = await window.hermesApi.subirImagen(archivo);
                if (!resultado.ok || !resultado.image_id) {
                    estadoSubida.textContent = resultado.error || 'No se pudo subir la imagen.';
                    return;
                }
                imageId = resultado.image_id;
                estadoSubida.textContent = 'Imagen subida y lista para enviar.';
            } catch {
                estadoSubida.textContent = 'No se pudo conectar con el servidor. Comprueba que el admin esté activo e inténtalo de nuevo.';
            } finally {
                uploadingImage = false;
                inputImagen.disabled = false;
                inputImagen.value = '';
                actualizarBotonEnviar();
            }
        });

        window.addEventListener('beforeunload', () => {
            if (previewUrl) URL.revokeObjectURL(previewUrl);
        });

        // Mostrar/ocultar selectores según el radio elegido
        rbsWpTarget.forEach(rb => {
            rb.addEventListener('change', () => {
                wpGrupoContainer.classList.add('hidden');
                wpUnoContainer.classList.add('hidden');

                if (rb.value === 'grupo') {
                    wpGrupoContainer.classList.remove('hidden');
                } else if (rb.value === 'equipo') {
                    wpUnoContainer.classList.remove('hidden');
                    wpClienteSelect.replaceChildren();
                    const placeholder = document.createElement('option');
                    placeholder.value = '';
                    placeholder.textContent = '-- Selecciona un equipo --';
                    wpClienteSelect.appendChild(placeholder);
                    for (const [grupo, clientes] of Object.entries(gruposActuales)) {
                        const optGroup = document.createElement('optgroup');
                        optGroup.label = grupo;
                        clientes.forEach(({ nombre, ip }) => {
                            const opt = document.createElement('option');
                            opt.value = ip;
                            opt.textContent = `${nombre} — ${ip}`;
                            optGroup.appendChild(opt);
                        });
                        wpClienteSelect.appendChild(optGroup);
                    }
                }
                actualizarBotonEnviar();
            });
        });

        wpGrupoSelect.addEventListener('change', actualizarBotonEnviar);
        wpClienteSelect.addEventListener('change', actualizarBotonEnviar);

        btnAplicar.addEventListener('click', async () => {
            if (!imageId || !destinoImagenValido() || sendingImage) return;
            const destino = document.querySelector('input[name="wp-target"]:checked').value;
            const solicitud = {
                image_id: imageId,
                tipo: selectorTipo.value,
                destino,
            };
            if (destino === 'grupo') solicitud.grupo = wpGrupoSelect.value;
            if (destino === 'equipo') solicitud.ip = wpClienteSelect.value;

            sendingImage = true;
            btnAplicar.textContent = 'Enviando...';
            actualizarBotonEnviar();
            wpResult.classList.add('hidden');
            try {
                const resultado = await window.hermesApi.enviarImagen(solicitud);
                if (resultado.error) {
                    mostrarErrorEnvio(resultado.error);
                    if (resultado.error.toLowerCase().includes('identificador de imagen')) {
                        imageId = null;
                        estadoSubida.textContent = 'El identificador expiró o ya no existe. Selecciona y sube la imagen de nuevo.';
                    }
                    return;
                }
                mostrarResultadoEnvio(resultado);
            } catch {
                mostrarErrorEnvio('No se pudo conectar con el servidor. Comprueba que el admin esté activo e inténtalo de nuevo.');
            } finally {
                sendingImage = false;
                btnAplicar.textContent = 'Enviar';
                actualizarBotonEnviar();
            }
        });

         // ### MESSAGES VIEW ###
        const btnSendMsg = document.getElementById('btn-enviar-msg');
        const rbsMsgTarget = document.getElementsByName('msg-target');
        const msgGrupoContainer = document.getElementById('msg-grupo-container');
        const msgIpContainer = document.getElementById('msg-ip-container');
        const msgClienteSelect = document.getElementById('msg-cliente-select');
        const msgResult = document.getElementById('msg-resultados');

        // Mostrar/ocultar selectores según el radio elegido
        rbsMsgTarget.forEach(rb => {
            rb.addEventListener('change', async () => {
                msgGrupoContainer.classList.add('hidden');
                msgIpContainer.classList.add('hidden');

                if (rb.value === 'grupo') {
                    msgGrupoContainer.classList.remove('hidden');
                } else if (rb.value === 'uno') {
                    msgIpContainer.classList.remove('hidden');
                    // Cargar lista de clientes en el select
                    const grupos = await window.hermesApi.getClientes();
                    msgClienteSelect.replaceChildren();
                    const placeholder = document.createElement('option');
                    placeholder.value = '';
                    placeholder.textContent = '-- Selecciona un equipo --';
                    msgClienteSelect.appendChild(placeholder);
                    for (const [grupo, clientes] of Object.entries(grupos)) {
                        const optGroup = document.createElement('optgroup');
                        optGroup.label = grupo;
                        clientes.forEach(({ nombre, ip }) => {
                            const opt = document.createElement('option');
                            opt.value = ip;
                            opt.textContent = `${nombre} — ${ip}`;
                            optGroup.appendChild(opt);
                        });
                        msgClienteSelect.appendChild(optGroup);
                    }
                }
            });
        });

        btnSendMsg.addEventListener('click', async () => {
            const titulo = document.getElementById('msg-titulo').value;
            const texto = document.getElementById('msg-texto').value;
            const icono = document.getElementById('msg-icono').value;
            const targetType = document.querySelector('input[name="msg-target"]:checked').value;

            if (targetType === 'uno' && !msgClienteSelect.value) {
                alert('Selecciona un equipo de la lista');
                return;
            }

            btnSendMsg.disabled = true;
            btnSendMsg.textContent = 'Enviando...';
            msgResult.classList.add('hidden');

            let res;
            if (targetType === 'todos') {
                res = await window.hermesApi.mensajeTodos(titulo, texto, icono);
            } else if (targetType === 'grupo') {
                const grupo = document.getElementById('msg-grupo').value;
                res = await window.hermesApi.mensajeGrupo(grupo, titulo, texto, icono);
            } else {
                const ip = msgClienteSelect.value;
                res = await window.hermesApi.mensajeUno(ip, titulo, texto, icono);
            }

            msgResult.textContent = JSON.stringify(res, null, 2);
            msgResult.classList.remove('hidden');
            btnSendMsg.disabled = false;
            btnSendMsg.textContent = 'Enviar Mensaje';
        });

        // ### CLIENTS VIEW ###
        const btnAddCli = document.getElementById('btn-add-cliente');
        const divError = document.getElementById('cli-error');
        const selectGrupo = document.getElementById('cli-grupo');
        const inputNombre = document.getElementById('cli-nueva-nombre');
        const inputIp = document.getElementById('cli-nueva-ip');

        btnAddCli.addEventListener('click', async () => {
            const grupo = selectGrupo.value;
            const nombre = inputNombre.value.trim();
            const ip = inputIp.value.trim();
            divError.classList.add('hidden');

            if (!nombre || !ip) {
                divError.textContent = 'Ingrese nombre e IP';
                divError.classList.remove('hidden');
                return;
            }

            const res = await window.hermesApi.addCliente(grupo, nombre, ip);
            if (res.ok) {
                inputNombre.value = '';
                inputIp.value = '';
                await renderClientsList();
                await initDashboard();
            } else {
                divError.textContent = res.error;
                divError.classList.remove('hidden');
            }
            
        });

        // Crear grupo
        const btnAddGrupo = document.getElementById('btn-add-grupo');
        const inputNuevoGrupo = document.getElementById('cli-nuevo-grupo');
        const errorGrupo = document.getElementById('cli-grupo-error');

        btnAddGrupo.addEventListener('click', async () => {
            const nombre = inputNuevoGrupo.value.trim();
            errorGrupo.classList.add('hidden');

            if (!nombre) {
                errorGrupo.textContent = 'Ingrese un nombre para el grupo';
                errorGrupo.classList.remove('hidden');
                return;
            }

            const res = await window.hermesApi.addGrupo(nombre);
            if (res.ok) {
                inputNuevoGrupo.value = '';
                await renderClientsList();
            } else {
                errorGrupo.textContent = res.error;
                errorGrupo.classList.remove('hidden');
            }
        });

        // Eliminar grupo
        const btnRemoveGrupo = document.getElementById('btn-remove-grupo');
        const errorGrupo2 = document.getElementById('cli-grupo-error2');
        const groupDeleteModal = document.getElementById('group-delete-modal');
        const groupDeleteMessage = document.getElementById('group-delete-message');
        const groupDeleteCancel = document.getElementById('group-delete-cancel');
        const groupDeleteConfirm = document.getElementById('group-delete-confirm');
        let grupoPendienteEliminar = null;
        let focoAntesDeModal = null;

        function cerrarModalEliminarGrupo() {
            groupDeleteModal.classList.add('hidden');
            grupoPendienteEliminar = null;
            if (focoAntesDeModal?.isConnected) focoAntesDeModal.focus();
        }

        function abrirModalEliminarGrupo(nombre, cantidad) {
            grupoPendienteEliminar = nombre;
            focoAntesDeModal = document.activeElement;
            groupDeleteMessage.textContent = cantidad > 0
                ? `El grupo ${nombre} tiene ${cantidad} ${cantidad === 1 ? 'equipo; se eliminará' : 'equipos; se eliminarán'} junto con él. Esta acción no se puede deshacer.`
                : `El grupo ${nombre} tiene 0 equipos. No hay equipos que eliminar. Esta acción no se puede deshacer.`;
            groupDeleteModal.classList.remove('hidden');
            groupDeleteCancel.focus();
        }

        btnRemoveGrupo.addEventListener('click', async () => {
            const nombre = document.getElementById('cli-grupo-eliminar').value;
            errorGrupo2.classList.add('hidden');

            if (!nombre) {
                errorGrupo2.textContent = 'Selecciona un grupo para eliminar';
                errorGrupo2.classList.remove('hidden');
                return;
            }

            const equipos = gruposActuales[nombre] || [];
            abrirModalEliminarGrupo(nombre, equipos.length);
        });

        groupDeleteCancel.addEventListener('click', cerrarModalEliminarGrupo);
        groupDeleteModal.addEventListener('click', (event) => {
            if (event.target === groupDeleteModal) cerrarModalEliminarGrupo();
        });
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && !groupDeleteModal.classList.contains('hidden')) {
                cerrarModalEliminarGrupo();
            }
        });
        groupDeleteConfirm.addEventListener('click', async () => {
            if (!grupoPendienteEliminar) return;
            const nombre = grupoPendienteEliminar;
            groupDeleteConfirm.disabled = true;
            groupDeleteCancel.disabled = true;
            groupDeleteConfirm.textContent = 'Eliminando...';
            try {
                const resultado = await window.hermesApi.removeGrupo(nombre);
                if (!resultado.ok) {
                    errorGrupo2.textContent = resultado.error || 'No se pudo eliminar el grupo.';
                    errorGrupo2.classList.remove('hidden');
                    cerrarModalEliminarGrupo();
                    return;
                }
                cerrarModalEliminarGrupo();
                await renderClientsList();
                await initDashboard();
            } catch {
                errorGrupo2.textContent = 'No se pudo conectar con el servidor. Comprueba que el admin esté activo e inténtalo de nuevo.';
                errorGrupo2.classList.remove('hidden');
                cerrarModalEliminarGrupo();
            } finally {
                groupDeleteConfirm.disabled = false;
                groupDeleteCancel.disabled = false;
                groupDeleteConfirm.textContent = 'Eliminar';
            }
        });
    }

    // MANTENER SINCRONIZADO WAWLLPAPERS, MENSAJES Y CLIENTES 

    function syncGrupoSelects(grupos) {
    const selectIds = ['cli-grupo', 'wp-grupo', 'msg-grupo', 'cli-grupo-eliminar'];
    selectIds.forEach(id => {
        const sel = document.getElementById(id);
        if (!sel) return;
        const current = sel.value;
        sel.replaceChildren();
        if (id === 'cli-grupo-eliminar') {
            const placeholder = document.createElement('option');
            placeholder.value = '';
            placeholder.textContent = '-- Selecciona un grupo --';
            sel.appendChild(placeholder);
        }
        grupos.forEach(g => {
            const opt = document.createElement('option');
            opt.value = g;
            opt.textContent = g;
            sel.appendChild(opt);
        });
        // Restaurar selección previa si sigue existiendo
        if ([...sel.options].some(o => o.value === current)) sel.value = current;
    });
}
});
