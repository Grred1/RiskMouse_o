let watchlistStocks = [];
let pendingCodes = [];
let assessmentResults = {};
const DIARY_KEY = 'riskDiary';

document.addEventListener('DOMContentLoaded', () => {
    initUploadZone();
    loadWatchlist();
    renderDiaryList('');
    const clockEl = document.getElementById('cyberClock');
    if (clockEl) {
        const tick = () => { clockEl.textContent = new Date().toLocaleString('zh-CN'); };
        tick();
        setInterval(tick, 1000);
    }
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

async function loadWatchlist() {
    try {
        const resp = await fetch('/api/watchlist/list', { headers: getAuthHeaders() });
        const data = await resp.json();
        watchlistStocks = data.stocks || [];
        renderWatchlistGrid();
        updateDiaryFilter();
        updateSparklines();
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
            headers: getAuthHeaders(),
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
        headers: getAuthHeaders(),
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
    const slots = [];
    for (let i = 0; i < 6; i++) {
        const s = watchlistStocks[i];
        if (!s) {
            slots.push(`<div class="saved-card saved-card-empty">
                <div class="saved-card-empty-inner">
                    <span class="saved-card-empty-icon">+</span>
                    <span class="saved-card-empty-hint">下方添加</span>
                </div>
            </div>`);
        } else {
            const spark = generateSparklineFallback(s.code);
            const assessed = !!assessmentResults[s.code];
            slots.push(`<div class="saved-card" data-code="${s.code}" onclick="openDetail('${s.code}')">
                <div class="saved-card-header">
                    <div>
                        <div class="saved-card-name">${s.name || s.code}</div>
                        <div class="saved-card-code">${s.code}</div>
                    </div>
                    <div style="display:flex;flex-direction:column;align-items:flex-end;gap:3px;">
                        <button class="saved-card-remove" onclick="event.stopPropagation();removeFromWatchlist('${s.code}')" title="移除">×</button>
                        <span class="saved-card-status-dot ${spark.statusClass}" data-code="${s.code}"></span>
                    </div>
                </div>
                <div class="saved-card-sparkline-wrap" data-code="${s.code}">${spark.svg}</div>
                <div class="saved-card-hint">${assessed ? '已测评 ✓' : '点击查看分析 →'}</div>
            </div>`);
        }
    }
    grid.innerHTML = slots.join('');
}

function buildSparklineSvg(prices, isUp) {
    const w = 100, h = 38, pts = prices.length;
    if (pts < 2) return generateSparklineFallback('').svg;
    const minV = Math.min(...prices), maxV = Math.max(...prices);
    const range = maxV - minV || 1;
    const pathPts = prices.map((v, i) =>
        `${(i / (pts - 1)) * w},${h - 2 - ((v - minV) / range) * (h - 6)}`
    ).join(' ');
    const color = isUp ? '#ef4444' : '#22c55e';
    return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" width="100%" height="100%" fill="none" xmlns="http://www.w3.org/2000/svg" class="saved-card-sparkline"><polyline points="${pathPts}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.85"/></svg>`;
}

async function updateSparklines() {
    for (const s of watchlistStocks) {
        try {
            const resp = await fetch(`/api/watchlist/sparkline/${s.code}`);
            const data = await resp.json();
            if (data.prices && data.prices.length >= 2) {
                const svg = buildSparklineSvg(data.prices, data.is_up);
                const wrap = document.querySelector(`.saved-card-sparkline-wrap[data-code="${s.code}"]`);
                const dot = document.querySelector(`.saved-card-status-dot[data-code="${s.code}"]`);
                if (wrap) wrap.innerHTML = svg;
                if (dot) {
                    dot.className = `saved-card-status-dot ${data.is_up ? 'saved-card-status-up' : 'saved-card-status-down'}`;
                }
            }
        } catch (e) { }
    }
}

function generateSparklineFallback(code) {
    let seed = 0;
    for (let i = 0; i < code.length; i++) seed = (seed * 31 + code.charCodeAt(i)) & 0x7fffffff;
    const rand = () => { seed = (seed * 1664525 + 1013904223) & 0x7fffffff; return seed / 0x7fffffff; };
    const pts = 16, w = 100, h = 38;
    const vals = [];
    let v = 50;
    for (let i = 0; i < pts; i++) { v += (rand() - 0.47) * 14; v = Math.max(8, Math.min(92, v)); vals.push(v); }
    const minV = Math.min(...vals), maxV = Math.max(...vals), range = maxV - minV || 1;
    const pathPts = vals.map((vv, i) =>
        `${(i / (pts - 1)) * w},${h - 2 - ((vv - minV) / range) * (h - 6)}`
    ).join(' ');
    const isUp = vals[vals.length - 1] > vals[0];
    const color = isUp ? '#ef4444' : '#22c55e';
    const statusClass = isUp ? 'saved-card-status-up' : 'saved-card-status-down';
    return {
        isUp,
        statusClass,
        svg: `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" width="100%" height="100%" fill="none" xmlns="http://www.w3.org/2000/svg" class="saved-card-sparkline"><polyline points="${pathPts}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.85"/></svg>`,
    };
}

async function openDetail(code) {
    document.querySelectorAll('.saved-card').forEach(c =>
        c.classList.toggle('selected', c.dataset.code === code)
    );
    renderDrawerLoading(code);

    try {
        const resp = await fetch(`/api/watchlist/detail/${code}`);
        if (!resp.ok) {
            const err = await resp.json();
            renderDrawerError(err.detail || '分析失败');
            return;
        }
        const data = await resp.json();
        assessmentResults[code] = data;
        renderDrawerContent(data);
        const hintEl = document.querySelector(`.saved-card[data-code="${code}"] .saved-card-hint`);
        if (hintEl) hintEl.textContent = '已测评 ✓';
    } catch (e) {
        renderDrawerError('请求失败：' + e.message);
    }
}

function closeDrawer() {
    document.getElementById('detailDrawer')?.classList.remove('open');
    document.getElementById('drawerOverlay')?.classList.remove('visible');
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
    const newsHtml = (d.news_json || []).slice(0, 6).map(n => `
        <a class="news-link-item" href="${n.url || '#'}" target="_blank" rel="noopener">
            <span class="news-date">${n.date || ''}</span>
            <span class="news-title">${n.title || ''}</span>
        </a>`).join('') || '<div class="news-empty">暂无新闻数据</div>';

    const wcHtml = d.wordcloud_b64
        ? `<img class="wordcloud-img" src="${d.wordcloud_b64}" alt="舆情词云">`
        : '<div class="news-empty">词云生成中或暂无数据</div>';

    document.getElementById('drawerBody').innerHTML = `
        <div class="drawer-stock-title">
            <span class="drawer-name">${d.name}</span>
            <span class="drawer-code">${d.code}</span>
        </div>

        <div class="drawer-section">
            <div class="drawer-section-title">四维评分</div>
            <div class="stars-grid">
                <div class="stars-item"><div class="stars-label">财报风险</div>${_starsHtml(d.fundamental_stars, 'stars-fund')}</div>
                <div class="stars-item"><div class="stars-label">舆论风险</div>${_starsHtml(d.news_stars, 'stars-news')}</div>
                <div class="stars-item"><div class="stars-label">市场风险</div>${_starsHtml(d.risk_stars, 'stars-risk')}</div>
                <div class="stars-item"><div class="stars-label">综合风险</div>${_starsHtml(d.overall_stars, 'stars-ovr')}</div>
            </div>
        </div>

        <div class="drawer-section">
            <div class="drawer-section-title">AI 综合解读</div>
            <div class="drawer-brief">${d.brief || '暂无解读'}</div>
        </div>

        <div class="drawer-news-wc-row">
            <div class="drawer-news-col">
                <div class="drawer-section-title">近期新闻 <span style="font-size:10px;color:#90a4ae;">点击查看原文</span></div>
                <div class="news-list">${newsHtml}</div>
            </div>
            <div class="drawer-wc-col">
                <div class="drawer-section-title">舆情词云</div>
                ${wcHtml}
            </div>
        </div>
    `;
}

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

    if (typeof Tesseract === 'undefined') {
        hint.textContent = '⚠️ OCR 引擎加载失败，请刷新页面重试';
        return;
    }

    hint.textContent = '🔍 识别中，首次使用需下载引擎（约几秒）...';
    try {
        const dataUrl = `data:${mimeType};base64,${base64}`;
        const { data: { text } } = await Tesseract.recognize(dataUrl, 'eng');

        const allMatches = [...text.matchAll(/\d{6}/g)].map(m => m[0]);
        const codes = [...new Set(allMatches.filter(c => ['0','3','4','6','8'].includes(c[0])))];

        if (codes.length === 0) {
            hint.textContent = '未识别到股票代码，请手动添加';
            return;
        }
        hint.textContent = `✅ 识别到 ${codes.length} 只股票`;
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

function normalizeCode(code) {
    code = String(code).trim().replace(/^[SsHhZzBbJj]{2}/, '');
    return /^\d{6}$/.test(code) ? code : '';
}

function showWatchlistError(msg) {
    const el = document.getElementById('watchlistError');
    if (el) el.textContent = msg;
}
