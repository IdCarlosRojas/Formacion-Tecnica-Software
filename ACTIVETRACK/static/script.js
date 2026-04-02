document.addEventListener('DOMContentLoaded', () => {
    
    // --- 1. LÓGICA DE MODALES (LOGIN Y REGISTER) ---
    const loginModal = document.getElementById('login-modal');
    const registerModal = document.getElementById('register-modal');
    const openBtnHero = document.getElementById('open-modal-btn-hero');
    
    const closeLoginBtn = loginModal ? loginModal.querySelector('.close-btn') : null;
    const closeRegisterBtn = registerModal ? registerModal.querySelector('.close-btn') : null;
    const registerLink = document.getElementById('register-link'); 

    const openLoginModal = (e) => {
        if (e) e.preventDefault(); 
        if(loginModal) loginModal.style.display = "block";
    };

    if (openBtnHero) openBtnHero.addEventListener('click', openLoginModal);

    if (closeLoginBtn) {
        closeLoginBtn.addEventListener('click', () => {
            if(loginModal) loginModal.style.display = "none";
        });
    }
    
    if (registerLink) {
        registerLink.addEventListener('click', (e) => {
            e.preventDefault(); 
            if(loginModal) loginModal.style.display = "none"; 
            if(registerModal) registerModal.style.display = "block"; 
        });
    }
    
    if (closeRegisterBtn) {
        closeRegisterBtn.addEventListener('click', () => {
            if(registerModal) registerModal.style.display = "none";
        });
    }

    // --- 2. LÓGICA MODAL DE INSTRUCTORES (¡NUEVO!) ---
    const instructorModal = document.getElementById('instructor-modal');
    const openInstructorBtn = document.getElementById('instructor-login-btn');
    const closeInstructorBtn = instructorModal ? instructorModal.querySelector('.close-btn') : null;
    
    if (openInstructorBtn) {
        openInstructorBtn.addEventListener('click', () => {
            if(loginModal) loginModal.style.display = "none"; // Ocultar login
            if (instructorModal) instructorModal.style.display = 'block'; // Mostrar instructores
        });
    }
    if (closeInstructorBtn) {
        closeInstructorBtn.addEventListener('click', () => {
            if (instructorModal) instructorModal.style.display = 'none';
        });
    }

    // --- ¡¡NUEVA LÓGICA PARA MODAL DE TÉRMINOS!! ---
    const termsModal = document.getElementById('terms-modal');
    const openTermsLink = document.getElementById('open-terms-link');
    const closeTermsBtn = termsModal ? termsModal.querySelector('.close-btn') : null;
    const closeTermsBtnBottom = termsModal ? termsModal.querySelector('.close-terms-btn') : null; // Botón "Cerrar" de abajo

    if (openTermsLink) {
        openTermsLink.addEventListener('click', (e) => {
            e.preventDefault();
            if (termsModal) termsModal.style.display = "block";
        });
    }
    if (closeTermsBtn) {
        closeTermsBtn.addEventListener('click', () => {
            if (termsModal) termsModal.style.display = "none";
        });
    }
    if (closeTermsBtnBottom) {
        closeTermsBtnBottom.addEventListener('click', () => {
            if (termsModal) termsModal.style.display = "none";
        });
    }
    // --- FIN DE LA NUEVA LÓGICA ---


    // --- 3. CERRAR MODALES AL HACER CLIC FUERA ---
    window.addEventListener('click', (event) => {
        if (event.target === loginModal) {
            loginModal.style.display = "none";
        }
        if (event.target === registerModal) {
            registerModal.style.display = "none";
        }
        if (event.target === instructorModal) {
            instructorModal.style.display = "none";
        }
        // ¡¡NUEVO!!
        if (event.target === termsModal) {
            termsModal.style.display = "none";
        }
    });

    // --- 4. LÓGICA DE INICIO RÁPIDO (¡NUEVO!) ---

    // Función auxiliar para rellenar el formulario
    function fillLoginForm(email, password) {
        const loginForm = document.getElementById('login-form');
        if (loginForm) {
            loginForm.querySelector('input[name="username"]').value = email;
            loginForm.querySelector('input[name="password"]').value = password;
        }
    }

    // Botón de Admin
    document.getElementById('admin-login-btn')?.addEventListener('click', () => {
        fillLoginForm('admin@activetrack.com', 'admin123');
        openLoginModal(); // Asegurarse de que el modal de login esté visible
    });
    
    // Botón de Demo User
    document.getElementById('demo-login-btn')?.addEventListener('click', () => {
        fillLoginForm('carlos.demo@activetrack.com', 'demo123'); // Corregido al email del demo user
        openLoginModal();
    });

    // Botones de selección de Instructor
    document.querySelectorAll('.instructor-choice').forEach(btn => {
        btn.addEventListener('click', () => {
            const email = btn.dataset.email;
            const pass = btn.dataset.pass;
            fillLoginForm(email, pass);
            
            if (instructorModal) instructorModal.style.display = 'none'; // Ocultar modal instructor
            openLoginModal(); // Mostrar modal login con datos
        });
    });

});