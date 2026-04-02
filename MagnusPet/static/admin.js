document.addEventListener("DOMContentLoaded", () => {
    
    // --- STATE ---
    let userRol = 'veterinario'; 
    let dataCache = {
        mascotas: {},
        productos: {},
        usuarios: {},
        veterinarios: {}
    };
    // Corregido: almacenar IDs en el estado global del modal
    let currentHistorialId = null; 
    let currentMascotaId = null;

    // --- SELECTORES ---
    const pages = document.querySelectorAll('.admin-page');
    const navLinks = document.querySelectorAll('.admin-nav-link');
    const logoutBtn = document.getElementById('admin-logout-btn');
    const adminContent = document.querySelector('.admin-content');

    // Citas
    const citasList = document.getElementById('admin-citas-list');
    const btnOpenCitaModal = document.getElementById('btn-open-cita-modal');
    const citaModal = document.getElementById('cita-modal');
    const citaForm = document.getElementById('cita-form');

    // Productos
    const productosList = document.getElementById('admin-productos-list');
    const productoModal = document.getElementById('producto-modal');
    const productoForm = document.getElementById('producto-form');
    const btnOpenProductoModal = document.getElementById('btn-open-producto-modal');

    // Usuarios
    const usuariosList = document.getElementById('admin-usuarios-list');
    const usuarioModal = document.getElementById('usuario-modal');
    const usuarioForm = document.getElementById('usuario-form');

    // Mascotas
    const mascotasList = document.getElementById('admin-mascotas-list');
    const mascotaModal = document.getElementById('mascota-modal');
    const mascotaForm = document.getElementById('mascota-form');
    const btnOpenCrearMascotaModal = document.getElementById('btn-open-crear-mascota-modal');
    const crearMascotaModal = document.getElementById('crear-mascota-modal');
    const crearMascotaForm = document.getElementById('crear-mascota-form');

    // Veterinarios
    const veterinariosList = document.getElementById('admin-veterinarios-list');
    const veterinarioModal = document.getElementById('veterinario-modal');
    const veterinarioForm = document.getElementById('veterinario-form');
    const btnOpenVeterinarioModal = document.getElementById('btn-open-veterinario-modal');

    // Carnet
    const carnetModal = document.getElementById('carnet-modal');
    const carnetForm = document.getElementById('carnet-form');
    const carnetVacunasList = document.getElementById('carnet-vacunas-list');
    const vacunaForm = document.getElementById('vacuna-form');
    const carnetMsg = document.getElementById('carnet-msg');

    // --- NAVEGACIÓN ---
    const showPage = (pageId) => {
        pages.forEach(page => {
            page.classList.toggle('hidden', page.id !== pageId);
        });
        navLinks.forEach(link => {
            link.classList.toggle('active', link.dataset.page === pageId);
        });

        // Cargar datos al cambiar de página
        switch (pageId) {
            case 'citas': loadCitas(); break;
            case 'productos': loadProductos(); break;
            case 'usuarios': loadUsuarios(); break;
            case 'mascotas': loadMascotas(); break;
            case 'veterinarios': loadVeterinarios(); break;
        }
    }

    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            showPage(e.target.dataset.page);
        });
    });

    // --- AUTENTICACIÓN Y API ---
    const getToken = () => localStorage.getItem('access_token');
    const clearToken = () => localStorage.removeItem('access_token');

    logoutBtn.addEventListener('click', () => {
        clearToken();
        window.location.href = '/'; 
    });

    const apiFetch = async (endpoint, options = {}) => {
        const token = getToken();
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
        };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        let url = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
        if (!url.startsWith('/api')) {
            url = `/api${url}`;
        }
        const response = await fetch(url, { ...options, headers });
        if (response.status === 401) { 
            logoutBtn.click();
            throw new Error('Sesión expirada'); 
        }
        return response;
    };

    const decodeToken = (token) => {
        try {
            const payloadBase64 = token.split('.')[1];
            const decodedPayload = atob(payloadBase64);
            return JSON.parse(decodedPayload);
        } catch (e) { return null; }
    };

    // --- MOSTRAR MENSAJES DE ERROR/ÉXITO ---
    const showMsg = (el, message, isError = true) => {
        if (!el) return;
        el.textContent = message;
        el.style.color = isError ? '#e76f51' : 'var(--verde-oscuro-pet)';
    }
    const clearMsg = (el) => {
        if (el) el.textContent = '';
    }

    // --- MANEJO DE MODALES ---
    const openModal = (modal) => modal.classList.remove('hidden');
    const closeModal = (modal) => modal.classList.add('hidden');

    document.querySelectorAll('.modal-close').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const modalId = e.target.dataset.modalId;
            closeModal(document.getElementById(modalId));
        });
    });

    // ===================================
    // LÓGICA DE GESTIÓN (CARGA DE DATOS)
    // ===================================

    // --- CITAS ---
    const loadCitas = async () => {
        if (!citasList) return;
        citasList.innerHTML = '<tr><td colspan="7">Cargando citas...</td></tr>';
        try {
            const response = await apiFetch('/admin/citas');
            if (!response.ok) throw new Error('Error al cargar las citas');
            const citas = await response.json();
            
            citasList.innerHTML = '';
            if (citas.length === 0) {
                citasList.innerHTML = '<tr><td colspan="7">No hay citas registradas.</td></tr>';
                return;
            }
            citas.forEach(cita => {
                const tr = document.createElement('tr');
                tr.dataset.id = cita.id;
                const estadoClass = `status-${cita.estado.toLowerCase().replace(' ', '-')}`;
                tr.innerHTML = `
                    <td>${cita.id}</td>
                    <td>${cita.cliente_nombre || 'N/A'}</td>
                    <td>${cita.mascota_nombre || 'N/A'}</td>
                    <td>${cita.fecha} ${cita.hora.substring(0, 5)}</td>
                    <td>${cita.motivo}</td>
                    <td><span class="status-badge-admin ${estadoClass}">${cita.estado}</span></td>
                    <td>
                        ${cita.estado === 'Pendiente' ? `
                            <button class="btn small btn-approve" data-id="${cita.id}">Aprobar</button>
                            <button class="btn small danger btn-reject" data-id="${cita.id}">Rechazar</button>
                        ` : ''}
                        ${userRol === 'admin' ? `<button class="btn small danger btn-delete-cita" data-id="${cita.id}">Borrar</button>` : ''}
                    </td>
                `;
                citasList.appendChild(tr);
            });
        } catch (error) {
            citasList.innerHTML = `<tr><td colspan="7">${error.message}</td></tr>`;
        }
    };

    // --- PRODUCTOS ---
    const loadProductos = async () => {
        if (!productosList) return;
        productosList.innerHTML = '<tr><td colspan="5">Cargando productos...</td></tr>';
        try {
            const response = await apiFetch('/api/products');
            if (!response.ok) throw new Error('Error al cargar productos');
            const productos = await response.json();

            productosList.innerHTML = '';
            dataCache.productos = {};
            if (productos.length === 0) {
                productosList.innerHTML = '<tr><td colspan="5">No hay productos.</td></tr>';
                return;
            }
            productos.forEach(p => {
                dataCache.productos[p.id] = p;
                const tr = document.createElement('tr');
                tr.dataset.id = p.id;
                tr.innerHTML = `
                    <td>${p.id}</td>
                    <td>${p.title}</td>
                    <td>$${p.price.toLocaleString()}</td>
                    <td>${p.stock}</td>
                    <td>
                        <button class="btn small btn-edit-producto" data-id="${p.id}">Editar</button>
                        <button class="btn small danger btn-delete-producto" data-id="${p.id}">Borrar</button>
                    </td>
                `;
                productosList.appendChild(tr);
            });
        } catch (error) {
            productosList.innerHTML = `<tr><td colspan="5">${error.message}</td></tr>`;
        }
    };

    // --- USUARIOS ---
    const loadUsuarios = async () => {
        if (!usuariosList) return;
        usuariosList.innerHTML = '<tr><td colspan="5">Cargando usuarios...</td></tr>';
        try {
            const response = await apiFetch('/admin/usuarios');
            if (!response.ok) throw new Error('Error al cargar usuarios');
            const usuarios = await response.json();

            usuariosList.innerHTML = '';
            dataCache.usuarios = {};
            if (usuarios.length === 0) {
                usuariosList.innerHTML = '<tr><td colspan="5">No hay usuarios.</td></tr>';
                return;
            }
            usuarios.forEach(u => {
                dataCache.usuarios[u.id] = u;
                const tr = document.createElement('tr');
                tr.dataset.id = u.id;
                tr.innerHTML = `
                    <td>${u.id}</td>
                    <td>${u.correo}</td>
                    <td>${u.nombre}</td>
                    <td><span class="status-badge-admin status-${u.rol}">${u.rol}</span></td>
                    <td>
                        <button class="btn small btn-edit-usuario" data-id="${u.id}">Editar</button>
                        ${u.rol !== 'admin' ? `<button class="btn small danger btn-delete-usuario" data-id="${u.id}">Borrar</button>` : ''}
                    </td>
                `;
                usuariosList.appendChild(tr);
            });
        } catch (error) {
            usuariosList.innerHTML = `<tr><td colspan="5">${error.message}</td></tr>`;
        }
    };

    // --- MASCOTAS ---
    const loadMascotas = async () => {
        if (!mascotasList) return;
        mascotasList.innerHTML = '<tr><td colspan="5">Cargando mascotas...</td></tr>';
        try {
            const response = await apiFetch('/admin/mascotas');
            if (!response.ok) throw new Error('Error al cargar mascotas');
            const mascotas = await response.json();

            mascotasList.innerHTML = '';
            dataCache.mascotas = {};
            if (mascotas.length === 0) {
                mascotasList.innerHTML = '<tr><td colspan="5">No hay mascotas.</td></tr>';
                return;
            }
            mascotas.forEach(m => {
                dataCache.mascotas[m.id] = m;
                const tr = document.createElement('tr');
                tr.dataset.id = m.id;
                tr.innerHTML = `
                    <td>${m.id}</td>
                    <td>${m.nombre}</td>
                    <td>${m.especie}</td>
                    <td>${m.cliente_nombre || 'N/A'}</td>
                    <td>
                        <button class="btn small ghost btn-carnet" data-id="${m.id}" data-nombre="${m.nombre}">Carnet</button>
                        <button class="btn small btn-edit-mascota" data-id="${m.id}">Editar</button>
                        ${userRol === 'admin' ? `<button class="btn small danger btn-delete-mascota" data-id="${m.id}">Borrar</button>` : ''}
                    </td>
                `;
                mascotasList.appendChild(tr);
            });
        } catch (error) {
            mascotasList.innerHTML = `<tr><td colspan="5">${error.message}</td></tr>`;
        }
    };

    // --- VETERINARIOS ---
    const loadVeterinarios = async () => {
        if (!veterinariosList) return;
        veterinariosList.innerHTML = '<tr><td colspan="5">Cargando veterinarios...</td></tr>';
        try {
            // Usar /api/admin/veterinarios en lugar de /api/veterinarios para obtener correos
            const response = await apiFetch('/admin/veterinarios'); 
            if (!response.ok) throw new Error('Error al cargar veterinarios');
            const veterinarios = await response.json();

            veterinariosList.innerHTML = '';
            dataCache.veterinarios = {};
            if (veterinarios.length === 0) {
                veterinariosList.innerHTML = '<tr><td colspan="5">No hay veterinarios.</td></tr>';
                return;
            }
            veterinarios.forEach(v => {
                dataCache.veterinarios[v.id] = v;
                const tr = document.createElement('tr');
                tr.dataset.id = v.id;
                tr.innerHTML = `
                    <td>${v.id}</td>
                    <td>${v.nombre}</td>
                    <td>${v.especialidad}</td>
                    <td>${v.correo}</td>
                    <td>
                        <button class="btn small btn-edit-veterinario" data-id="${v.id}">Editar</button>
                        <button class="btn small danger btn-delete-veterinario" data-id="${v.id}">Borrar</button>
                    </td>
                `;
                veterinariosList.appendChild(tr);
            });
        } catch (error) {
            veterinariosList.innerHTML = `<tr><td colspan="5">${error.message}</td></tr>`;
        }
    };
    
    // --- NUEVO: Funciones para poblar dropdowns ---
    const loadClientesDropdown = async (selectElement) => {
        try {
            const response = await apiFetch('/admin/clientes');
            if (!response.ok) throw new Error('Error al cargar clientes');
            const clientes = await response.json();
            selectElement.innerHTML = '<option value="">Seleccione un cliente...</option>';
            clientes.forEach(c => {
                selectElement.innerHTML += `<option value="${c.id}">${c.nombre}</option>`;
            });
        } catch (error) {
            selectElement.innerHTML = `<option value="">${error.message}</option>`;
        }
    };
    
    const loadVeterinariosDropdown = async (selectElement) => {
        try {
            const response = await apiFetch('/admin/veterinarios');
            if (!response.ok) throw new Error('Error al cargar veterinarios');
            const vets = await response.json();
            selectElement.innerHTML = '<option value="">Cualquier veterinario...</option>';
            vets.forEach(v => {
                selectElement.innerHTML += `<option value="${v.id}">${v.nombre}</option>`;
            });
        } catch (error) {
            selectElement.innerHTML = `<option value="">${error.message}</option>`;
        }
    };

    // ===================================
    // MANEJO DE EVENTOS (Acciones)
    // ===================================

    // --- Botones para abrir modales de CREACIÓN ---
    if (btnOpenProductoModal) {
        btnOpenProductoModal.addEventListener('click', () => {
            productoForm.reset();
            document.getElementById('producto-id').value = '';
            document.getElementById('producto-modal-title').textContent = 'Crear Producto';
            clearMsg(document.getElementById('producto-msg'));
            openModal(productoModal);
        });
    }

    if (btnOpenVeterinarioModal) {
        btnOpenVeterinarioModal.addEventListener('click', () => {
            veterinarioForm.reset();
            document.getElementById('veterinario-id').value = '';
            document.getElementById('veterinario-modal-title').textContent = 'Crear Veterinario';
            document.getElementById('veterinario-user-fields').style.display = 'block';
            document.getElementById('veterinario-correo').disabled = false;
            clearMsg(document.getElementById('veterinario-msg'));
            openModal(veterinarioModal);
        });
    }

    if (btnOpenCrearMascotaModal) {
        btnOpenCrearMascotaModal.addEventListener('click', () => {
            crearMascotaForm.reset();
            clearMsg(document.getElementById('crear-mascota-msg'));
            loadClientesDropdown(document.getElementById('crear-mascota-cliente'));
            openModal(crearMascotaModal);
        });
    }
    
    if (btnOpenCitaModal) {
        btnOpenCitaModal.addEventListener('click', () => {
            citaForm.reset();
            clearMsg(document.getElementById('cita-msg'));
            loadClientesDropdown(document.getElementById('cita-cliente'));
            loadVeterinariosDropdown(document.getElementById('cita-veterinario'));
            document.getElementById('cita-mascota').innerHTML = '<option value="">Seleccione un cliente primero...</option>';
            openModal(citaModal);
        });
    }

    // --- Delegación de eventos para EDITAR y BORRAR ---
    adminContent.addEventListener('click', async (e) => {
        const target = e.target;
        const id = target.dataset.id;
        if (!id) return;

        try {
            // Citas
            if (target.classList.contains('btn-approve')) {
                if (!confirm('¿Aprobar esta cita?')) return;
                await apiFetch(`/admin/citas/${id}/approve`, { method: 'PUT' });
                loadCitas();
            }
            else if (target.classList.contains('btn-reject')) {
                if (!confirm('¿Rechazar esta cita?')) return;
                await apiFetch(`/admin/citas/${id}/reject`, { method: 'PUT' });
                loadCitas();
            }
            else if (target.classList.contains('btn-delete-cita')) {
                if (!confirm('¿BORRAR esta cita?')) return;
                await apiFetch(`/admin/citas/${id}`, { method: 'DELETE' });
                loadCitas();
            }

            // Productos
            else if (target.classList.contains('btn-edit-producto')) {
                const data = dataCache.productos[id];
                if (data) {
                    document.getElementById('producto-id').value = data.id;
                    document.getElementById('producto-nombre').value = data.title;
                    document.getElementById('producto-descripcion').value = data.desc;
                    document.getElementById('producto-precio').value = data.price;
                    document.getElementById('producto-stock').value = data.stock;
                    document.getElementById('producto-imagen').value = data.imagen_url;
                    document.getElementById('producto-modal-title').textContent = 'Editar Producto';
                    clearMsg(document.getElementById('producto-msg'));
                    openModal(productoModal);
                }
            }
            else if (target.classList.contains('btn-delete-producto')) {
                if (!confirm('¿BORRAR este producto?')) return;
                await apiFetch(`/admin/productos/${id}`, { method: 'DELETE' });
                loadProductos();
            }

            // Usuarios
            else if (target.classList.contains('btn-edit-usuario')) {
                const data = dataCache.usuarios[id];
                if (data) {
                    document.getElementById('usuario-id').value = data.id;
                    document.getElementById('usuario-correo').value = data.correo;
                    document.getElementById('usuario-nombre').value = data.nombre;
                    document.getElementById('usuario-rol').value = data.rol;
                    clearMsg(document.getElementById('usuario-msg'));
                    openModal(usuarioModal);
                }
            }
            else if (target.classList.contains('btn-delete-usuario')) {
                if (!confirm('¿BORRAR este usuario? Esta acción es permanente y borrará sus datos asociados.')) return;
                await apiFetch(`/admin/usuarios/${id}`, { method: 'DELETE' });
                loadUsuarios();
            }

            // Mascotas
            else if (target.classList.contains('btn-edit-mascota')) {
                const data = dataCache.mascotas[id];
                if (data) {
                    document.getElementById('mascota-id').value = data.id;
                    document.getElementById('mascota-nombre').value = data.nombre;
                    document.getElementById('mascota-especie').value = data.especie;
                    document.getElementById('mascota-raza').value = data.raza || '';
                    document.getElementById('mascota-edad').value = data.edad || '';
                    document.getElementById('mascota-genero').value = data.genero || '';
                    clearMsg(document.getElementById('mascota-msg'));
                    openModal(mascotaModal);
                }
            }
            else if (target.classList.contains('btn-delete-mascota')) {
                if (!confirm('¿BORRAR esta mascota? Esto borrará su historial y citas.')) return;
                await apiFetch(`/admin/mascotas/${id}`, { method: 'DELETE' });
                loadMascotas();
            }
            else if (target.classList.contains('btn-carnet')) {
                const mascotaId = target.dataset.id;
                const mascotaNombre = target.dataset.nombre;
                openCarnetModal(mascotaId, mascotaNombre);
            }

            // Veterinarios
            else if (target.classList.contains('btn-edit-veterinario')) {
                const data = dataCache.veterinarios[id];
                if (data) {
                    document.getElementById('veterinario-id').value = data.id;
                    document.getElementById('veterinario-nombre').value = data.nombre;
                    document.getElementById('veterinario-especialidad').value = data.especialidad;
                    document.getElementById('veterinario-modal-title').textContent = 'Editar Veterinario';
                    document.getElementById('veterinario-user-fields').style.display = 'none';
                    document.getElementById('veterinario-correo').disabled = true;
                    clearMsg(document.getElementById('veterinario-msg'));
                    openModal(veterinarioModal);
                }
            }
            else if (target.classList.contains('btn-delete-veterinario')) {
                if (!confirm('¿BORRAR este veterinario? Esto borrará su cuenta de usuario.')) return;
                await apiFetch(`/admin/veterinarios/${id}`, { method: 'DELETE' });
                loadVeterinarios();
            }

        } catch (error) {
            alert(`Error: ${error.message}`);
        }
    });

    // --- Manejadores de envío de formularios ---
    if (productoForm) {
        productoForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const id = document.getElementById('producto-id').value;
            const msgEl = document.getElementById('producto-msg');
            showMsg(msgEl, 'Guardando...', false);
            const data = {
                nombre: document.getElementById('producto-nombre').value,
                descripcion: document.getElementById('producto-descripcion').value,
                precio: document.getElementById('producto-precio').value,
                stock: document.getElementById('producto-stock').value,
                imagen_url: document.getElementById('producto-imagen').value
            };
            try {
                const method = id ? 'PUT' : 'POST';
                const endpoint = id ? `/admin/productos/${id}` : '/admin/productos';
                const response = await apiFetch(endpoint, { method, body: JSON.stringify(data) });
                if (!response.ok) { const err = await response.json(); throw new Error(err.msg); }
                showMsg(msgEl, '¡Guardado!', false);
                loadProductos();
                setTimeout(() => closeModal(productoModal), 1000);
            } catch (error) { showMsg(msgEl, error.message, true); }
        });
    }

    if (usuarioForm) {
        usuarioForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const id = document.getElementById('usuario-id').value;
            const msgEl = document.getElementById('usuario-msg');
            showMsg(msgEl, 'Guardando...', false);
            const data = {
                nombre: document.getElementById('usuario-nombre').value,
                rol: document.getElementById('usuario-rol').value
            };
            try {
                const response = await apiFetch(`/admin/usuarios/${id}`, { method: 'PUT', body: JSON.stringify(data) });
                if (!response.ok) { const err = await response.json(); throw new Error(err.msg); }
                showMsg(msgEl, '¡Guardado!', false);
                loadUsuarios();
                setTimeout(() => closeModal(usuarioModal), 1000);
            } catch (error) { showMsg(msgEl, error.message, true); }
        });
    }

    if (mascotaForm) {
        mascotaForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const id = document.getElementById('mascota-id').value;
            const msgEl = document.getElementById('mascota-msg');
            showMsg(msgEl, 'Guardando...', false);
            const data = {
                nombre: document.getElementById('mascota-nombre').value,
                especie: document.getElementById('mascota-especie').value,
                raza: document.getElementById('mascota-raza').value,
                edad: document.getElementById('mascota-edad').value,
                genero: document.getElementById('mascota-genero').value,
            };
            try {
                const response = await apiFetch(`/admin/mascotas/${id}`, { method: 'PUT', body: JSON.stringify(data) });
                if (!response.ok) { const err = await response.json(); throw new Error(err.msg); }
                showMsg(msgEl, '¡Guardado!', false);
                loadMascotas();
                setTimeout(() => closeModal(mascotaModal), 1000);
            } catch (error) { showMsg(msgEl, error.message, true); }
        });
    }

    if (crearMascotaForm) {
        crearMascotaForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const msgEl = document.getElementById('crear-mascota-msg');
            showMsg(msgEl, 'Guardando...', false);
            const data = {
                cliente_id: document.getElementById('crear-mascota-cliente').value,
                nombre: document.getElementById('crear-mascota-nombre').value,
                especie: document.getElementById('crear-mascota-especie').value,
                raza: document.getElementById('crear-mascota-raza').value,
                edad: document.getElementById('crear-mascota-edad').value,
                genero: document.getElementById('crear-mascota-genero').value,
            };
            try {
                const response = await apiFetch(`/admin/mascotas`, { method: 'POST', body: JSON.stringify(data) });
                if (!response.ok) { const err = await response.json(); throw new Error(err.msg); }
                showMsg(msgEl, '¡Mascota Guardada!', false);
                loadMascotas();
                setTimeout(() => closeModal(crearMascotaModal), 1000);
            } catch (error) { showMsg(msgEl, error.message, true); }
        });
    }

    if (veterinarioForm) {
        veterinarioForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const id = document.getElementById('veterinario-id').value;
            const msgEl = document.getElementById('veterinario-msg');
            showMsg(msgEl, 'Guardando...', false);
            const data = {
                nombre: document.getElementById('veterinario-nombre').value,
                especialidad: document.getElementById('veterinario-especialidad').value,
                correo: document.getElementById('veterinario-correo').value,
                password: document.getElementById('veterinario-password').value
            };
            try {
                const method = id ? 'PUT' : 'POST';
                const endpoint = id ? `/admin/veterinarios/${id}` : '/admin/veterinarios';
                const response = await apiFetch(endpoint, { method, body: JSON.stringify(data) });
                if (!response.ok) { const err = await response.json(); throw new Error(err.msg); }
                showMsg(msgEl, '¡Guardado!', false);
                loadVeterinarios();
                setTimeout(() => closeModal(veterinarioModal), 1000);
            } catch (error) { showMsg(msgEl, error.message, true); }
        });
    }
    
    if (citaForm) {
        // Dropdown de cliente cambia -> cargar mascotas
        document.getElementById('cita-cliente').addEventListener('change', async (e) => {
            const clienteId = e.target.value;
            const mascotaSelect = document.getElementById('cita-mascota');
            if (!clienteId) {
                mascotaSelect.innerHTML = '<option value="">Seleccione un cliente primero...</option>';
                return;
            }
            try {
                const response = await apiFetch(`/admin/clientes/${clienteId}/mascotas`);
                if (!response.ok) throw new Error('Error al cargar mascotas');
                const mascotas = await response.json();
                mascotaSelect.innerHTML = '<option value="">Seleccione una mascota...</option>';
                mascotas.forEach(m => {
                    mascotaSelect.innerHTML += `<option value="${m.id}">${m.nombre}</option>`;
                });
            } catch (error) {
                mascotaSelect.innerHTML = `<option value="">${error.message}</option>`;
            }
        });

        // Enviar formulario de cita
        citaForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const msgEl = document.getElementById('cita-msg');
            showMsg(msgEl, 'Programando...', false);
            const data = {
                cliente_id: document.getElementById('cita-cliente').value,
                mascota_id: document.getElementById('cita-mascota').value,
                veterinario_id: document.getElementById('cita-veterinario').value,
                fecha: document.getElementById('cita-fecha').value,
                hora: document.getElementById('cita-hora').value,
                motivo: document.getElementById('cita-motivo').value,
            };
            try {
                const response = await apiFetch(`/admin/citas`, { method: 'POST', body: JSON.stringify(data) });
                if (!response.ok) { const err = await response.json(); throw new Error(err.msg); }
                showMsg(msgEl, '¡Cita Programada!', false);
                loadCitas();
                setTimeout(() => closeModal(citaModal), 1000);
            } catch (error) { showMsg(msgEl, error.message, true); }
        });
    }

    // ===================================
    // LÓGICA DE CARNET (CORREGIDA)
    // ===================================

    const openCarnetModal = async (mascotaId, mascotaNombre) => {
        document.getElementById('carnet-mascota-nombre').textContent = mascotaNombre;
        carnetForm.reset();
        vacunaForm.reset();
        carnetVacunasList.innerHTML = '<tr><td colspan="4">Cargando...</td></tr>';
        clearMsg(carnetMsg);
        
        // CORRECCIÓN: Almacenar el mascotaId
        currentMascotaId = mascotaId;
        openModal(carnetModal);

        try {
            const response = await apiFetch(`/admin/mascotas/${mascotaId}/historial`);
            if (!response.ok) throw new Error('No se pudo cargar el historial');
            const historial = await response.json();

            currentHistorialId = historial.id; 
            
            document.getElementById('carnet-historial-id').value = historial.id;
            document.getElementById('carnet-diagnostico').value = historial.diagnostico || '';
            document.getElementById('carnet-tratamiento').value = historial.tratamiento || '';

            renderVacunas(historial.vacunas);
        } catch (error) {
            showMsg(carnetMsg, error.message, true);
        }
    };

    const renderVacunas = (vacunas) => {
        carnetVacunasList.innerHTML = '';
        if (!vacunas || vacunas.length === 0) {
            carnetVacunasList.innerHTML = '<tr><td colspan="4">No hay vacunas registradas.</td></tr>';
            return;
        }
        vacunas.forEach(v => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${v.nombre}</td>
                <td>${v.fecha_aplicacion || 'N/A'}</td>
                <td>${v.fecha_proxima || 'N/A'}</td>
                <td>
                    <button class="btn small danger btn-delete-vacuna" data-id="${v.id}">X</button>
                </td>
            `;
            carnetVacunasList.appendChild(tr);
        });
    };

    if (carnetForm) {
        carnetForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const historialId = currentHistorialId;
            showMsg(carnetMsg, 'Guardando...', false);
            
            const data = {
                diagnostico: document.getElementById('carnet-diagnostico').value,
                tratamiento: document.getElementById('carnet-tratamiento').value,
            };

            try {
                const response = await apiFetch(`/admin/historial/${historialId}`, { method: 'PUT', body: JSON.stringify(data) });
                if (!response.ok) { const err = await response.json(); throw new Error(err.msg); }
                showMsg(carnetMsg, '¡Historial guardado!', false);
            } catch (error) {
                showMsg(carnetMsg, error.message, true);
            }
        });
    }

    if (vacunaForm) {
        vacunaForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const historialId = currentHistorialId;
            showMsg(carnetMsg, 'Añadiendo vacuna...', false);

            const data = {
                nombre: document.getElementById('vacuna-nombre').value,
                fecha_aplicacion: document.getElementById('vacuna-fecha-aplicacion').value,
                fecha_proxima: document.getElementById('vacuna-fecha-proxima').value || null,
            };

            try {
                const response = await apiFetch(`/admin/historial/${historialId}/vacuna`, { method: 'POST', body: JSON.stringify(data) });
                if (!response.ok) { const err = await response.json(); throw new Error(err.msg); }
                
                showMsg(carnetMsg, '¡Vacuna añadida!', false);
                vacunaForm.reset();
                
                // CORRECCIÓN: Usar el currentMascotaId almacenado para recargar
                const histResponse = await apiFetch(`/admin/mascotas/${currentMascotaId}/historial`);
                const historial = await histResponse.json();
                renderVacunas(historial.vacunas);

            } catch (error) {
                showMsg(carnetMsg, error.message, true);
            }
        });
    }

    if (carnetVacunasList) {
        carnetVacunasList.addEventListener('click', async (e) => {
            const target = e.target;
            if (target.classList.contains('btn-delete-vacuna')) {
                const vacunaId = target.dataset.id;
                if (!vacunaId || !confirm('¿Borrar esta vacuna?')) return;

                showMsg(carnetMsg, 'Borrando vacuna...', false);
                try {
                    const response = await apiFetch(`/admin/vacuna/${vacunaId}`, { method: 'DELETE' });
                    if (!response.ok) { const err = await response.json(); throw new Error(err.msg); }
                    target.closest('tr').remove();
                    showMsg(carnetMsg, 'Vacuna borrada', false);
                } catch (error) {
                    showMsg(carnetMsg, error.message, true);
                }
            }
        });
    }

    // --- INICIALIZACIÓN DEL PANEL ---
    const token = getToken();
    if (!token) {
        window.location.href = '/'; 
    } else {
        const payload = decodeToken(token);
        userRol = payload ? payload.rol : null;
        
        if (userRol !== 'admin' && userRol !== 'veterinario') {
             window.location.href = '/'; 
        }
        
        // Ocultar cosas si NO es admin
        if(userRol !== 'admin') {
            document.querySelectorAll('[data-page="usuarios"], [data-page="veterinarios"], [data-page="productos"]').forEach(el => el.style.display = 'none');
            if (btnOpenProductoModal) btnOpenProductoModal.style.display = 'none';
            if (btnOpenVeterinarioModal) btnOpenVeterinarioModal.style.display = 'none';
        }
        
        document.getElementById('admin-info').innerText = `Usuario: ${payload.sub} (Rol: ${userRol})`;
        showPage('dashboard');
    }
});