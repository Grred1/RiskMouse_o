function fmtMoney(val) {
    if (val === 0) return '-';
    const yi = val / 1e8;
    if (yi >= 1) return yi.toFixed(2) + ' 亿';
    const wan = val / 1e4;
    return wan.toFixed(2) + ' 万';
}

function fmtNum(val) {
    if (val === null || val === undefined) return '-';
    if (val === 0) return '0';
    const abs = Math.abs(val);
    if (abs >= 1e8) return (val / 1e8).toFixed(2) + '亿';
    if (abs >= 1e4) return (val / 1e4).toFixed(2) + '万';
    return val.toFixed(2);
}

function switchFeature(feature) {
    // nav-tabs 已移除，以下保留向后兼容
    document.querySelectorAll('.nav-tab').forEach(el => el.classList.remove('active'));
    const navTab = document.querySelector(`.nav-tab[data-feature="${feature}"]`);
    if (navTab) navTab.classList.add('active');
    document.querySelectorAll('.feature-section').forEach(el => el.classList.remove('active'));
    const section = document.getElementById(`feature-${feature}`);
    if (section) section.classList.add('active');
    // 同步侧边栏激活状态
    document.querySelectorAll('.sidebar-btn').forEach(el => el.classList.remove('active'));
    const sid = document.getElementById('sidebar' + feature.charAt(0).toUpperCase() + feature.slice(1));
    if (sid) sid.classList.add('active');
    // 切换后收起侧栏（手机端遮罩消失露出内容）
    if (window.innerWidth <= 768) {
        document.body.classList.add('sidebar-hidden');
    }
    updateSidebarToggleIcon();
}

function toggleMobileSidebar() {
    document.body.classList.toggle('sidebar-hidden');
    updateSidebarToggleIcon();
}

function updateSidebarToggleIcon() {
    const toggle = document.getElementById('sidebarToggle');
    if (!toggle) return;
    const hidden = document.body.classList.contains('sidebar-hidden');
    if (window.innerWidth <= 768) {
        toggle.textContent = hidden ? '▶' : '▼';
    } else {
        toggle.textContent = hidden ? '▶' : '◀';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    updateSidebarToggleIcon();
    window.addEventListener('resize', updateSidebarToggleIcon);
});
