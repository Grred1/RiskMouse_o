// ── 状态 ────────────────────────────────────────────────────
let watchlistStocks = [];   // 持久化列表（来自服务端）
let pendingCodes = [];       // 待添加临时列表
let assessmentResults = {};  // { code: detailApiResponse }，内存，刷新后清空
const DIARY_KEY = 'riskDiary';

// ── 初始化 ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initUploadZone();
    loadWatchlist();
    renderDiaryList('');
});

function initUploadZone() {
    const zone = document.getElementById('uploadZone');
    if (!zone) return;
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', e => {
        e.preventDefault(); zone.classList.remove('drag-over');
        const file = e.dataTransfer.files[0];
        if (file && file.type.startsWith('image/')) handleImageFile(file);
    });
    zone.addEventListener('click', () => document.getElementById('imageInput').click());
    document.getElementById('imageInput').addEventListener('change', e => {
        if (e.target.files[0]) handleImageFile(e.target.files[0]);
        e.target.value = '';
    });
}

// ── 持久化自选股 ─────────────────────────────────────────────
async function loadWatchlist() {
    try {
        const resp = await fetch('/api/watchlist/list');
        const data = await resp.json();
        watchlistStocks = data.stocks || [];
        renderWatchlistGrid();
        updateDiaryFilter();
    } catch (e) {
        console.error('loadWatchlist', e);
    }
}

async function addToWatchlist(code) {
    code = normalizeCode(code);
    if (!code) return;
    try {
        const resp = await fetch('/api/watchlist/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code }),
        });
        const data = await resp.json();
        if (!resp.ok) { showWatchlistError(data.detail || '添加失败'); return; }
        await loadWatchlist();
        clearPendingCode(code);
        showWatchlistError('');
    } catch (e) {
        showWatchlistError('添加失败：' + e.message);
    }
}

async function removeFromWatchlist(code) {
    await fetch('/api/watchlist/remove', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
    });
    delete assessmentResults[code];
    cleanDiaryForStock(code);
    renderRatingList();
    renderStickyNotes();
    await loadWatchlist();
}

function renderWatchlistGrid() {
    const grid = document.getElementById('savedGrid');
    if (!grid) return;
    if (watchlistStocks.length === 0) {
        grid.innerHTML = '<div class="saved-empty">暂无自选股，请在下方添加</div>';
        return;
    }
    grid.innerHTML = watchlistStocks.map(s => `
        <div class="saved-card" onclick="openDetail('${s.code}')">
            <div class="saved-card-header">
                <div>
                    <div class="saved-card-name">${s.name || s.code}</div>
                    <div class="saved-card-code">${s.code}</div>
                </div>
                <button class="saved-card-remove" onclick="event.stopPropagation();removeFromWatchlist('${s.code}')" title="移除">×</button>
            </div>
            <div class="saved-card-hint">点击查看风险分析 →</div>
        </div>
    `).join('');
}

// ── 详情抽屉 ─────────────────────────────────────────────────
async function openDetail(code) {
    const drawer = document.getElementById('detailDrawer');
    const overlay = document.getElementById('drawerOverlay');
    drawer.classList.add('open');
    overlay.classList.add('visible');
    renderDrawerLoading(code);

    try {
        const resp = await fetch(`/api/watchlist/detail/${code}`);
        if (!resp.ok) {
            const err = await resp.json();
            renderDrawerError(err.detail || '分析失败');
            return;
        }
        const data = await resp.json();
        renderDrawerContent(data);
    } catch (e) {
        renderDrawerError('请求失败：' + e.message);
    }
}

function closeDrawer() {
    document.getElementById('detailDrawer').classList.remove('open');
    document.getElementById('drawerOverlay').classList.remove('visible');
}

function renderDrawerLoading(code) {
    document.getElementById('drawerBody').innerHTML = `
        <div class="drawer-loading">
            <div class="spinner"></div>
            <div>${code} 分析中，正在获取财务数据与新闻...</div>
        </div>`;
}

function renderDrawerError(msg) {
    document.getElementById('drawerBody').innerHTML =
        `<div class="drawer-error">${msg}</div>`;
}

function renderDrawerContent(d) {
    const starsHtml = (n, type) => {
        n = Math.max(1, Math.min(5, n || 3));
        return Array.from({length: 5}, (_, i) =>
            `<span class="${i < n ? 'star-filled' : 'star-empty'}"${type === 'risk' && i < n ? ' style="color:#e53935"' : ''}>★</span>`
        ).join('');
    };

    const basisHtml = (label, stars, basis) => `
        <div class="basis-row">
            <div class="basis-label">${label}</div>
            <div class="basis-stars">${starsHtml(stars, label.includes('风险') ? 'risk' : 'normal')}</div>
            <div class="basis-text">${basis || '-'}</div>
        </div>`;

    const newsHtml = (d.news_json || []).slice(0, 6).map(n => `
        <a class="news-link-item" href="${n.url || '#'}" target="_blank" rel="noopener">
            <span class="news-date">${n.date || ''}</span>
            <span class="news-title">${n.title || ''}</span>
        </a>`).join('') || '<div class="news-empty">暂无新闻数据</div>';

    const wcHtml = d.wordcloud_b64
        ? `<img class="wordcloud-img" src="${d.wordcloud_b64}" alt="舆情词云">`
        : '<div class="news-empty">词云生成中或暂无数据</div>';

    const basis = d.score_basis || {};

    document.getElementById('drawerBody').innerHTML = `
        <div class="drawer-stock-title">
            <span class="drawer-name">${d.name}</span>
            <span class="drawer-code">${d.code}</span>
        </div>

        <div class="drawer-section">
            <div class="drawer-section-title">四维评分</div>
            <div class="stars-grid">
                <div class="stars-item"><div class="stars-label">基本面</div><div class="stars-row">${starsHtml(d.fundamental_stars, 'normal')}</div></div>
                <div class="stars-item"><div class="stars-label">新闻情绪</div><div class="stars-row">${starsHtml(d.news_stars, 'normal')}</div></div>
                <div class="stars-item"><div class="stars-label">风险等级 ⚠️</div><div class="stars-row stars-risk">${starsHtml(d.risk_stars, 'risk')}</div></div>
                <div class="stars-item"><div class="stars-label">综合评分</div><div class="stars-row">${starsHtml(d.overall_stars, 'normal')}</div></div>
            </div>
        </div>

        <div class="drawer-section">
            <div class="drawer-section-title">打分依据 <span class="basis-toggle" onclick="toggleBasis(this)">展开 ▾</span></div>
            <div class="score-basis" style="display:none">
                ${basisHtml('基本面', d.fundamental_stars, basis.fundamental)}
                ${basisHtml('新闻情绪', d.news_stars, basis.news)}
                ${basisHtml('风险等级⚠️', d.risk_stars, basis.risk)}
                ${basisHtml('综合评分', d.overall_stars, basis.overall)}
            </div>
        </div>

        <div class="drawer-section">
            <div class="drawer-section-title">AI 综合解读</div>
            <div class="drawer-brief">${d.brief || '暂无解读'}</div>
        </div>

        <div class="drawer-section">
            <div class="drawer-section-title">近期新闻 <span style="font-size:12px;color:#90a4ae;">点击可查看原文</span></div>
            <div class="news-list">${newsHtml}</div>
        </div>

        <div class="drawer-section">
            <div class="drawer-section-title">舆情词云</div>
            ${wcHtml}
        </div>
    `;
}

function toggleBasis(btn) {
    const el = btn.closest('.drawer-section').querySelector('.score-basis');
    const hidden = el.style.display === 'none';
    el.style.display = hidden ? 'block' : 'none';
    btn.textContent = hidden ? '收起 ▴' : '展开 ▾';
}

// ── 截图 OCR ─────────────────────────────────────────────────
function handleImageFile(file) {
    const reader = new FileReader();
    reader.onload = async e => {
        const dataUrl = e.target.result;
        const preview = document.getElementById('uploadPreview');
        preview.src = dataUrl; preview.style.display = 'block';
        await parseImageCodes(dataUrl.split(',')[1], file.type);
    };
    reader.readAsDataURL(file);
}

async function parseImageCodes(base64, mimeType) {
    const hint = document.getElementById('parsingHint');
    setOcrAddBtn([], false);
    hint.textContent = '识别中...';
    try {
        const resp = await fetch('/api/watchlist/parse-image', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: base64, mime_type: mimeType }),
        });
        const data = await resp.json();
        if (data.ocr_available === false) {
            hint.textContent = '⚠️ 未配置识别服务，请手动输入（可设置 DASHSCOPE_API_KEY 启用 Qwen-VL）';
            return;
        }
        const codes = data.codes || [];
        const engine = data.method === 'qwen-vl' ? 'Qwen-VL' : 'OCR';
        if (codes.length === 0) { hint.textContent = `${engine} 未识别到股票代码，请手动添加`; return; }
        hint.textContent = `${engine} 识别到 ${codes.length} 只股票代码`;
        codes.forEach(c => addToPending(c));
        setOcrAddBtn(codes, true);
    } catch (e) {
        hint.textContent = '识别失败：' + e.message;
    }
}

function setOcrAddBtn(codes, show) {
    const btn = document.getElementById('ocrAddBtn');
    if (!btn) return;
    if (!show || codes.length === 0) { btn.style.display = 'none'; return; }
    btn.textContent = `添加全部到自选（${codes.length} 只）`;
    btn.style.display = 'inline-block';
    btn.onclick = async () => {
        btn.disabled = true;
        btn.textContent = '添加中...';
        for (const c of codes) await addToWatchlist(c);
        btn.style.display = 'none';
        document.getElementById('parsingHint').textContent = '已添加到自选股 ✓';
    };
}

// ── 待添加临时列表 ───────────────────────────────────────────
function addToPending(code) {
    code = normalizeCode(code);
    if (!code || pendingCodes.includes(code)) return;
    pendingCodes.push(code);
    renderPendingTags();
}

function clearPendingCode(code) {
    pendingCodes = pendingCodes.filter(c => c !== code);
    renderPendingTags();
}

function renderPendingTags() {
    const container = document.getElementById('stockTags');
    if (!container) return;
    if (pendingCodes.length === 0) {
        container.innerHTML = '<span class="stock-tags-empty">暂无待添加股票</span>';
        return;
    }
    container.innerHTML = pendingCodes.map(code => `
        <span class="stock-tag">
            ${code}
            <span class="tag-action" onclick="addToWatchlist('${code}')" title="加入自选">+</span>
            <span class="tag-remove" onclick="clearPendingCode('${code}')" title="移除">×</span>
        </span>`).join('');
}

function handleManualInput(e) {
    if (e && e.key && e.key !== 'Enter') return;
    const input = document.getElementById('manualInput');
    const val = input.value.trim();
    if (!val) return;
    val.split(/[,，\s]+/).forEach(c => addToPending(c.trim()));
    input.value = '';
}

// ── 工具函数 ─────────────────────────────────────────────────
function normalizeCode(code) {
    code = String(code).trim().replace(/^[SsHhZzBbJj]{2}/, '');
    return /^\d{6}$/.test(code) ? code : '';
}

function showWatchlistError(msg) {
    const el = document.getElementById('watchlistError');
    if (el) el.textContent = msg;
}

// ── 一键测评 ─────────────────────────────────────────────────
async function assessAll() {
    if (watchlistStocks.length === 0) {
        document.getElementById('assessStatus').textContent = '请先添加自选股';
        return;
    }
    const btn = document.querySelector('.assess-btn');
    const status = document.getElementById('assessStatus');
    btn.disabled = true;
    const total = watchlistStocks.length;
    let done = 0;
    for (const s of watchlistStocks) {
        status.textContent = `测评中 ${done + 1}/${total}：${s.name || s.code}...`;
        try {
            const resp = await fetch(`/api/watchlist/detail/${s.code}`);
            if (resp.ok) {
                const data = await resp.json();
                assessmentResults[s.code] = data;
            }
        } catch (e) {
            console.warn('assessAll error', s.code, e);
        }
        done++;
    }
    status.textContent = `测评完成，共 ${Object.keys(assessmentResults).length} 只`;
    btn.disabled = false;
    renderRatingList();
    renderStickyNotes();
}

function _starsHtml(n, isRisk) {
    n = Math.max(1, Math.min(5, n || 3));
    return Array.from({length: 5}, (_, i) => {
        const color = isRisk && i < n ? 'color:#e53935' : '';
        return `<span style="font-size:13px;${color}">${i < n ? '★' : '☆'}</span>`;
    }).join('');
}

function renderRatingList() {
    const section = document.getElementById('ratingListSection');
    const container = document.getElementById('ratingListContainer');
    const entries = Object.values(assessmentResults);
    if (entries.length === 0) { section.style.display = 'none'; return; }
    section.style.display = '';
    const sorted = [...entries].sort((a, b) => (b.overall_stars || 0) - (a.overall_stars || 0));
    container.innerHTML = `
        <table class="rating-table">
            <thead><tr>
                <th class="rating-rank">#</th>
                <th>代码</th><th>名称</th>
                <th>基本面</th><th>新闻</th><th>风险⚠️</th><th>综合</th>
            </tr></thead>
            <tbody>${sorted.map((d, i) => `
                <tr onclick="openDetail('${d.code}')">
                    <td class="rating-rank">${i + 1}</td>
                    <td>${d.code}</td>
                    <td>${d.name || d.code}</td>
                    <td>${_starsHtml(d.fundamental_stars, false)}</td>
                    <td>${_starsHtml(d.news_stars, false)}</td>
                    <td>${_starsHtml(d.risk_stars, true)}</td>
                    <td>${_starsHtml(d.overall_stars, false)}</td>
                </tr>`).join('')}
            </tbody>
        </table>`;
}

function renderStickyNotes() {
    const section = document.getElementById('stickyNotesSection');
    const container = document.getElementById('stickyNotesContainer');
    const entries = Object.values(assessmentResults);
    if (entries.length === 0) { section.style.display = 'none'; return; }
    section.style.display = '';
    container.innerHTML = entries.map(d => `
        <div class="sticky-note">
            <div class="sticky-note-name">${d.name || d.code}</div>
            <div class="sticky-note-code">${d.code}</div>
            <div class="sticky-note-brief">${d.brief || '暂无 AI 解读'}</div>
            <div class="sticky-note-footer">
                <div>${_starsHtml(d.overall_stars, false)}</div>
                <button class="sticky-note-btn"
                    onclick="prefillDiary('${d.code}','${(d.name||d.code).replace(/'/g,'')}')">
                    记录日记
                </button>
            </div>
        </div>`).join('');
}

// ── 风险日记 ─────────────────────────────────────────────────
function loadDiary() {
    try { return JSON.parse(localStorage.getItem(DIARY_KEY) || '[]'); } catch { return []; }
}
function saveDiary(entries) {
    localStorage.setItem(DIARY_KEY, JSON.stringify(entries));
}

function addDiaryEntry(entry) {
    const entries = loadDiary();
    entries.unshift(entry);
    saveDiary(entries);
    renderDiaryList(document.getElementById('diaryFilterSelect')?.value || '');
}

function deleteDiaryEntry(id) {
    saveDiary(loadDiary().filter(e => e.id !== id));
    renderDiaryList(document.getElementById('diaryFilterSelect')?.value || '');
}

function cleanDiaryForStock(code) {
    saveDiary(loadDiary().filter(e => e.stockSymbol !== code));
    renderDiaryList(document.getElementById('diaryFilterSelect')?.value || '');
}

function renderDiaryList(filterCode) {
    const container = document.getElementById('diaryListContainer');
    if (!container) return;
    let entries = loadDiary();
    if (filterCode) entries = entries.filter(e => e.stockSymbol === filterCode);
    if (entries.length === 0) {
        container.innerHTML = '<div class="diary-empty">暂无日记记录</div>';
        return;
    }
    container.innerHTML = entries.map(e => `
        <div class="diary-card">
            <div class="diary-card-header">
                <div class="diary-card-meta">
                    <span class="diary-card-stock">${e.stockName || e.stockSymbol} (${e.stockSymbol})</span>
                    <span class="diary-risk-badge diary-risk-${e.riskLevel}">${e.riskLevel}风险</span>
                    ${e.riskScore ? `<span style="font-size:12px;color:#90a4ae;">${_starsHtml(e.riskScore, false)}</span>` : ''}
                </div>
                <div style="display:flex;align-items:center;gap:8px;">
                    <span class="diary-card-date">${e.date || ''}</span>
                    <button class="diary-delete-btn" onclick="deleteDiaryEntry(${e.id})" title="删除">×</button>
                </div>
            </div>
            <div class="diary-card-body">
                ${e.systemSuggestion ? `<div class="diary-card-suggestion">系统建议：${e.systemSuggestion}</div>` : ''}
                ${e.userNote ? `<div class="diary-card-note">我的备注：${e.userNote}</div>` : ''}
                ${e.tag ? `<div class="diary-card-tag"># ${e.tag}</div>` : ''}
            </div>
        </div>`).join('');
}

function updateDiaryFilter() {
    const sel = document.getElementById('diaryFilterSelect');
    if (!sel) return;
    const current = sel.value;
    sel.innerHTML = '<option value="">全部</option>' +
        watchlistStocks.map(s =>
            `<option value="${s.code}"${s.code === current ? ' selected' : ''}>${s.name || s.code} (${s.code})</option>`
        ).join('');
}

function toggleDiaryForm() {
    const form = document.getElementById('diaryForm');
    if (!form) return;
    const hidden = form.style.display === 'none';
    form.style.display = hidden ? 'block' : 'none';
    if (hidden) {
        const dateEl = document.getElementById('dDate');
        if (dateEl && !dateEl.value) {
            dateEl.value = new Date().toISOString().slice(0, 10);
        }
    }
}

function prefillDiary(code, name) {
    const section = document.getElementById('riskDiarySection');
    if (section) section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    const form = document.getElementById('diaryForm');
    if (form) form.style.display = 'block';
    document.getElementById('dStockSymbol').value = code;
    document.getElementById('dStockName').value = name;
    document.getElementById('dStockCode').textContent = code;
    document.getElementById('dDate').value = new Date().toISOString().slice(0, 10);
    const res = assessmentResults[code];
    if (res) {
        const score = res.overall_stars || '';
        document.getElementById('dRiskScore').value = score;
        const level = score >= 4 ? '低' : score <= 2 ? '高' : '中';
        document.getElementById('dRiskLevel').value = level;
        document.getElementById('dSystemSuggestion').value = res.brief || '';
    }
}

function handleDiarySubmit() {
    const symbol = document.getElementById('dStockSymbol').value.trim();
    const name = document.getElementById('dStockName').value.trim();
    if (!symbol) { alert('请先选择股票（从便利贴点击「记录日记」或手动填写）'); return; }
    const entry = {
        id: Date.now(),
        stockSymbol: symbol,
        stockName: name || symbol,
        date: document.getElementById('dDate').value,
        riskLevel: document.getElementById('dRiskLevel').value,
        riskScore: parseInt(document.getElementById('dRiskScore').value) || null,
        systemSuggestion: document.getElementById('dSystemSuggestion').value.trim(),
        userNote: document.getElementById('dUserNote').value.trim(),
        tag: document.getElementById('dTag').value.trim(),
    };
    addDiaryEntry(entry);
    // 重置表单但保留日期
    document.getElementById('dStockSymbol').value = '';
    document.getElementById('dStockName').value = '';
    document.getElementById('dStockCode').textContent = '';
    document.getElementById('dRiskScore').value = '';
    document.getElementById('dSystemSuggestion').value = '';
    document.getElementById('dUserNote').value = '';
    document.getElementById('dTag').value = '';
    document.getElementById('diaryForm').style.display = 'none';
}
