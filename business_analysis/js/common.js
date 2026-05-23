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
    document.querySelectorAll('.nav-tab').forEach(el => el.classList.remove('active'));
    document.querySelector(`.nav-tab[data-feature="${feature}"]`).classList.add('active');
    document.querySelectorAll('.feature-section').forEach(el => el.classList.remove('active'));
    document.getElementById(`feature-${feature}`).classList.add('active');
}

// 宏观日历初始化
function initMacroCalendar() {
    const monthInput = document.getElementById('macroMonthInput');
    if (monthInput) {
        // 默认显示当前月份
        const now = new Date();
        monthInput.value = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
        monthInput.addEventListener('change', function() {
            renderMacroCalendar(this.value);
        });
    }
}

// 渲染宏观日历
function renderMacroCalendar(yearMonth) {
    const calendar = document.getElementById('macroCalendar');
    if (!yearMonth) return;

    const [year, month] = yearMonth.split('-').map(Number);

    // 预定义的宏观事件数据
    const events = {
        '01': [
            { date: 10, name: '12月CPI/PPI公布', type: 'macro' },
            { date: 15, name: '12月进出口数据', type: 'macro' },
            { date: 20, name: '1月LPR公布', type: 'policy' },
            { date: 25, name: '12月规模以上工业利润', type: 'macro' },
        ],
        '02': [
            { date: 10, name: '1月CPI/PPI公布', type: 'macro' },
            { date: 15, name: '1月社融/M2数据', type: 'macro' },
            { date: 23, name: '2月LPR公布', type: 'policy' },
        ],
        '03': [
            { date: 9, name: '2月CPI/PPI公布', type: 'macro' },
            { date: 10, name: '2月社融数据', type: 'macro' },
            { date: 15, name: '2月经济数据', type: 'macro' },
            { date: 20, name: '3月LPR公布', type: 'policy' },
            { date: 25, name: '全国两会（通常）', type: 'policy' },
            { date: 31, name: '季度GDP数据', type: 'macro' },
        ],
        '04': [
            { date: 10, name: '3月CPI/PPI公布', type: 'macro' },
            { date: 12, name: '3月社融数据', type: 'macro' },
            { date: 20, name: '4月LPR公布', type: 'policy' },
            { date: 30, name: '年报披露截止', type: 'report' },
        ],
        '05': [
            { date: 10, name: '4月CPI/PPI公布', type: 'macro' },
            { date: 15, name: '4月社融数据', type: 'macro' },
            { date: 20, name: '5月LPR公布', type: 'policy' },
            { date: 25, name: '4月工业企业利润', type: 'macro' },
        ],
        '06': [
            { date: 9, name: '5月CPI/PPI公布', type: 'macro' },
            { date: 10, name: '5月社融数据', type: 'macro' },
            { date: 15, name: '5月经济数据', type: 'macro' },
            { date: 20, name: '6月LPR公布', type: 'policy' },
            { date: 30, name: '季度GDP初值', type: 'macro' },
        ],
        '07': [
            { date: 10, name: '6月CPI/PPI公布', type: 'macro' },
            { date: 12, name: '6月社融数据', type: 'macro' },
            { date: 15, name: '上半年经济数据', type: 'macro' },
            { date: 22, name: '7月LPR公布', type: 'policy' },
            { date: 30, name: '政治局会议（年中）', type: 'policy' },
        ],
        '08': [
            { date: 9, name: '7月CPI/PPI公布', type: 'macro' },
            { date: 13, name: '7月社融数据', type: 'macro' },
            { date: 20, name: '8月LPR公布', type: 'policy' },
            { date: 31, name: '半年报披露截止', type: 'report' },
        ],
        '09': [
            { date: 10, name: '8月CPI/PPI公布', type: 'macro' },
            { date: 13, name: '8月社融数据', type: 'macro' },
            { date: 15, name: '8月经济数据', type: 'macro' },
            { date: 20, name: '9月LPR公布', type: 'policy' },
            { date: 30, name: '季度GDP修正值', type: 'macro' },
        ],
        '10': [
            { date: 10, name: '9月CPI/PPI公布', type: 'macro' },
            { date: 14, name: '9月社融数据', type: 'macro' },
            { date: 20, name: '10月LPR公布', type: 'policy' },
            { date: 25, name: '9月工业企业利润', type: 'macro' },
            { date: 30, name: '三季度GDP', type: 'macro' },
        ],
        '11': [
            { date: 9, name: '10月CPI/PPI公布', type: 'macro' },
            { date: 11, name: '10月社融数据', type: 'macro' },
            { date: 15, name: '10月经济数据', type: 'macro' },
            { date: 20, name: '11月LPR公布', type: 'policy' },
        ],
        '12': [
            { date: 9, name: '11月CPI/PPI公布', type: 'macro' },
            { date: 10, name: '11月社融数据', type: 'macro' },
            { date: 15, name: '11月经济数据', type: 'macro' },
            { date: 20, name: '12月LPR公布', type: 'policy' },
            { date: 28, name: '政治局会议（年末）', type: 'policy' },
            { date: 31, name: '三季度报披露截止', type: 'report' },
        ],
    };

    const monthKey = String(month).padStart(2, '0');
    const monthEvents = events[monthKey] || [];

    if (monthEvents.length === 0) {
        calendar.innerHTML = `
            <div class="macro-placeholder">
                <div class="macro-icon">📅</div>
                <div>${year}年${month}月暂无预定义事件</div>
            </div>
        `;
        return;
    }

    let html = '<div class="calendar-grid">';
    monthEvents.forEach(event => {
        const tagClass = event.type === 'macro' ? 'tag-macro' : event.type === 'policy' ? 'tag-policy' : 'tag-report';
        const tagText = event.type === 'macro' ? '宏观' : event.type === 'policy' ? '政策' : '财报';
        html += `
            <div class="calendar-event">
                <div class="event-date-badge">${event.date}日</div>
                <div class="event-info">
                    <div class="event-title">${event.name}</div>
                    <span class="event-tag ${tagClass}">${tagText}</span>
                </div>
            </div>
        `;
    });
    html += '</div>';

    // 添加内联样式
    const style = document.createElement('style');
    style.textContent = `
        .calendar-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
            gap: 12px;
        }
        .calendar-event {
            display: flex;
            gap: 12px;
            padding: 14px;
            background: #21262d;
            border-radius: 8px;
            border: 1px solid #30363d;
            transition: all 0.2s;
        }
        .calendar-event:hover {
            border-color: #58a6ff;
            transform: translateY(-2px);
        }
        .event-date-badge {
            background: linear-gradient(135deg, #58a6ff, #388bfd);
            color: #fff;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            white-space: nowrap;
        }
        .event-info {
            flex: 1;
        }
        .event-title {
            font-size: 13px;
            color: #e6edf3;
            margin-bottom: 6px;
        }
    `;

    calendar.innerHTML = html;
    if (!document.getElementById('calendar-styles')) {
        style.id = 'calendar-styles';
        document.head.appendChild(style);
    }
}

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', initMacroCalendar);

