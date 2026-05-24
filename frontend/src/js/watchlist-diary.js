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
    ['dStockSymbol','dStockName','dRiskScore','dSystemSuggestion','dUserNote'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });
    document.getElementById('dStockCode').textContent = '';
    document.querySelectorAll('input[name="dTagRadio"]').forEach(r => r.checked = false);
}

function toggleDiaryForm() {}
function toggleBasis() {}
