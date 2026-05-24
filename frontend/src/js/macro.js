// ══════════════════════════════════════════════════════════════════════════════
// 宏观风险时间轴
// ══════════════════════════════════════════════════════════════════════════════

const MONTH_NAMES = ['一月','二月','三月','四月','五月','六月','七月','八月','九月','十月','十一月','十二月'];
const WEEKDAYS = ['日','一','二','三','四','五','六'];

let macroData = null;
let selectedView = 'timeline';
let filterRisk = 'all';
let filterTime = 'all';
let selectedEvent = null;
let calendarMonth = new Date().getMonth();
let calendarYear = new Date().getFullYear();

function fmtDate(d) {
    if (!d) return '';
    const parts = d.split('-');
    if (parts.length === 3) return `${parseInt(parts[1])}月${parseInt(parts[2])}日`;
    return d;
}

function riskLabel(level) {
    if (level === '高') return '<span class="rc-badge rc-high">高风险</span>';
    if (level === '中') return '<span class="rc-badge rc-mid">中风险</span>';
    return '<span class="rc-badge rc-low">低风险</span>';
}

function riskDot(level) {
    if (level === '高') return '●';
    if (level === '中') return '●';
    return '●';
}

// ══════════════════════════════════════════════════════════════════════════════
// 数据获取
// ══════════════════════════════════════════════════════════════════════════════

async function fetchMacroRiskTimeline(refresh = false) {
    const container = document.getElementById('macroCalendarContent');
    if (!container) return;
    container.innerHTML = '<div class="macro-loading"><div class="spinner"></div>正在加载宏观风险数据...</div>';
    try {
        const url = `/api/macro/risk-timeline?refresh=${refresh}&days=30`;
        const r = await fetch(url);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        if (data.error) throw new Error(data.error);
        macroData = data;
        if (data.cache_status === 'no_cache') {
            container.innerHTML = `<div class="macro-error">暂无数据，请点击刷新获取最新宏观风险数据</div>`;
            return;
        }
        renderMacroView();
    } catch (e) {
        container.innerHTML = `<div class="macro-error">数据加载失败: ${e.message}</div>`;
    }
}

// ══════════════════════════════════════════════════════════════════════════════
// 主渲染
// ══════════════════════════════════════════════════════════════════════════════

function renderMacroView() {
    const container = document.getElementById('macroCalendarContent');
    if (!container || !macroData) return;
    const tl = macroData.timeline;
    const stats = macroData.stats;

    const allEvents = [...(tl.past?.events || []), ...(tl.current?.events || []), ...(tl.future?.events || [])];
    const pastCount = tl.past?.stats?.total || 0;
    const currentCount = tl.current?.stats?.total || 0;
    const futureCount = tl.future?.stats?.total || 0;

    let filteredEvents = allEvents;
    if (filterRisk !== 'all') filteredEvents = filteredEvents.filter(e => e.risk_level === filterRisk);
    if (filterTime === 'past') filteredEvents = tl.past?.events || [];
    else if (filterTime === 'current') filteredEvents = tl.current?.events || [];
    else if (filterTime === 'future') filteredEvents = tl.future?.events || [];

    const html = `
        <div class="macro-timeline-wrap">
            <div class="tl-stats-bar">
                <div class="tl-stat-card tl-past" onclick="switchFilter('time','past')">
                    <div class="tl-stat-icon">📋</div>
                    <div>
                        <div class="tl-stat-label">已结束事件</div>
                        <div class="tl-stat-num">${pastCount}</div>
                        <div class="tl-stat-detail"><span>高 ${tl.past?.stats?.high||0}</span><span>中 ${tl.past?.stats?.medium||0}</span><span>低 ${tl.past?.stats?.low||0}</span></div>
                    </div>
                </div>
                <div class="tl-stat-card tl-current" onclick="switchFilter('time','current')">
                    <div class="tl-stat-icon">🔥</div>
                    <div>
                        <div class="tl-stat-label">进行中事件</div>
                        <div class="tl-stat-num">${currentCount}</div>
                        <div class="tl-stat-detail"><span>高 ${tl.current?.stats?.high||0}</span><span>中 ${tl.current?.stats?.medium||0}</span><span>低 ${tl.current?.stats?.low||0}</span></div>
                    </div>
                </div>
                <div class="tl-stat-card tl-future" onclick="switchFilter('time','future')">
                    <div class="tl-stat-icon">🔮</div>
                    <div>
                        <div class="tl-stat-label">预期事件</div>
                        <div class="tl-stat-num">${futureCount}</div>
                        <div class="tl-stat-detail"><span>高 ${tl.future?.stats?.high||0}</span><span>中 ${tl.future?.stats?.medium||0}</span><span>低 ${tl.future?.stats?.low||0}</span></div>
                    </div>
                </div>
                <div class="tl-meta">
                    <span>📊 共 ${stats?.total||0} 条宏观风险事件</span>
                    <span class="rc-time">更新: ${macroData.fetched_at || '-'}</span>
                    <button class="rc-btn-refresh" onclick="fetchMacroRiskTimeline(true)">🔄 刷新数据</button>
                </div>
            </div>

            <div class="tl-filter-tabs">
                <span class="tl-risk-label">风险等级:</span>
                <button class="tl-risk-btn ${filterRisk==='all'?'active':''}" onclick="switchFilter('risk','all')">全部</button>
                <button class="tl-risk-btn high ${filterRisk==='高'?'active':''}" onclick="switchFilter('risk','高')">🔴 高风险</button>
                <button class="tl-risk-btn medium ${filterRisk==='中'?'active':''}" onclick="switchFilter('risk','中')">🟡 中风险</button>
                <button class="tl-risk-btn low ${filterRisk==='低'?'active':''}" onclick="switchFilter('risk','低')">🟢 低风险</button>
            </div>

            <div class="tl-main-area">
                <div class="tl-timeline-container">
                    ${renderTimeline(filteredEvents)}
                </div>
                <div class="tl-detail-panel">
                    ${selectedEvent ? renderDetail(selectedEvent) : '<div class="tl-detail-placeholder">点击左侧事件查看详情</div>'}
                </div>
            </div>
        </div>
    `;
    container.innerHTML = html;
}

// ══════════════════════════════════════════════════════════════════════════════
// 时间线渲染
// ══════════════════════════════════════════════════════════════════════════════

function renderTimeline(events) {
    if (!events || events.length === 0) {
        return '<div class="tl-empty">暂无匹配的宏观风险事件</div>';
    }

    const sorted = [...events].sort((a, b) => {
        const da = a.first_occurrence || a.date || '';
        const db = b.first_occurrence || b.date || '';
        return db.localeCompare(da);
    });

    const now = new Date();
    return `
        <div class="tl-line-header">📌 宏观风险时间线</div>
        <div class="tl-line">
            ${sorted.map(ev => {
                const fo = ev.first_occurrence || ev.date || '';
                const status = ev.time_status || '进行中';
                const level = ev.risk_level || '中';
                let dotClass = 'tl-dot level-' + (level === '高' ? 'high' : level === '中' ? 'mid' : 'low');
                let dotTimeClass = 'dot-current';
                if (status === '已结束') dotTimeClass = 'dot-past';
                if (status === '预期发生') dotTimeClass = 'dot-future';
                return `
                    <div class="tl-item ${dotTimeClass}" onclick="selectEvent('${escapeStr(ev.title)}')">
                        <div class="${dotClass}"></div>
                        <div class="tl-date">${fmtDate(fo)} ${ev.source ? '· '+ev.source : ''}</div>
                        <div class="tl-title">${riskLabel(level)} ${ev.title}</div>
                        <div class="tl-meta-row">
                            <span class="tl-duration">⏱ ${ev.duration||'中期影响'}</span>
                            <span class="tl-risk level-${level==='高'?'high':level==='中'?'mid':'low'}">${riskDot(level)} ${level}风险</span>
                            <span>${ev.category||''}</span>
                        </div>
                    </div>
                `;
            }).join('')}
        </div>
    `;
}

// ══════════════════════════════════════════════════════════════════════════════
// 详情面板
// ══════════════════════════════════════════════════════════════════════════════

function renderDetail(ev) {
    return `
        <div class="tl-detail-header">
            <div class="tl-detail-title">${ev.title || ''}</div>
            <div class="tl-detail-badges">
                ${riskLabel(ev.risk_level)}
                <span class="tl-badge">${ev.category||'其他'}</span>
                <span class="tl-badge">${ev.source||'未知来源'}</span>
                <span class="tl-badge">${ev.time_status||'进行中'}</span>
            </div>
        </div>
        <div class="tl-detail-section">
            <div class="tl-detail-grid">
                <div class="tl-detail-item">
                    <span class="tl-detail-key">首次发生</span>
                    <span class="tl-detail-val">${fmtDate(ev.first_occurrence||ev.date||'')}</span>
                </div>
                <div class="tl-detail-item">
                    <span class="tl-detail-key">持续时间</span>
                    <span class="tl-detail-val">${ev.duration||'未知'}</span>
                </div>
                <div class="tl-detail-item">
                    <span class="tl-detail-key">预估结束</span>
                    <span class="tl-detail-val">${fmtDate(ev.estimated_end||'') || '持续中'}</span>
                </div>
                <div class="tl-detail-item">
                    <span class="tl-detail-key">时间分析</span>
                    <span class="tl-detail-val">${ev.time_reasoning||''}</span>
                </div>
            </div>
        </div>
        ${ev.summary ? `
        <div class="tl-detail-section">
            <div class="tl-detail-label">事件摘要</div>
            <div class="tl-detail-summary">${ev.summary}</div>
        </div>` : ''}
        ${ev.url ? `
        <div class="tl-detail-link">
            <a href="${ev.url}" target="_blank" rel="noopener">🔗 查看原文</a>
        </div>` : ''}
    `;
}

// ══════════════════════════════════════════════════════════════════════════════
// 事件选择
// ══════════════════════════════════════════════════════════════════════════════

function selectEvent(title) {
    const allEvents = getAllEvents();
    selectedEvent = allEvents.find(e => e.title === title) || null;
    renderMacroView();
}

function getAllEvents() {
    if (!macroData || !macroData.timeline) return [];
    const tl = macroData.timeline;
    return [...(tl.past?.events||[]), ...(tl.current?.events||[]), ...(tl.future?.events||[])];
}

// ══════════════════════════════════════════════════════════════════════════════
// 筛选切换
// ══════════════════════════════════════════════════════════════════════════════

function switchFilter(type, val) {
    if (type === 'risk') filterRisk = val;
    if (type === 'time') filterTime = val;
    selectedEvent = null;
    renderMacroView();
}

function escapeStr(s) {
    if (!s) return '';
    return s.replace(/'/g, "\\'").replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ══════════════════════════════════════════════════════════════════════════════
// 初始化
// ══════════════════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    fetchMacroRiskTimeline(false);
});
