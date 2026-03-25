/**
 * HERMES - Lógica de la Interfaz del Administrador
 */

document.addEventListener('DOMContentLoaded', () => {
    // Referencias UI (Navegación)
    const navBtnElements = document.querySelectorAll('.nav-btn');
    const viewElements = document.querySelectorAll('.view');
    const loader = document.getElementById('loader');

    // Inicializar la aplicación cuando PyWebView esté listo
    window.addEventListener('pywebviewready', async () => {
        loader.classList.remove('active'); // Ocultar loader
        switchView('dashboard'); // Mostrar la vista principal
        await initDashboard();
        await initMessagesForm();
        await renderClientsList();
        setupEventListeners();
    });

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
        select.innerHTML = '';
        iconos.forEach(ico => {
            const option = document.createElement('option');
            option.value = ico;
            option.textContent = ico.charAt(0).toUpperCase() + ico.slice(1);
            select.appendChild(option);
        });
    }

    async function renderClientsList() {
    const grupos = await window.hermesApi.getClientes();
    const listEl = document.getElementById('cli-lista');
    const countEl = document.getElementById('cli-count');

    const total = Object.values(grupos).reduce((s, arr) => s + arr.length, 0);
    countEl.textContent = total;
    listEl.innerHTML = '';

    for (const [grupo, clientes] of Object.entries(grupos)) {
        const header = document.createElement('li');
        header.className = 'group-header';
        header.innerHTML = `<strong>📁 ${grupo}</strong> <span>(${clientes.length})</span>`;
        listEl.appendChild(header);

        if (clientes.length === 0) {
            const empty = document.createElement('li');
            empty.style.cssText = 'justify-content:center; color: var(--text-muted); font-size:13px;';
            empty.textContent = 'Sin clientes en este grupo';
            listEl.appendChild(empty);
        } else {
            clientes.forEach(({ nombre, ip }) => {
                const li = document.createElement('li');
                li.innerHTML = `
                    <span>💻 <strong>${nombre}</strong> — ${ip}</span>
                    <div style="display:flex; gap:6px;">
                        <button class="btn" style="padding:5px 10px; font-size:12px;"
                            onclick="editCliente('${grupo}', '${nombre}', '${ip}')">Editar</button>
                        <button class="btn danger" style="padding:5px 10px; font-size:12px;"
                            onclick="removeCliente('${grupo}', '${ip}')">Eliminar</button>
                    </div>`;
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

    // Funciones globales para inline handlers (como en clientes)
    window.removeCliente = async (ip) => {
        if(confirm(`¿Seguro de eliminar la IP ${ip}?`)) {
            const res = await window.hermesApi.removeCliente(ip);
            if(res.ok) {
                await renderClientsList();
                await initDashboard();
            } else {
                alert(`Error al eliminar: ${res.error}`);
            }
        }
    };

    // --- EVENT LISTENERS PRINCIPALES ---
    function setupEventListeners() {
        // Navegación
        navBtnElements.forEach(btn => {
            btn.addEventListener('click', () => switchView(btn.dataset.target));
        });

        // ### WALLPAPER VIEW ###
        const btnSelectImg = document.getElementById('btn-seleccionar-img');
        const inputRuta = document.getElementById('wp-ruta');
        const btnAplicar = document.getElementById('btn-aplicar-fondo');
        const wpResult = document.getElementById('wp-resultados');
        const rbsWpTarget = document.getElementsByName('wp-target');
        const wpGrupoContainer = document.getElementById('wp-grupo-container');
        const wpUnoContainer = document.getElementById('wp-uno-container');
        const wpClienteSelect = document.getElementById('wp-cliente-select');

        // Mostrar/ocultar selectores según el radio elegido
        rbsWpTarget.forEach(rb => {
            rb.addEventListener('change', async () => {
                wpGrupoContainer.classList.add('hidden');
                wpUnoContainer.classList.add('hidden');

                if (rb.value === 'grupo') {
                    wpGrupoContainer.classList.remove('hidden');
                } else if (rb.value === 'uno') {
                    wpUnoContainer.classList.remove('hidden');
                    // Cargar lista de clientes en el select
                    const grupos = await window.hermesApi.getClientes();
                    wpClienteSelect.innerHTML = '<option value="">-- Selecciona un equipo --</option>';
                    for (const [grupo, clientes] of Object.entries(grupos)) {
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
            });
        });

        btnSelectImg.addEventListener('click', async () => {
            const res = await window.hermesApi.seleccionarImagen();
            if (res && res.ok) {
                inputRuta.value = res.ruta;
                btnAplicar.disabled = false;
            } else if (res && res.error && res.error !== 'Selección cancelada') {
                alert('Error: ' + res.error);
            }
        });

        btnAplicar.addEventListener('click', async () => {
            const ruta = inputRuta.value;
            if (!ruta) return;

            const targetType = document.querySelector('input[name="wp-target"]:checked').value;

            // Validar selección individual
            if (targetType === 'uno' && !wpClienteSelect.value) {
                alert('Selecciona un equipo de la lista');
                return;
            }

            btnAplicar.disabled = true;
            btnAplicar.textContent = 'Enviando...';
            wpResult.classList.add('hidden');

            let res;
            if (targetType === 'todos') {
                res = await window.hermesApi.cambiarFondo(ruta);
            } else if (targetType === 'grupo') {
                const grupo = document.getElementById('wp-grupo').value;
                res = await window.hermesApi.cambiarFondoGrupo(grupo, ruta);
            } else {
                const ip = wpClienteSelect.value;
                res = await window.hermesApi.cambiarFondoUno(ip, ruta);
            }

            wpResult.textContent = JSON.stringify(res, null, 2);
            wpResult.classList.remove('hidden');
            btnAplicar.textContent = 'Aplicar';
            btnAplicar.disabled = false;
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
                    msgClienteSelect.innerHTML = '<option value="">-- Selecciona un equipo --</option>';
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

        btnRemoveGrupo.addEventListener('click', async () => {
            const nombre = document.getElementById('cli-grupo-eliminar').value;
            errorGrupo2.classList.add('hidden');

            if (!nombre) {
                errorGrupo2.textContent = 'Selecciona un grupo para eliminar';
                errorGrupo2.classList.remove('hidden');
                return;
            }

            const clientesEnGrupo = (await window.hermesApi.getClientes())[nombre] || [];
            const aviso = clientesEnGrupo.length > 0
                ? `⚠️ El grupo "${nombre}" tiene ${clientesEnGrupo.length} cliente(s). ¿Eliminar igualmente?`
                : `¿Eliminar el grupo "${nombre}"?`;

            if (!confirm(aviso)) return;

            const res = await window.hermesApi.removeGrupo(nombre);
            if (res.ok) {
                await renderClientsList();
            } else {
                errorGrupo2.textContent = res.error;
                errorGrupo2.classList.remove('hidden');
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
        sel.innerHTML = id === 'cli-grupo-eliminar'
            ? '<option value="">-- Selecciona un grupo --</option>'
            : '';
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
