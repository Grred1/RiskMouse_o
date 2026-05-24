let chartInstances = {};
let allData = null;
let financialData = null;
let currentSymbol = '';
const CATEGORY_MAP = { '按行业分类': 'industry', '按产品分类': 'product', '按地区分类': 'region' };
const REVERSE_MAP = { 'industry': '按行业分类', 'product': '按产品分类', 'region': '按地区分类' };
let finChartInstances = {};
let growthChartsRendered = false;
const ZYGC_COLORS = ['#4f8fdc', '#34d399', '#a78bfa', '#fb923c', '#f472b6', '#fbbf24', '#60a5fa', '#4ade80'];

document.addEventListener('DOMContentLoaded', function() {
    const input = document.getElementById('symbolInput');
    if (input) {
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') search();
        });
    }
});

function quickSearch(symbol) {
    document.getElementById('symbolInput').value = symbol;
    search();
}

function showError(msg) {
    const el = document.getElementById('errorMsg');
    el.textContent = msg;
    el.style.display = 'block';
}

function hideError() {
    document.getElementById('errorMsg').style.display = 'none';
}

function adjustFinLayout() {
    document.querySelectorAll('.fin-chart-grid').forEach(grid => {
        const hasVisible = Array.from(grid.querySelectorAll('.fin-panel'))
            .some(p => p.style.display !== 'none');
        grid.style.display = hasVisible ? '' : 'none';
    });

    document.querySelectorAll('.sub-tab-content').forEach(content => {
        const hasVisible = Array.from(content.querySelectorAll('.fin-panel'))
            .some(p => p.style.display !== 'none');
        const key = content.id.replace('subtab-', '');
        const tabBtn = document.querySelector(`#finSectionHeader .sub-tab[data-tab="${key}"]`);
        if (tabBtn) tabBtn.style.display = hasVisible ? '' : 'none';
    });

    const anyVisibleTab = Array.from(document.querySelectorAll('#finSectionHeader .sub-tab'))
        .some(t => t.style.display !== 'none');
    if (!anyVisibleTab) {
        document.getElementById('finSectionHeader').style.display = 'none';
        document.getElementById('financialContent').style.display = 'none';
    }

    const anyVisibleNav = Array.from(document.querySelectorAll('.zygc-nav-item'))
        .some(n => n.style.display !== 'none');
    if (!anyVisibleNav) {
        document.getElementById('zygcLayout').style.display = 'none';
    }
}

async function clearCache() {
    if (!currentSymbol) return;
    if (!confirm(`确定清除 ${currentSymbol} 在所有模块的缓存数据？`)) return;
    try {
        const resp = await fetch('/api/financial/clear-cache', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: currentSymbol }),
        });
        const data = await resp.json();
        if (data.ok) {
            alert(`已清除 ${data.removed} 个缓存文件，点击查询将重新分析`);
            document.getElementById('aiSection').style.display = 'none';
            document.getElementById('clearCacheRow').style.display = 'none';
        } else {
            alert('清缓存失败');
        }
    } catch (e) {
        alert('清缓存失败: ' + e.message);
    }
}
