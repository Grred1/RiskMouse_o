// ── 状态 ────────────────────────────────────────────────────
let watchlistStocks = [];   // 持久化列表（来自服务端）
let pendingCodes = [];       // 待添加临时列表
let assessmentResults = {};  // { code: detailApiResponse }，内存，刷新后清空
const DIARY_KEY = 'riskDiary';
let carouselIndex = 0;

// ── 初始化 ───────────────────────────────────────────────────
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

// ── 持久化自选股 ─────────────────────────────────────────────
async function loadWatchlist() {
    try {
        const resp = await fetch('/api/watchlist/list');
        const data = await resp.json();
        watchlistStocks = data.stocks || [];
        renderWatchlistGrid();
        updateDiaryFilter();
        // 异步更新真实走势图
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

// ── 渲染自选股格子（固定6槽位） ─────────────────────────────
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
                    <span class="saved-card-empty-hint">添加自选</span>
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

// ── 真实走势图（异步更新） ──────────────────────────────────
function buildSparklineSvg(prices, isUp) {
    const w = 100, h = 38, pts = prices.length;
    if (pts < 2) return generateSparklineFallback('').svg;
    const minV = Math.min(...prices), maxV = Math.max(...prices);
    const range = maxV - minV || 1;
    const pathPts = prices.map((v, i) =>
        `${(i / (pts - 1)) * w},${h - 2 - ((v - minV) / range) * (h - 6)}`
    ).join(' ');
    // 中国惯例：红涨绿跌
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
                    // 红涨绿跌
                    dot.className = `saved-card-status-dot ${data.is_up ? 'saved-card-status-up' : 'saved-card-status-down'}`;
                }
            }
        } catch (e) { /* 保留 fallback */ }
    }
}

// ── 伪随机走势（fallback，中国惯例红涨绿跌） ──────────────
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
    // 中国惯例：红涨绿跌
    const color = isUp ? '#ef4444' : '#22c55e';
    const statusClass = isUp ? 'saved-card-status-up' : 'saved-card-status-down';
    return {
        isUp,
        statusClass,
        svg: `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" width="100%" height="100%" fill="none" xmlns="http://www.w3.org/2000/svg" class="saved-card-sparkline"><polyline points="${pathPts}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.85"/></svg>`,
    };
}

// ── 详情面板（内嵌右侧列） ────────────────────────────────────
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
        // 更新该卡片的"已测评"提示
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

    // 布局：上面四维评分 → 中间AI解读 → 下面左新闻右词云
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
    renderWatchlistGrid();
    renderRatingList();
    renderStickyNotes();
}

// ── 星星渲染 ─────────────────────────────────────────────────
function _starsHtml(n, cls) {
    n = Math.max(1, Math.min(5, n || 3));
    const stars = Array.from({length: 5}, (_, i) =>
        `<span class="${i < n ? 'star-on' : 'star-off'}">★</span>`
    ).join('');
    return `<span class="stars-row ${cls || ''}">${stars}</span>`;
}

// 渐变星（多星=绿=低风险，少星=红=高风险）
function _riskStarsHtml(n) {
    n = Math.max(1, Math.min(5, n || 3));
    const colors = {1: '#ef4444', 2: '#f97316', 3: '#f59e0b', 4: '#4ade80', 5: '#22c55e'};
    const color = colors[n];
    const stars = Array.from({length: 5}, (_, i) =>
        `<span style="color:${i < n ? color : 'rgba(148,163,184,0.30)'}">★</span>`
    ).join('');
    return `<span class="stars-row" title="${n}星·${n >= 4 ? '低风险' : n <= 2 ? '高风险' : '中风险'}">${stars}</span>`;
}

// ── 风险评级排行榜 ────────────────────────────────────────────
function renderRatingList() {
    const container = document.getElementById('ratingListContainer');
    const entries = Object.values(assessmentResults);
    if (entries.length === 0) {
        container.innerHTML = '<div class="rating-empty">点击「一键测评」生成排行榜</div>';
        return;
    }
    const sorted = [...entries].sort((a, b) => (b.overall_stars || 0) - (a.overall_stars || 0));
    container.innerHTML = `
        <div class="rating-legend">⭐多星=低风险(绿) &nbsp; ⭐少星=高风险(红)</div>
        <table class="rating-table">
            <thead><tr>
                <th class="rating-rank">#</th>
                <th>代码</th><th>名称</th>
                <th>财报风险</th><th>舆论风险</th><th>市场风险</th><th>综合风险</th>
            </tr></thead>
            <tbody>${sorted.map((d, i) => {
                const medalCls = i < 3 ? ` rank-medal-${i + 1}` : '';
                return `
                <tr onclick="openDetail('${d.code}')" style="cursor:pointer;">
                    <td class="rating-rank"><span class="rank-medal${medalCls}">${i + 1}</span></td>
                    <td>${d.code}</td>
                    <td>${d.name || d.code}</td>
                    <td>${_riskStarsHtml(d.fundamental_stars)}</td>
                    <td>${_riskStarsHtml(d.news_stars)}</td>
                    <td>${_riskStarsHtml(d.risk_stars)}</td>
                    <td>${_riskStarsHtml(d.overall_stars)}</td>
                </tr>`;
            }).join('')}
            </tbody>
        </table>`;
}

// ── 风险便利贴 ────────────────────────────────────────────────
function renderStickyNotes() {
    const container = document.getElementById('stickyNotesContainer');
    const entries = Object.values(assessmentResults);
    if (entries.length === 0) {
        container.innerHTML = '<div class="sticky-note-empty">测评后将生成风险便利贴</div>';
        const dots = document.getElementById('carouselDots');
        if (dots) dots.innerHTML = '';
        return;
    }
    carouselIndex = 0;
    container.style.transition = 'none';
    container.style.transform = 'translateX(0)';
    container.innerHTML = entries.map(d => `
        <div class="sticky-note">
            <div class="sticky-note-name">${d.name || d.code}</div>
            <div class="sticky-note-code">${d.code}</div>
            <div class="sticky-note-brief">${d.brief || '暂无 AI 解读'}</div>
            <div class="sticky-note-footer">
                <span class="sticky-note-stars">${_riskStarsHtml(d.overall_stars)}</span>
                <button class="sticky-note-btn"
                    onclick="prefillDiary('${d.code}','${(d.name||d.code).replace(/'/g,'')}')">
                    记录日记
                </button>
            </div>
        </div>`).join('');
    initCarousel(entries.length);
}

// ── 便利贴轮播 ───────────────────────────────────────────────
const STICKY_NOTE_W = 214;

function initCarousel(count) {
    const dots = document.getElementById('carouselDots');
    if (!dots) return;
    dots.innerHTML = Array.from({length: count}, (_, i) =>
        `<span class="carousel-dot${i === 0 ? ' active' : ''}" onclick="goToSlide(${i})"></span>`
    ).join('');
    updateCarouselDisplay();
}

function updateCarouselDisplay() {
    const track = document.getElementById('stickyNotesContainer');
    if (track) {
        track.style.transition = 'transform 0.35s cubic-bezier(0.4,0,0.2,1)';
        track.style.transform = `translateX(-${carouselIndex * STICKY_NOTE_W}px)`;
    }
    document.querySelectorAll('#carouselDots .carousel-dot').forEach((d, i) =>
        d.classList.toggle('active', i === carouselIndex)
    );
    document.querySelectorAll('#stickyNotesContainer .sticky-note').forEach((n, i) =>
        n.classList.toggle('carousel-active', i === carouselIndex)
    );
}

function scrollCarousel(dir) {
    const total = document.querySelectorAll('#stickyNotesContainer .sticky-note').length;
    if (total === 0) return;
    carouselIndex = (carouselIndex + dir + total) % total;
    updateCarouselDisplay();
}

function goToSlide(index) {
    carouselIndex = index;
    updateCarouselDisplay();
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
    const tagColorMap = { '风险': 'diary-tag-risk', '关注': 'diary-tag-watch', '机会': 'diary-tag-chance' };
    container.innerHTML = entries.map(e => {
        const tagCls = tagColorMap[e.tag] || 'diary-card-tag-item';
        return `
        <div class="diary-card">
            <div class="diary-card-header">
                <div class="diary-card-meta">
                    <span class="diary-card-stock">${e.stockName || e.stockSymbol}</span>
                    <span class="diary-risk-badge diary-risk-${e.riskLevel}">${e.riskLevel}险</span>
                    ${e.tag ? `<span class="diary-card-tag-item ${tagCls}">${e.tag}</span>` : ''}
                </div>
                <div style="display:flex;align-items:center;gap:6px;">
                    <span class="diary-card-date">${e.date || ''}</span>
                    <button class="diary-delete-btn" onclick="deleteDiaryEntry(${e.id})" title="删除">×</button>
                </div>
            </div>
            <div class="diary-card-body">
                ${e.userNote ? `<div class="diary-card-note">${e.userNote}</div>` : ''}
                ${e.systemSuggestion ? `<div class="diary-card-suggestion">${e.systemSuggestion}</div>` : ''}
            </div>
        </div>`;
    }).join('');
}

function updateDiaryFilter() {
    const sel = document.getElementById('diaryFilterSelect');
    if (!sel) return;
    const current = sel.value;
    sel.innerHTML = '<option value="">全部类型</option>' +
        watchlistStocks.map(s =>
            `<option value="${s.code}"${s.code === current ? ' selected' : ''}>${s.name || s.code}</option>`
        ).join('');
}

// 日记表单始终可见，prefillDiary 只需填充数据
function prefillDiary(code, name) {
    const section = document.getElementById('riskDiarySection');
    if (section) section.scrollIntoView({ behavior: 'smooth', block: 'start' });
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
    // 短暂高亮表单
    const form = document.getElementById('diaryFormInner');
    if (form) {
        form.classList.add('diary-form-highlight');
        setTimeout(() => form.classList.remove('diary-form-highlight'), 800);
    }
}

function handleDiarySubmit() {
    const symbol = document.getElementById('dStockSymbol').value.trim();
    const name = document.getElementById('dStockName').value.trim();
    if (!symbol) { alert('请先选择股票（从便利贴点击「记录日记」）'); return; }
    // 读取标签单选
    const tagRadio = document.querySelector('input[name="dTagRadio"]:checked');
    const entry = {
        id: Date.now(),
        stockSymbol: symbol,
        stockName: name || symbol,
        date: document.getElementById('dDate').value,
        riskLevel: document.getElementById('dRiskLevel').value,
        riskScore: parseInt(document.getElementById('dRiskScore').value) || null,
        systemSuggestion: document.getElementById('dSystemSuggestion').value.trim(),
        userNote: document.getElementById('dUserNote').value.trim(),
        tag: tagRadio ? tagRadio.value : '',
    };
    addDiaryEntry(entry);
    // 重置表单
    ['dStockSymbol','dStockName','dRiskScore','dSystemSuggestion','dUserNote'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    document.getElementById('dStockCode').textContent = '';
    document.querySelectorAll('input[name="dTagRadio"]').forEach(r => r.checked = false);
}

// 保留向后兼容（按钮可能已移除但保留函数）
function toggleDiaryForm() {}
function toggleBasis() {}
