/**
 * 宏观日历组件
 */

// 预定义的宏观日历数据
const MACRO_EVENTS = {
    '01': {
        name: '一月',
        events: [
            { date: '01-15', title: '12月CPI/PPI', category: '物价', importance: 'high' },
            { date: '01-31', title: '1月PMI', category: '制造业', importance: 'high' },
        ]
    },
    '02': {
        name: '二月',
        events: [
            { date: '02-10', title: '1月CPI/PPI', category: '物价', importance: 'high' },
            { date: '02-28', title: '2月PMI', category: '制造业', importance: 'high' },
        ]
    },
    '03': {
        name: '三月',
        events: [
            { date: '03-09', title: '2月CPI/PPI', category: '物价', importance: 'high' },
            { date: '03-15', title: '2月经济数据', category: '经济', importance: 'high' },
            { date: '03-31', title: '3月PMI', category: '制造业', importance: 'high' },
        ]
    },
    '04': {
        name: '四月',
        events: [
            { date: '04-10', title: '3月CPI/PPI', category: '物价', importance: 'high' },
            { date: '04-16', title: '一季度GDP', category: '经济', importance: 'high' },
            { date: '04-30', title: '4月PMI', category: '制造业', importance: 'high' },
            { date: '04', title: '两会（全国人大/政协会议）', category: '政治', importance: 'high' },
        ]
    },
    '05': {
        name: '五月',
        events: [
            { date: '05-09', title: '4月CPI/PPI', category: '物价', importance: 'high' },
            { date: '05-31', title: '5月PMI', category: '制造业', importance: 'high' },
        ]
    },
    '06': {
        name: '六月',
        events: [
            { date: '06-10', title: '5月CPI/PPI', category: '物价', importance: 'high' },
            { date: '06-30', title: '6月PMI', category: '制造业', importance: 'high' },
            { date: '06', title: '美联储利率决议', category: '美联储', importance: 'high' },
        ]
    },
    '07': {
        name: '七月',
        events: [
            { date: '07-10', title: '6月CPI/PPI', category: '物价', importance: 'high' },
            { date: '07-15', title: '上半年经济数据', category: '经济', importance: 'high' },
            { date: '07-31', title: '7月PMI', category: '制造业', importance: 'high' },
            { date: '07', title: '年中政治局会议', category: '政治', importance: 'high' },
        ]
    },
    '08': {
        name: '八月',
        events: [
            { date: '08-09', title: '7月CPI/PPI', category: '物价', importance: 'high' },
            { date: '08-31', title: '8月PMI', category: '制造业', importance: 'high' },
        ]
    },
    '09': {
        name: '九月',
        events: [
            { date: '09-10', title: '8月CPI/PPI', category: '物价', importance: 'high' },
            { date: '09-15', title: '8月经济数据', category: '经济', importance: 'high' },
            { date: '09-30', title: '9月PMI', category: '制造业', importance: 'high' },
            { date: '09', title: '美联储利率决议', category: '美联储', importance: 'high' },
        ]
    },
    '10': {
        name: '十月',
        events: [
            { date: '10-14', title: '9月CPI/PPI', category: '物价', importance: 'high' },
            { date: '10-18', title: '三季度GDP', category: '经济', importance: 'high' },
            { date: '10-31', title: '10月PMI', category: '制造业', importance: 'high' },
        ]
    },
    '11': {
        name: '十一月',
        events: [
            { date: '11-09', title: '10月CPI/PPI', category: '物价', importance: 'high' },
            { date: '11-30', title: '11月PMI', category: '制造业', importance: 'high' },
            { date: '11', title: '中国国际进口博览会(CIIE)', category: '贸易', importance: 'medium' },
        ]
    },
    '12': {
        name: '十二月',
        events: [
            { date: '12-09', title: '11月CPI/PPI', category: '物价', importance: 'high' },
            { date: '12-15', title: '中央经济工作会议', category: '政治', importance: 'high' },
            { date: '12-31', title: '12月PMI', category: '制造业', importance: 'high' },
            { date: '12', title: '美联储利率决议', category: '美联储', importance: 'high' },
        ]
    }
};

// 事件类别样式
const CATEGORY_STYLES = {
    '物价': { icon: '📊', color: '#3b82f6' },
    '制造业': { icon: '🏭', color: '#8b5cf6' },
    '经济': { icon: '📈', color: '#10b981' },
    '政治': { icon: '🏛️', color: '#f59e0b' },
    '美联储': { icon: '💵', color: '#ef4444' },
    '贸易': { icon: '🌐', color: '#06b6d4' },
};

/**
 * 初始化宏观日历
 */
export function initMacroCalendar() {
    const calendar = document.getElementById('macro-calendar');
    if (!calendar) return;

    renderMacroCalendar(calendar);
}

/**
 * 渲染宏观日历
 */
export function renderMacroCalendar(container) {
    const currentYear = new Date().getFullYear();
    const currentMonth = String(new Date().getMonth() + 1).padStart(2, '0');

    let html = '<div class="macro-header">';
    html += `<h3>${currentYear} 宏观事件日历</h3>`;
    html += '<div class="macro-legend">';
    html += '<span class="legend-item"><span class="legend-dot high"></span>重要数据</span>';
    html += '<span class="legend-item"><span class="legend-dot medium"></span>一般事件</span>';
    html += '</div></div>';
    html += '<div class="macro-grid">';

    Object.entries(MACRO_EVENTS).forEach(([month, data]) => {
        const isCurrent = month === currentMonth;
        html += `<div class="macro-month ${isCurrent ? 'current' : ''}">`;
        html += `<div class="month-header">${data.name}${isCurrent ? ' <span class="current-tag">当前</span>' : ''}</div>`;
        html += '<div class="month-events">';

        data.events.forEach(event => {
            const style = CATEGORY_STYLES[event.category] || { icon: '📅', color: '#6b7280' };
            const importanceClass = event.importance === 'high' ? 'high' : 'medium';
            html += `<div class="event-item ${importanceClass}">
                <span class="event-date">${event.date}</span>
                <span class="event-content">
                    <span class="event-title">${event.title}</span>
                    <span class="event-category" style="color: ${style.color}">${style.icon} ${event.category}</span>
                </span>
            </div>`;
        });

        html += '</div></div>';
    });

    html += '</div>';
    container.innerHTML = html;
}

// 导出给全局使用
window.initMacroCalendar = initMacroCalendar;
