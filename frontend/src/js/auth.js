// ── 认证工具：供其他模块调用 ─────────────────────────────────
function getAuthHeaders() {
    const token = localStorage.getItem('token');
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    return headers;
}

// ── header 登录状态管理 ──────────────────────────────────────
(function() {
    const usernameEl = document.getElementById('headerUsername');
    const logoutBtn  = document.getElementById('headerLogoutBtn');
    const loginBtn   = document.getElementById('headerLoginBtn');

    function updateUI() {
        const t = localStorage.getItem('token');
        const u = localStorage.getItem('user');
        if (t && u) {
            if (usernameEl) { usernameEl.textContent = u; usernameEl.style.display = ''; }
            if (logoutBtn)  logoutBtn.style.display = '';
            if (loginBtn)   loginBtn.style.display = 'none';
        } else {
            if (usernameEl) usernameEl.style.display = 'none';
            if (logoutBtn)  logoutBtn.style.display = 'none';
            if (loginBtn)   loginBtn.style.display = '';
        }
    }

    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            updateUI();
            location.reload();
        });
    }

    if (loginBtn) {
        loginBtn.addEventListener('click', () => {
            const modal = document.getElementById('authModal');
            if (modal) modal.classList.add('active');
        });
    }

    updateUI();
})();

// ── 登录/注册弹窗逻辑 ────────────────────────────────────────
(function() {
    const authModal       = document.getElementById('authModal');
    if (!authModal) return;

    const authModalTitle  = document.getElementById('authModalTitle');
    const authModalSub    = document.getElementById('authModalSub');
    const authUsernameInput = document.getElementById('authUsernameInput');
    const authPasswordInput = document.getElementById('authPasswordInput');
    const authSubmitBtn   = document.getElementById('authSubmitBtn');
    const authToggleBtn   = document.getElementById('authToggleBtn');
    const authError       = document.getElementById('authError');
    const authSuccess     = document.getElementById('authSuccess');

    let isLoginMode = true;

    function showError(msg) {
        authError.textContent = msg;
        authError.classList.add('show');
        authSuccess.classList.remove('show');
    }
    function showSuccess(msg) {
        authSuccess.textContent = msg;
        authSuccess.classList.add('show');
        authError.classList.remove('show');
    }
    function hideMessages() {
        authError.classList.remove('show');
        authSuccess.classList.remove('show');
    }

    document.getElementById('authModalClose').addEventListener('click', () => {
        authModal.classList.remove('active');
    });
    authModal.addEventListener('click', (e) => {
        if (e.target === authModal) authModal.classList.remove('active');
    });

    authToggleBtn.addEventListener('click', () => {
        isLoginMode = !isLoginMode;
        hideMessages();
        if (isLoginMode) {
            authModalTitle.textContent = '登录';
            authModalSub.textContent   = '登录以使用自选股等个性化功能';
            authSubmitBtn.textContent  = '登录';
            authToggleBtn.textContent  = '没有账号？去注册';
        } else {
            authModalTitle.textContent = '注册';
            authModalSub.textContent   = '创建账号以使用全部功能';
            authSubmitBtn.textContent  = '注册';
            authToggleBtn.textContent  = '已有账号？去登录';
        }
    });

    authSubmitBtn.addEventListener('click', async () => {
        const username = authUsernameInput.value.trim();
        const password = authPasswordInput.value.trim();
        if (!username || !password) { showError('请填写用户名和密码'); return; }
        hideMessages();
        const endpoint = isLoginMode ? '/api/auth/login' : '/api/auth/register';
        try {
            const res  = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
            });
            const data = await res.json();
            if (!res.ok) { showError(data.detail || '操作失败'); return; }
            if (isLoginMode) {
                localStorage.setItem('token', data.token);
                localStorage.setItem('user', data.username);
                authModal.classList.remove('active');
                authUsernameInput.value = '';
                authPasswordInput.value = '';
                location.reload();
            } else {
                showSuccess('注册成功，请登录');
                isLoginMode = true;
                authModalTitle.textContent = '登录';
                authModalSub.textContent   = '登录以使用自选股等个性化功能';
                authSubmitBtn.textContent  = '登录';
                authToggleBtn.textContent  = '没有账号？去注册';
            }
        } catch (err) {
            showError('网络错误，请稍后重试');
        }
    });
})();
