// ── 认证工具：供其他模块调用 ─────────────────────────────────
function getAuthHeaders() {
    const token = localStorage.getItem('token');
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    return headers;
}

// 401 响应自动清除过期 token（不刷新页面，避免死循环）
function handleAuthError(detail) {
    if (detail && (detail.includes('用户不存在') || detail.includes('无效的认证令牌') || detail.includes('未登录'))) {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
    }
}

// ── 侧栏登录状态管理 ─────────────────────────────────────────
(function() {
    const authBtn   = document.getElementById('sidebarAuthBtn');
    const authIcon  = document.getElementById('sidebarAuthIcon');
    const authLabel = document.getElementById('sidebarAuthLabel');

    function updateUI() {
        const t = localStorage.getItem('token');
        const u = localStorage.getItem('user');
        if (t && u) {
            if (authIcon)  authIcon.textContent  = u.charAt(0).toUpperCase();
            if (authLabel) authLabel.textContent = '退出';
            if (authBtn)   authBtn.classList.add('logged-in');
        } else {
            if (authIcon)  authIcon.textContent  = '👤';
            if (authLabel) authLabel.textContent = '登录';
            if (authBtn)   authBtn.classList.remove('logged-in');
        }
    }

    if (authBtn) {
        authBtn.addEventListener('click', () => {
            const t = localStorage.getItem('token');
            if (t) {
                localStorage.removeItem('token');
                localStorage.removeItem('user');
                // 退出账号时清理小老鼠前端缓存，防止下一位用户看到上一位的对话残影。
                Object.keys(localStorage).forEach(key => {
                    if (key.startsWith('mouse_chat_history_') || key.startsWith('riskmouse_agent_')) {
                        localStorage.removeItem(key);
                    }
                });
                updateUI();
                location.reload();
            } else {
                const modal = document.getElementById('authModal');
                if (modal) modal.classList.add('active');
            }
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
