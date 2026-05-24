// ══════════════════════════════════════════════════════════════════════════════
// 宏观风险时间轴 & 月历
// ══════════════════════════════════════════════════════════════════════════════

const MONTH_NAMES = ['一月','二月','三月','四月','五月','六月','七月','八月','九月','十月','十一月','十二月'];
const MONTH_KEYS = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];
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

let pollTimer = null;

async function fetchMacroRiskTimeline(refresh = false, background = false) {
    const container = document.getElementById('macroCalendarContent');
    if (!container) return;
    container.innerHTML = '<div class="macro-loading"><div class="spinner"></div>正在加载宏观风险数据...</div>';

    try {
        const params = new URLSearchParams({ refresh: refresh, days: '30' });
        if (background) params.set('background', 'true');
        const url = `/api/macro/risk-timeline?${params}`;
        const r = await fetch(url);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        if (data.error) throw new Error(data.error);
        macroData = data;

        // 首次无缓存 → 自动触发后台采集 + 轮询等待
        if (data.cache_status === 'no_cache') {
            container.innerHTML = '<div class="macro-loading"><div class="spinner"></div>首次加载中，正在采集宏观风险数据 (约1-2分钟)...</div>';
            fetch('/api/macro/risk-timeline?refresh=true&background=true&days=30').catch(() => {});
            startPolling();
            return;
        }

        // 后台采集已启动 → 进入轮询等待
        if (data.cache_status === 'background_started' || data.cache_status === 'background_updating') {
            container.innerHTML = '<div class="macro-loading"><div class="spinner"></div>正在更新数据...</div>';
            startPolling();
            return;
        }

        renderMacroView();
    } catch (e) {
        container.innerHTML = `<div class="macro-error">数据加载失败: ${e.message}</div>`;
    }
}

function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    // 5秒后开始轮询，每5秒查一次，最多查60次（5分钟）
    setTimeout(() => {
        let attempts = 0;
        pollTimer = setInterval(async () => {
            attempts++;
            if (attempts > 60) {
                clearInterval(pollTimer);
                pollTimer = null;
                const container = document.getElementById('macroCalendarContent');
                if (container) container.innerHTML = '<div class="macro-error">数据加载超时，请点击刷新重试</div>';
                return;
            }
            try {
                const r = await fetch('/api/macro/risk-timeline?refresh=false&days=30');
                const data = await r.json();
                if (data && data.timeline && (data.timeline.past?.events?.length > 0 || data.timeline.current?.events?.length > 0 || data.timeline.future?.events?.length > 0)) {
                    clearInterval(pollTimer);
                    pollTimer = null;
                    macroData = data;
                    renderMacroView();
                }
            } catch (e) {}
        }, 5000);
    }, 5000);
}

function refreshData() {
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
    fetchMacroRiskTimeline(true, true);
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
                    <button class="rc-btn-refresh" style="background:${selectedView==='timeline'?'#4f8fdc':'#888'}" onclick="switchView('timeline')">📋 时间轴</button>
                    <button class="rc-btn-refresh" style="background:${selectedView==='calendar'?'#4f8fdc':'#888'}" onclick="switchView('calendar')">📅 月历</button>
                    <button class="rc-btn-refresh" onclick="refreshData()">🔄 刷新数据</button>
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
                ${selectedView === 'calendar'
                    ? renderCalendar(allEvents)
                    : `<div class="tl-timeline-container">
                        ${renderTimeline(filteredEvents)}
                    </div>
                    <div class="tl-detail-panel">
                        ${selectedEvent ? renderDetail(selectedEvent) : '<div class="tl-detail-placeholder">点击左侧事件查看详情</div>'}
                    </div>`
                }
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
// 视图切换
// ══════════════════════════════════════════════════════════════════════════════

function switchView(view) {
    selectedView = view;
    selectedEvent = null;
    renderMacroView();
}

// ══════════════════════════════════════════════════════════════════════════════
// 月历渲染
// ══════════════════════════════════════════════════════════════════════════════

function changeMonth(delta) {
    calendarMonth += delta;
    if (calendarMonth > 11) { calendarMonth = 0; calendarYear++; }
    if (calendarMonth < 0) { calendarMonth = 11; calendarYear--; }
    renderMacroView();
}

function renderCalendar(events) {
    const year = calendarYear;
    const month = calendarMonth;
    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const today = new Date();
    const todayStr = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;

    // 按日期分组事件
    const eventsByDate = {};
    events.forEach(ev => {
        const d = ev.first_occurrence || ev.date || '';
        if (!d) return;
        const key = d.substring(0, 10);
        if (!eventsByDate[key]) eventsByDate[key] = [];
        eventsByDate[key].push(ev);
    });

    let cells = '';
    for (let i = 0; i < firstDay; i++) {
        cells += '<div class="rc-day rc-day-empty"></div>';
    }
    for (let d = 1; d <= daysInMonth; d++) {
        const dateStr = `${year}-${String(month+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
        const isToday = dateStr === todayStr;
        const dayEvents = eventsByDate[dateStr] || [];
        let riskClass = '';
        if (dayEvents.length > 0) {
            const hasHigh = dayEvents.some(e => e.risk_level === '高');
            const hasMid = dayEvents.some(e => e.risk_level === '中');
            if (hasHigh) riskClass = 'rc-day-high';
            else if (hasMid) riskClass = 'rc-day-mid';
            else riskClass = 'rc-day-low';
        }
        const dots = dayEvents.slice(0, 3).map(e => {
            const dot = e.risk_level === '高' ? '🔴' : e.risk_level === '中' ? '🟡' : '🟢';
            return `<span title="${e.title}">${dot}</span>`;
        }).join('');
        const more = dayEvents.length > 3 ? `<span class="rc-more">+${dayEvents.length-3}</span>` : '';

        cells += `<div class="rc-day ${isToday?'rc-today':''} ${riskClass}" onclick="selectCalendarDay('${dateStr}')">
            <span class="rc-day-num">${d}</span>
            <div class="rc-day-dots">${dots}${more}</div>
        </div>`;
    }
    const remaining = (7 - (firstDay + daysInMonth) % 7) % 7;
    for (let i = 0; i < remaining; i++) {
        cells += '<div class="rc-day rc-day-empty"></div>';
    }

    const detailHtml = renderCalendarDetail();

    return `
        <div style="display:flex;flex-direction:row;flex-wrap:wrap;gap:12px;align-items:flex-start;">
            <div class="rc-calendar-wrap" style="flex:1;min-width:300px;">
                <div class="rc-cal-nav">
                    <button onclick="changeMonth(-1)">◀</button>
                    <span>${year}年 ${MONTH_KEYS[month]}</span>
                    <button onclick="changeMonth(1)">▶</button>
                </div>
                <div class="rc-cal-weekdays">
                    ${WEEKDAYS.map(w => `<div class="rc-weekday">${w}</div>`).join('')}
                </div>
                <div class="rc-cal-days">${cells}</div>
            </div>
            ${detailHtml}
        </div>
    `;
}

let selectedCalendarDate = null;

function selectCalendarDay(dateStr) {
    selectedCalendarDate = selectedCalendarDate === dateStr ? null : dateStr;
    renderMacroView();
}

function renderCalendarDetail() {
    if (!selectedCalendarDate) {
        return '<div class="rc-detail-panel" style="flex:0 0 360px;max-width:100%;"><div class="rc-detail-header"><span>点击日期查看事件</span></div></div>';
    }
    const allEvents = getAllEvents();
    const dayEvents = allEvents.filter(ev => {
        const d = ev.first_occurrence || ev.date || '';
        return d.substring(0, 10) === selectedCalendarDate;
    });
    const parts = selectedCalendarDate.split('-');
    const label = `${parseInt(parts[1])}月${parseInt(parts[2])}日`;
    if (dayEvents.length === 0) {
        return `<div class="rc-detail-panel" style="flex:0 0 360px;max-width:100%;">
            <div class="rc-detail-header"><span>📅 ${label}</span><button onclick="selectCalendarDay('${selectedCalendarDate}')">✕</button></div>
            <div class="rc-detail-list"><div style="padding:16px;text-align:center;color:#999;">暂无事件</div></div>
        </div>`;
    }
    return `<div class="rc-detail-panel" style="flex:0 0 360px;max-width:100%;">
        <div class="rc-detail-header"><span>📅 ${label} (${dayEvents.length}条)</span><button onclick="selectCalendarDay('${selectedCalendarDate}')">✕</button></div>
        <div class="rc-detail-list">${dayEvents.map(ev => `
            <div class="rc-detail-card">
                <div class="rc-detail-card-header">
                    <span class="rc-level-tag" style="border-color:${ev.risk_level==='高'?'#e74c3c':ev.risk_level==='中'?'#f39c12':'#27ae60'};color:${ev.risk_level==='高'?'#e74c3c':ev.risk_level==='中'?'#f39c12':'#27ae60'}">${ev.risk_level||'中'}风险</span>
                    <span class="rc-cat-tag">${ev.category||'其他'}</span>
                    <span class="rc-src-tag">${ev.source||''}</span>
                </div>
                <div class="rc-detail-title">${ev.title||''}</div>
                ${ev.summary ? `<div class="rc-detail-summary">${ev.summary}</div>` : ''}
                ${ev.url ? `<div class="rc-detail-url"><a href="${ev.url}" target="_blank">查看原文</a></div>` : ''}
            </div>
        `).join('')}</div>
    </div>`;
}

// ══════════════════════════════════════════════════════════════════════════════
// 初始化
// ══════════════════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    fetchMacroRiskTimeline(false);
});
