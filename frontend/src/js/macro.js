// 宏观经济日历
const MACRO_EVENTS = {
    1: [
        { date: '1月10日左右', name: 'CPI/PPI 月度数据', tag: 'normal' },
        { date: '1月中旬', name: '社融/信贷数据', tag: 'important' },
        { date: '1月31日', name: 'PMI 月度数据', tag: 'normal' },
    ],
    2: [
        { date: '2月10日左右', name: 'CPI/PPI 月度数据', tag: 'normal' },
        { date: '2月中旬', name: '社融/信贷数据', tag: 'important' },
        { date: '2月底', name: 'PMI 月度数据', tag: 'normal' },
    ],
    3: [
        { date: '3月5日', name: '全国两会开幕', tag: 'important' },
        { date: '3月10日左右', name: 'CPI/PPI 月度数据', tag: 'normal' },
        { date: '3月中旬', name: '1-2月经济数据（工业/消费/投资）', tag: 'important' },
        { date: '3月中旬', name: '社融/信贷数据', tag: 'important' },
        { date: '3月31日', name: 'PMI 月度数据', tag: 'normal' },
    ],
    4: [
        { date: '4月10日左右', name: 'CPI/PPI 月度数据', tag: 'normal' },
        { date: '4月中旬', name: '一季度GDP', tag: 'important' },
        { date: '4月中旬', name: '3月经济数据', tag: 'important' },
        { date: '4月中旬', name: '社融/信贷数据', tag: 'important' },
        { date: '4月30日', name: '政治局会议', tag: 'important' },
        { date: '4月30日', name: 'PMI 月度数据', tag: 'normal' },
    ],
    5: [
        { date: '5月10日左右', name: 'CPI/PPI 月度数据', tag: 'normal' },
        { date: '5月中旬', name: '社融/信贷数据', tag: 'important' },
        { date: '5月31日', name: 'PMI 月度数据', tag: 'normal' },
    ],
    6: [
        { date: '6月10日左右', name: 'CPI/PPI 月度数据', tag: 'normal' },
        { date: '6月中旬', name: '5月经济数据', tag: 'important' },
        { date: '6月中旬', name: '社融/信贷数据', tag: 'important' },
        { date: '6月底', name: 'PMI 月度数据', tag: 'normal' },
        { date: '6月底', name: '半年度经济数据前瞻', tag: 'warning' },
    ],
    7: [
        { date: '7月10日左右', name: 'CPI/PPI 月度数据', tag: 'normal' },
        { date: '7月中旬', name: '二季度GDP', tag: 'important' },
        { date: '7月中旬', name: '6月经济数据', tag: 'important' },
        { date: '7月中旬', name: '社融/信贷数据', tag: 'important' },
        { date: '7月底', name: '政治局会议（上半年经济形势）', tag: 'important' },
        { date: '7月31日', name: 'PMI 月度数据', tag: 'normal' },
    ],
    8: [
        { date: '8月10日左右', name: 'CPI/PPI 月度数据', tag: 'normal' },
        { date: '8月中旬', name: '7月经济数据', tag: 'important' },
        { date: '8月中旬', name: '社融/信贷数据', tag: 'important' },
        { date: '8月31日', name: 'PMI 月度数据', tag: 'normal' },
    ],
    9: [
        { date: '9月10日左右', name: 'CPI/PPI 月度数据', tag: 'normal' },
        { date: '9月中旬', name: '8月经济数据', tag: 'important' },
        { date: '9月中旬', name: '社融/信贷数据', tag: 'important' },
        { date: '9月底', name: 'PMI 月度数据', tag: 'normal' },
        { date: '9月底', name: '三季度经济前瞻', tag: 'warning' },
    ],
    10: [
        { date: '10月10日左右', name: 'CPI/PPI 月度数据', tag: 'normal' },
        { date: '10月中旬', name: '三季度GDP', tag: 'important' },
        { date: '10月中旬', name: '9月经济数据', tag: 'important' },
        { date: '10月中旬', name: '社融/信贷数据', tag: 'important' },
        { date: '10月31日', name: 'PMI 月度数据', tag: 'normal' },
    ],
    11: [
        { date: '11月10日左右', name: 'CPI/PPI 月度数据', tag: 'normal' },
        { date: '11月中旬', name: '10月经济数据', tag: 'important' },
        { date: '11月中旬', name: '社融/信贷数据', tag: 'important' },
        { date: '11月30日', name: 'PMI 月度数据', tag: 'normal' },
    ],
    12: [
        { date: '12月10日左右', name: 'CPI/PPI 月度数据', tag: 'normal' },
        { date: '12月中旬', name: '11月经济数据', tag: 'important' },
        { date: '12月中旬', name: '社融/信贷数据', tag: 'important' },
        { date: '12月中旬', name: '中央经济工作会议', tag: 'important' },
        { date: '12月31日', name: 'PMI 月度数据', tag: 'normal' },
    ],
};

const MONTH_NAMES = ['一月','二月','三月','四月','五月','六月','七月','八月','九月','十月','十一月','十二月'];

function renderMacroCalendar() {
    const container = document.getElementById('macroCalendarContent');
    if (!container) return;

    const now = new Date();
    const currentMonth = now.getMonth() + 1;

    let html = '<div class="macro-calendar">';
    for (let m = 1; m <= 12; m++) {
        const events = MACRO_EVENTS[m] || [];
        const isCurrent = m === currentMonth;
        html += `<div class="macro-month" style="${isCurrent ? 'border-left:3px solid #c0392b;padding-left:12px;' : ''}">
            <h4>${isCurrent ? '🔴 ' : ''}${MONTH_NAMES[m-1]}</h4>`;
        events.forEach(ev => {
            html += `<div class="macro-event">
                <span class="event-date">${ev.date}</span>
                <span class="event-name">${ev.name}</span>
                <span class="event-tag ${ev.tag}">${ev.tag === 'important' ? '重要' : ev.tag === 'warning' ? '关注' : '常规'}</span>
            </div>`;
        });
        html += '</div>';
    }
    html += '</div>';
    container.innerHTML = html;
}

document.addEventListener('DOMContentLoaded', renderMacroCalendar);
