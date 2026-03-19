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
        const clientes = await window.hermesApi.getClientes();
        const listEl = document.getElementById('cli-lista');
        const countEl = document.getElementById('cli-count');
        
        countEl.textContent = clientes.length;
        listEl.innerHTML = '';

        if (clientes.length === 0) {
            listEl.innerHTML = '<li style="justify-content:center; color: var(--text-muted)">No hay clientes registrados</li>';
            return;
        }

        clientes.forEach(ip => {
            const li = document.createElement('li');
            li.innerHTML = `
                <span>💻 ${ip}</span>
                <button class="btn danger" style="padding: 6px 12px; font-size: 13px;" onclick="removeCliente('${ip}')">Eliminar</button>
            `;
            listEl.appendChild(li);
        });
    }

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

        btnSelectImg.addEventListener('click', async () => {
            const res = await window.hermesApi.seleccionarImagen();
            if (res && res.ok) {
                inputRuta.value = res.ruta;
                btnAplicar.disabled = false;
            } else if (res && res.error && res.error !== "Selección cancelada") {
                alert("Error: " + res.error);
            }
        });

        btnAplicar.addEventListener('click', async () => {
            const ruta = inputRuta.value;
            if (!ruta) return;

            btnAplicar.disabled = true;
            btnAplicar.textContent = 'Enviando...';
            wpResult.classList.add('hidden');

            const res = await window.hermesApi.cambiarFondo(ruta);
            
            btnAplicar.textContent = 'Aplicar a todos';
            btnAplicar.disabled = false;
            
            wpResult.textContent = JSON.stringify(res, null, 2);
            wpResult.classList.remove('hidden');
        });

        // ### MESSAGES VIEW ###
        const btnSendMsg = document.getElementById('btn-enviar-msg');
        const rbsTarget = document.getElementsByName('msg-target');
        const containerIp = document.getElementById('msg-ip-container');
        const msgResult = document.getElementById('msg-resultados');

        // Toggle IP Input
        rbsTarget.forEach(rb => {
            rb.addEventListener('change', () => {
                if (rb.value === 'uno') {
                    containerIp.classList.remove('hidden');
                } else {
                    containerIp.classList.add('hidden');
                }
            });
        });

        btnSendMsg.addEventListener('click', async () => {
            const titulo = document.getElementById('msg-titulo').value;
            const texto = document.getElementById('msg-texto').value;
            const icono = document.getElementById('msg-icono').value;
            
            const targetType = document.querySelector('input[name="msg-target"]:checked').value;
            
            btnSendMsg.disabled = true;
            btnSendMsg.textContent = 'Enviando...';
            msgResult.classList.add('hidden');

            let res;
            if (targetType === 'todos') {
                res = await window.hermesApi.mensajeTodos(titulo, texto, icono);
            } else {
                const ip = document.getElementById('msg-ip').value;
                if (!ip) {
                    alert('Debes escribir una IP');
                    btnSendMsg.disabled = false;
                    btnSendMsg.textContent = 'Enviar Mensaje';
                    return;
                }
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
        const inputIp = document.getElementById('cli-nueva-ip');

        btnAddCli.addEventListener('click', async () => {
            const ip = inputIp.value;
            divError.classList.add('hidden');

            if (!ip) {
                divError.textContent = "Ingrese una IP";
                divError.classList.remove('hidden');
                return;
            }

            const res = await window.hermesApi.addCliente(ip);
            if (res.ok) {
                inputIp.value = '';
                await renderClientsList();
                await initDashboard();
            } else {
                divError.textContent = res.error;
                divError.classList.remove('hidden');
            }
        });
    }
});
