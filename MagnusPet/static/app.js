// app.js

document.addEventListener("DOMContentLoaded", () => {
    
    // --- CONSTANTES Y ESTADO ---
    const API_URL = '/api'; 
    let activePage = "home";
    let cart = []; 

    // --- SELECTORES DEL DOM ---
    const pages = document.querySelectorAll('.page');
    const navButtons = document.querySelectorAll('.nav-btn');
    
    // Auth
    const openLoginBtn = document.getElementById('open-login');
    const logoutBtn = document.getElementById('logout-btn');
    const authModal = document.getElementById('auth-modal');
    const modalClose = document.getElementById('modal-close');
    const tabLogin = document.getElementById('tab-login');
    const tabRegister = document.getElementById('tab-register');
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    
    // Notificaciones
    const notifBtn = document.getElementById('notif-btn');
    const notifCount = document.getElementById('notif-count');
    const notifModal = document.getElementById('notif-modal');
    const notifClose = document.getElementById('notif-close');
    const notifList = document.getElementById('notif-list');

    // Carrito
    const cartBtn = document.getElementById('cart-btn');
    const cartCount = document.getElementById('cart-count');
    const cartModal = document.getElementById('cart-modal');
    const cartClose = document.getElementById('cart-close');
    const cartCheckoutBtn = document.getElementById('cart-checkout-btn');

    // Historial
    const historialModal = document.getElementById('historial-modal');
    const historialClose = document.getElementById('historial-close');

    // Perfil
    const profileForm = document.getElementById('profile-form');
    
    // Términos y Condiciones
    const termsModal = document.getElementById('terms-modal');
    const termsClose = document.getElementById('terms-close');
    const openTermsLink = document.getElementById('open-terms');
    const openPolicyLink = document.getElementById('open-policy');


    // --- FUNCIONES DE AUTENTICACIÓN Y API ---

    const getToken = () => localStorage.getItem('access_token');
    const saveToken = (token) => localStorage.setItem('access_token', token);
    const clearToken = () => localStorage.removeItem('access_token');

    /**
     * Decodifica un token JWT para obtener el payload.
     * No verifica la firma, solo decodifica.
     * @param {string} token El token JWT
     * @returns {object | null} El payload del token o null si es inválido
     */
    const decodeToken = (token) => {
        try {
            const payloadBase64 = token.split('.')[1];
            const decodedPayload = atob(payloadBase64);
            return JSON.parse(decodedPayload);
        } catch (e) {
            console.error("Error al decodificar el token:", e);
            return null;
        }
    };
    
    /** Fetch con manejo automático de tokens y errores 401 */
    const apiFetch = async (endpoint, options = {}) => {
        const token = getToken();
        
        // No poner Content-Type si es FormData (para subir archivos)
        const headers = options.body instanceof FormData ? {} : {
            'Content-Type': 'application/json',
            ...options.headers,
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        // --- CORRECCIÓN CLAVE ---
        // El `API_URL` se debe añadir aquí, en la función centralizada.
        const response = await fetch(`${API_URL}${endpoint}`, { ...options, headers });

        if (response.status === 401) { 
            logout();
            showMsg('login-msg', 'Tu sesión ha expirado. Por favor, inicia sesión de nuevo.');
            openAuth();
            throw new Error('Sesión expirada'); 
        }
        
        return response;
    };

    /** Muestra/oculta elementos según el estado de login y carga datos iniciales */
    const updateUI = () => {
        const token = getToken();
        if (token) {
            // Decodificar token para verificar rol
            const payload = decodeToken(token);
            const rol = payload ? payload.rol : 'cliente';

            // Si es admin o vet, no debería estar en esta página
            // Los ocultamos y preparamos para logout si es necesario
            if (rol === 'admin' || rol === 'veterinario') {
                openLoginBtn.classList.add('hidden');
                logoutBtn.classList.remove('hidden');
                notifBtn.classList.add('hidden');
                cartBtn.classList.add('hidden'); 
                document.querySelector('nav').style.display = 'none'; // Ocultar nav de cliente
            } else {
                // Comportamiento normal para cliente
                openLoginBtn.classList.add('hidden');
                logoutBtn.classList.remove('hidden');
                notifBtn.classList.remove('hidden');
                cartBtn.classList.remove('hidden'); 
                
                loadProfile();
                loadNotificaciones();
                if (activePage === 'mascotas') loadMascotas();
                if (activePage === 'citas') loadCitas();
            }
        } else {
            // No logueado
            openLoginBtn.classList.remove('hidden');
            logoutBtn.classList.add('hidden');
            notifBtn.classList.add('hidden');
            cartBtn.classList.add('hidden'); 

            clearProfileData();
            document.getElementById('mascotas-list').innerHTML = '<p>Inicia sesión para ver tus mascotas.</p>';
            document.getElementById('citas-list').innerHTML = '<p>Inicia sesión para ver tus citas.</p>';
            cart = [];
            updateCartBadge();
        }
    };

    /** Muestra un mensaje en los formularios */
    const showMsg = (elementId, message, isError = true) => {
        const msgEl = document.getElementById(elementId);
        if (msgEl) {
            msgEl.textContent = message;
            msgEl.style.color = isError ? '#e76f51' : 'var(--verde-oscuro-pet)';
            // Añadir clase de éxito para estilos
            msgEl.classList.toggle('success', !isError);
        }
    };

    // --- LÓGICA DE NAVEGACIÓN ---
    const showPage = (pageId) => {
        if (!pageId) return;
        pages.forEach(page => page.classList.add('hidden'));
        const newPage = document.getElementById(pageId);
        if (newPage) newPage.classList.remove('hidden');
        
        navButtons.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.route === pageId);
        });
        activePage = pageId;

        if (pageId === 'catalog') loadProducts();
        if (getToken()) {
            if (pageId === 'profile') loadProfile();
            if (pageId === 'mascotas') loadMascotas();
            if (pageId === 'citas') {
                loadCitas();
                loadMascotas(); 
                loadVeterinarios();
            }
        }
    };

    // --- LÓGICA DE AUTENTICACIÓN (FORMULARIOS) ---
    const openAuth = () => authModal.classList.remove('hidden');
    const closeAuth = () => { 
        authModal.classList.add('hidden');
        showMsg('reg-msg', ''); 
        showMsg('login-msg', '');
    }
    
    const setAuthTab = (tab) => {
        tabLogin.classList.toggle('active', tab === 'login');
        tabRegister.classList.toggle('active', tab === 'register');
        loginForm.classList.toggle('hidden', tab !== 'login');
        registerForm.classList.toggle('hidden', tab !== 'register');
        showMsg('reg-msg', ''); 
        showMsg('login-msg', '');
    };

    // FORMULARIO DE REGISTRO
    registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const termsCheckbox = document.getElementById('reg-terms');
        if (!termsCheckbox.checked) {
            showMsg('reg-msg', 'Debes aceptar los términos y condiciones para registrarte.');
            return; 
        }

        showMsg('reg-msg', 'Registrando...', false);
        const data = {
            name: document.getElementById('reg-name').value,
            lastname: document.getElementById('reg-lastname').value,
            email: document.getElementById('reg-email').value,
            phone: document.getElementById('reg-phone').value,
            password: document.getElementById('reg-password').value,
        };
        try {
            // ================== INICIO DE LA CORRECCIÓN ==================
            // Usamos apiFetch y solo pasamos el endpoint, no la URL completa
            const response = await apiFetch('/register', {
                method: 'POST',
                body: JSON.stringify(data),
            });
            // ================== FIN DE LA CORRECCIÓN ==================

            const result = await response.json();
            if (!response.ok) throw new Error(result.msg);
            showMsg('reg-msg', '¡Registro exitoso! Ahora puedes iniciar sesión.', false);
            e.target.reset();
            setTimeout(() => setAuthTab('login'), 1500);
        } catch (error) {
            showMsg('reg-msg', error.message || 'Error en el registro.');
        }
    });

   // En app.js

// FORMULARIO DE LOGIN
loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    console.log("--- [DEBUG] Botón 'Entrar' presionado. ---"); // DEBUG
    showMsg('login-msg', 'Iniciando sesión...', false);
    
    const data = {
        identifier: document.getElementById('login-identifier').value,
        password: document.getElementById('login-password').value,
    };
    
    console.log("--- [DEBUG] Enviando estos datos al servidor:", data); // DEBUG

    try {
        const response = await fetch(`${API_URL}/login`, { //
            method: 'POST', //
            headers: { 'Content-Type': 'application/json' }, //
            body: JSON.stringify(data), //
        });

        console.log("--- [DEBUG] Respuesta 'cruda' recibida del servidor:", response); // DEBUG

        if (!response.ok) {
            // Si la respuesta NO es OK (ej: 401, 500)
            console.error("--- [DEBUG] Respuesta no-OK. Status:", response.status); // DEBUG
            // Intentamos leerla como JSON para el mensaje de error
            const errorResult = await response.json();
            console.error("--- [DEBUG] Error (JSON):", errorResult); // DEBUG
            throw new Error(errorResult.msg || `Error ${response.status}`);
        }
        
        // Si la respuesta SÍ es OK (ej: 200)
        const result = await response.json();
        console.log("--- [DEBUG] Respuesta OK (JSON):", result); // DEBUG
        
        saveToken(result.access_token);
        
        // --- LÓGICA DE REDIRECCIÓN POR ROL ---
        const payload = decodeToken(result.access_token);
        const rol = payload ? payload.rol : 'cliente';

        if (rol === 'admin' || rol === 'veterinario') {
            showMsg('login-msg', '¡Bienvenido! Redirigiendo...', false);
            setTimeout(() => {
                window.location.href = '/admin'; 
            }, 1000);
        } else {
            showMsg('login-msg', '¡Bienvenido!', false);
            setTimeout(() => {
                closeAuth();
                updateUI();
                showPage('profile');
            }, 1000);
        }
        // --- FIN DE LA LÓGICA DE REDIRECCIÓN ---

    } catch (error) {
        // Aquí es donde estás cayendo.
        console.error("--- [DEBUG] ERROR EN EL BLOQUE CATCH ---", error); // DEBUG
        showMsg('login-msg', error.message || 'Credenciales incorrectas.');
        console.error("--- [DEBUG] El error de arriba (Unexpected token '<') significa que la 'response' de la línea 233 era HTML, no JSON."); // DEBUG
    }
});

    // --- LISTENER PARA EL BOTÓN DE ADMIN ---
    const adminLoginBtn = document.getElementById('btn-login-admin');
    if (adminLoginBtn) {
        adminLoginBtn.addEventListener('click', () => {
            document.getElementById('login-identifier').value = 'admin@magnus.pet';
            document.getElementById('login-password').value = 'admin123';
            showMsg('login-msg', 'Credenciales de administrador cargadas. Haz clic en "Entrar".', false);
        });
    }

    const logout = () => {
        clearToken();
        updateUI();
        showPage('home');
    }
    logoutBtn.addEventListener('click', logout);

    // --- LÓGICA DE PERFIL EDITABLE ---
    const loadProfile = async () => {
        showMsg('profile-msg', 'Cargando perfil...', false);
        try {
            const response = await apiFetch('/profile');
            if (!response.ok) throw new Error('No se pudo cargar el perfil');
            const data = await response.json();
            
            document.getElementById('profile-name').value = data.nombre || '';
            document.getElementById('profile-email').value = data.correo || '';
            document.getElementById('profile-phone').value = data.telefono || '';
            
            document.getElementById('profile-wallet').textContent = data.wallet.toLocaleString() || '0';
            document.getElementById('profile-coins').textContent = data.coins.toLocaleString() || '0';
            showMsg('profile-msg', '', false); 
        } catch (error) {
            showMsg('profile-msg', 'Error al cargar el perfil.', true);
            console.error(error.message);
        }
    };
    
    const clearProfileData = () => {
        profileForm.reset();
        document.getElementById('profile-wallet').textContent = '0';
        document.getElementById('profile-coins').textContent = '0';
    };

    profileForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        showMsg('profile-msg', 'Actualizando...', false);
        const data = {
            nombre: document.getElementById('profile-name').value,
            telefono: document.getElementById('profile-phone').value,
        };

        try {
            const response = await apiFetch('/profile', {
                method: 'PUT',
                body: JSON.stringify(data),
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.msg);

            showMsg('profile-msg', '¡Perfil actualizado con éxito!', false);
        } catch (error) {
            showMsg('profile-msg', error.message || 'Error al actualizar.');
        }
    });


    // --- LÓGICA DE PRODUCTOS Y CARRITO ---

    const loadProducts = async () => {
        const productList = document.getElementById('product-list');
        productList.innerHTML = '<p>Cargando productos...</p>';
        try {
            // Nota: /products es una ruta pública, así que fetch() normal está bien,
            // pero usar apiFetch también es correcto.
            const response = await apiFetch('/products'); 
            if (!response.ok) throw new Error('No se pudo cargar productos');
            const products = await response.json();
            
            productList.innerHTML = ''; 
            if (products.length === 0) {
                productList.innerHTML = '<p>No hay productos disponibles.</p>'; return;
            }
            
            products.forEach(p => {
                const card = document.createElement('div');
                card.className = 'product';
                card.innerHTML = `
                    <img src="${p.imagen_url}" alt="${p.title}" class="product-image">
                    <div class="product-info">
                        <div class="title">${p.title}</div>
                        <div class="desc">${p.desc}</div>
                        <div class="price">$${p.price.toLocaleString()}</div>
                        <button class="btn small btn-comprar" data-id="${p.id}" data-title="${p.title}" data-price="${p.price}">Comprar</button>
                    </div>
                `;
                productList.appendChild(card);
            });
        } catch (error) {
            productList.innerHTML = `<p>Error al cargar productos: ${error.message}</p>`;
        }
    };

    const addToCart = (product) => {
        if (!getToken()) {
            alert('Debes iniciar sesión para añadir productos al carrito.');
            openAuth();
            return;
        }

        const existingItem = cart.find(item => item.id === product.id);
        if (existingItem) {
            existingItem.cantidad++;
        } else {
            cart.push({
                id: product.id,
                title: product.title,
                price: product.price,
                cantidad: 1
            });
        }
        updateCartBadge();
        renderCartModal();
        cartModal.classList.remove('hidden'); 
    };

    const updateCartBadge = () => {
        const totalItems = cart.reduce((sum, item) => sum + item.cantidad, 0);
        cartCount.textContent = `(${totalItems})`;
    };

    const renderCartModal = () => {
        const cartItemsList = document.getElementById('cart-items-list');
        const cartTotal = document.getElementById('cart-total');
        
        cartItemsList.innerHTML = '';
        if (cart.length === 0) {
            cartItemsList.innerHTML = '<p>Tu carrito está vacío.</p>';
            cartTotal.textContent = '0';
            cartCheckoutBtn.disabled = true;
            return;
        }
        cartCheckoutBtn.disabled = false;

        let total = 0;
        cart.forEach(item => {
            const itemEl = document.createElement('div');
            itemEl.className = 'cart-item';
            itemEl.innerHTML = `
                <span>${item.title} (x${item.cantidad})</span>
                <span>$${(item.price * item.cantidad).toLocaleString()}</span>
            `;
            cartItemsList.appendChild(itemEl);
            total += item.price * item.cantidad;
        });

        cartTotal.textContent = total.toLocaleString();
    };

    const checkout = async () => {
        showMsg('cart-msg', 'Procesando...', false);
        try {
            const cartData = cart.map(item => ({ id: item.id, cantidad: item.cantidad }));
            const response = await apiFetch('/checkout', { // Asumiendo que esta ruta existe
                method: 'POST',
                body: JSON.stringify({ cart: cartData }),
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.msg);

            showMsg('cart-msg', `¡Compra #${result.factura_id} finalizada!`, false);
            cart = []; 
            updateCartBadge();
            renderCartModal();
            loadProducts(); 
        } catch (error) {
            showMsg('cart-msg', error.message || 'Error en la compra.');
        }
    };


    // --- LÓGICA DE MASCOTAS ---

    const loadMascotas = async () => {
        const mascotasList = document.getElementById('mascotas-list');
        const mascotaSelect = document.getElementById('cita-mascota');
        mascotasList.innerHTML = 'Cargando...';
        mascotaSelect.innerHTML = '<option value="">Selecciona una mascota...</option>';

        try {
            const response = await apiFetch('/mascotas');
            if (!response.ok) throw new Error('Error al cargar mascotas');
            const mascotas = await response.json();
            
            mascotasList.innerHTML = '';
            if (mascotas.length === 0) {
                mascotasList.innerHTML = '<p>Aún no tienes mascotas registradas.</p>';
            }

            mascotas.forEach(m => {
                const card = document.createElement('div');
                card.className = 'mascota-card';
                card.innerHTML = `
                    <img src="${m.imagen_url}" alt="Foto de ${m.nombre}" class="mascota-card-img" onerror="this.src='/static/pet_default.png'">
                    <div class="mascota-card-info">
                        <strong>${m.nombre}</strong>
                        <span>${m.especie} (${m.raza || 'N/A'})</span>
                        <small>Edad: ${m.edad || 'N/A'} años, Género: ${m.genero || 'N/A'}</small>
                    </div>
                    
                    <form class="photo-upload-form">
                      <label for="photo-${m.id}" class="btn-label">Elegir foto...</label>
                      <input type="file" name="photo" id="photo-${m.id}" class="photo-input" accept="image/png, image/jpeg">
                      <button type="button" class="btn small btn-upload-photo" data-id="${m.id}">Subir Foto</button>
                    </form>

                    <div class="mascota-card-actions">
                        <button class="btn small ghost btn-historial" data-id="${m.id}">Ver Carnet</button>
                        <button class="btn small danger btn-delete-mascota" data-id="${m.id}">Eliminar</button>
                    </div>
                `;
                mascotasList.appendChild(card);
                
                // Rellenar el select de citas
                const option = document.createElement('option');
                option.value = m.id;
                option.textContent = `${m.nombre} (${m.especie})`;
                mascotaSelect.appendChild(option);
            });
        } catch (error) {
            mascotasList.innerHTML = `<p>${error.message}</p>`;
        }
    };
    
    // FORMULARIO DE REGISTRO DE MASCOTA
    document.getElementById('mascota-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        showMsg('mascota-msg', 'Guardando...', false);
        const data = {
            nombre: document.getElementById('mascota-nombre').value,
            especie: document.getElementById('mascota-especie').value,
            raza: document.getElementById('mascota-raza').value,
            edad: document.getElementById('mascota-edad').value,
            genero: document.getElementById('mascota-genero').value,
        };
        try {
            const response = await apiFetch('/mascotas', { method: 'POST', body: JSON.stringify(data) });
            if (!response.ok) {
                const result = await response.json();
                throw new Error(result.msg || 'Error al guardar.');
            }
            showMsg('mascota-msg', '¡Mascota registrada!', false);
            e.target.reset(); 
            loadMascotas(); 
            setTimeout(() => showMsg('mascota-msg', ''), 2000);
        } catch (error) {
            showMsg('mascota-msg', error.message);
        }
    });

    /** Elimina una mascota (Llamado por delegado) */
    const deleteMascota = async (mascotaId) => {
        if (!confirm('¿Estás seguro de que quieres eliminar esta mascota? Esta acción eliminará también sus citas e historial clínico.')) {
            return;
        }
        try {
            const response = await apiFetch(`/mascotas/${mascotaId}`, { method: 'DELETE' });
            if (!response.ok) {
                const result = await response.json();
                throw new Error(result.msg || 'Error al eliminar');
            }
            loadMascotas(); 
        } catch (error) {
            alert(error.message);
        }
    };

    /** Sube la foto de la mascota */
    const uploadPetPhoto = async (mascotaId, file) => {
        const formData = new FormData();
        formData.append('photo', file);

        try {
            const response = await apiFetch(`/mascotas/${mascotaId}/upload`, {
                method: 'POST',
                body: formData, 
            });
            
            const result = await response.json();
            if (!response.ok) throw new Error(result.msg);

            alert('¡Foto actualizada!');
            loadMascotas(); 

        } catch (error) {
            alert(`Error al subir la foto: ${error.message}`);
        }
    };


    // --- LÓGICA DE CITAS ---

    const loadCitas = async () => {
        const citasList = document.getElementById('citas-list');
        citasList.innerHTML = 'Cargando...';
        try {
            const response = await apiFetch('/citas');
            if (!response.ok) throw new Error('Error al cargar citas');
            const citas = await response.json();
            
            citasList.innerHTML = '';
            if (citas.length === 0) {
                citasList.innerHTML = '<p>No tienes citas programadas.</p>'; return;
            }

            citas.forEach(c => {
                const item = document.createElement('div');
                item.className = 'cita-item';
                const estadoClass = `status-${c.estado.toLowerCase().replace(' ', '-')}`;
                item.innerHTML = `
                    <p><strong>Mascota:</strong> ${c.mascota_nombre || 'N/A'}</p>
                    <p><strong>Fecha:</strong> ${c.fecha} a las ${c.hora.substring(0, 5)}</p>
                    <p><strong>Motivo:</strong> ${c.motivo}</p>
                    <p><strong>Veterinario:</strong> ${c.veterinario_nombre || 'Por asignar'}</p>
                    <span class="status-badge ${estadoClass}">${c.estado}</span>`;
                citasList.appendChild(item);
            });
        } catch (error) {
            citasList.innerHTML = `<p>${error.message}</p>`;
        }
    };

    const loadVeterinarios = async () => {
        const vetSelect = document.getElementById('cita-veterinario');
        vetSelect.innerHTML = '<option value="">Cargando veterinarios...</option>';
        try {
            const response = await apiFetch('/veterinarios');
            if (!response.ok) return;
            const vets = await response.json();
            vetSelect.innerHTML = '<option value="">Cualquier veterinario</option>';
            vets.forEach(v => {
                const option = document.createElement('option');
                option.value = v.id;
                option.textContent = `${v.nombre} (${v.especialidad})`;
                vetSelect.appendChild(option);
            });
        } catch (error) { console.error('Error cargando veterinarios:', error); }
    };
    
    document.getElementById('cita-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        showMsg('cita-msg', 'Enviando solicitud...', false);
        const data = {
            mascota_id: document.getElementById('cita-mascota').value,
            veterinario_id: document.getElementById('cita-veterinario').value || null, // Enviar null si no se selecciona
            fecha: document.getElementById('cita-fecha').value,
            hora: document.getElementById('cita-hora').value,
            motivo: document.getElementById('cita-motivo').value,
        };
        try {
            const response = await apiFetch('/citas', { method: 'POST', body: JSON.stringify(data) });
            if (!response.ok) {
                const result = await response.json();
                throw new Error(result.msg || 'Error al agendar.');
            }
            showMsg('cita-msg', '¡Solicitud enviada! Recibirás una notificación cuando sea aprobada.', false);
            e.target.reset(); 
            loadCitas(); 
            loadNotificaciones(); 
            setTimeout(() => showMsg('cita-msg', ''), 3000);
        } catch (error) {
            showMsg('cita-msg', error.message);
        }
    });

    // --- LÓGICA DE NOTIFICACIONES ---
    const loadNotificaciones = async () => {
        notifList.innerHTML = 'Cargando...';
        try {
            const response = await apiFetch('/notificaciones');
            if (!response.ok) throw new Error('Error al cargar notificaciones');
            const notifs = await response.json();
            
            notifList.innerHTML = '';
            notifCount.textContent = `(${notifs.length})`;
            
            if (notifs.length === 0) {
                notifList.innerHTML = '<p>No tienes notificaciones nuevas.</p>'; return;
            }
            
            notifs.forEach(n => {
                const item = document.createElement('div');
                item.className = 'notif-item';
                item.innerHTML = `<p>${n.mensaje}</p><small>${new Date(n.fecha).toLocaleString()}</small>`;
                notifList.appendChild(item);
            });
        } catch (error) {
            notifList.innerHTML = `<p>${error.message}</p>`;
        }
    };
    
    // --- LÓGICA DE HISTORIAL (VACUNAS) ---
    const loadHistorial = async (mascotaId) => {
        document.getElementById('historial-mascota-nombre').textContent = '...';
        document.getElementById('historial-diagnostico').textContent = 'Cargando...';
        document.getElementById('historial-tratamiento').textContent = 'Cargando...';
        document.getElementById('vacunas-list').innerHTML = '';
        historialModal.classList.remove('hidden');

        try {
            const response = await apiFetch(`/mascotas/${mascotaId}/historial`);
            if (!response.ok) {
                 const result = await response.json();
                 throw new Error(result.msg || 'Error al cargar historial');
            }
            const data = await response.json();

            document.getElementById('historial-mascota-nombre').textContent = data.mascota_nombre;
            document.getElementById('historial-diagnostico').textContent = data.diagnostico || "Sin diagnóstico registrado.";
            document.getElementById('historial-tratamiento').textContent = data.tratamiento || "Sin tratamiento registrado.";
            
            const vacunasList = document.getElementById('vacunas-list');
            if (!data.vacunas || data.vacunas.length === 0) {
                vacunasList.innerHTML = '<tr><td colspan="3">No hay vacunas registradas.</td></tr>';
                return;
            }

            data.vacunas.forEach(v => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${v.nombre}</td>
                    <td>${v.fecha_aplicacion || 'N/A'}</td>
                    <td>${v.fecha_proxima || 'N/A'}</td>`;
                vacunasList.appendChild(tr);
            });
        } catch (error) {
            document.getElementById('historial-diagnostico').textContent = error.message;
        }
    };
    
    // --- EVENT LISTENERS GLOBALES ---

    // Navegación
    navButtons.forEach(btn => btn.addEventListener('click', (e) => showPage(e.target.dataset.route)));
    document.querySelectorAll('.hero-btns button[data-route]').forEach(btn => btn.addEventListener('click', (e) => showPage(e.target.dataset.route)));

    // Modales Auth
    openLoginBtn.addEventListener('click', () => { 
        setAuthTab('login');
        openAuth();
    });
    modalClose.addEventListener('click', closeAuth);
    tabLogin.addEventListener('click', () => setAuthTab('login'));
    tabRegister.addEventListener('click', () => setAuthTab('register'));
    
    // Modales Notificaciones
    notifBtn.addEventListener('click', () => notifModal.classList.remove('hidden'));
    notifClose.addEventListener('click', () => notifModal.classList.add('hidden'));

    // Modales Carrito
    cartBtn.addEventListener('click', () => {
        renderCartModal();
        cartModal.classList.remove('hidden');
    });
    cartClose.addEventListener('click', () => cartModal.classList.add('hidden'));
    cartCheckoutBtn.addEventListener('click', checkout);

    // Modal Historial
    historialClose.addEventListener('click', () => historialModal.classList.add('hidden'));

    // Listeners para Modal de Términos
    const openTermsModal = (e) => {
        e.preventDefault(); 
        termsModal.classList.remove('hidden');
    };
    openTermsLink.addEventListener('click', openTermsModal);
    openPolicyLink.addEventListener('click', openTermsModal);
    termsClose.addEventListener('click', () => termsModal.classList.add('hidden'));

    // Listeners delegados para botones dinámicos
    document.body.addEventListener('click', (e) => {
        
        // Botón "Comprar" en catálogo
        const comprarBtn = e.target.closest('.btn-comprar');
        if (comprarBtn) {
            addToCart({
                id: parseInt(comprarBtn.dataset.id),
                title: comprarBtn.dataset.title,
                price: parseFloat(comprarBtn.dataset.price)
            });
            return;
        }

        // Botón "Ver Carnet" en mascotas
        const historialBtn = e.target.closest('.btn-historial');
        if (historialBtn) {
            loadHistorial(historialBtn.dataset.id);
            return;
        }
        
        // Botón "Eliminar" en mascotas
        const deleteBtn = e.target.closest('.btn-delete-mascota');
        if (deleteBtn) {
            deleteMascota(deleteBtn.dataset.id);
            return;
        }

        // Listener para botón de subir foto
        const uploadBtn = e.target.closest('.btn-upload-photo');
        if (uploadBtn) {
            const mascotaId = uploadBtn.dataset.id;
            const form = uploadBtn.closest('.photo-upload-form');
            const fileInput = form.querySelector('.photo-input');
            const file = fileInput.files[0];

            if (!file) {
                alert('Por favor, selecciona un archivo primero.');
                return;
            }
            
            uploadPetPhoto(mascotaId, file);
            return;
        }
    });

    // --- INICIALIZACIÓN ---
    updateUI();
    showPage(activePage);
    if (activePage === 'home' || activePage === 'catalog') {
        loadProducts();
    }
});