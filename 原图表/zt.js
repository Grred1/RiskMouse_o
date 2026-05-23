let ztPoolData = null;

document.addEventListener('DOMContentLoaded', function() {
    const dt = document.getElementById('ztDateInput');
    if (dt) {
        const d = new Date();
        dt.value = d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
    }
});

async function fetchZTPool() {
    const btn = document.getElementById('ztFetchBtn');
    const dateInput = document.getElementById('ztDateInput');
    const date = dateInput.value.replace(/-/g, '');
    const tableBody = document.getElementById('ztTableBody');
    const summary = document.getElementById('ztSummary');
    const error = document.getElementById('ztError');

    btn.disabled = true;
    btn.textContent = '获取中...';
    error.style.display = 'none';
    tableBody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#999;padding:30px;">正在获取数据...</td></tr>';
    summary.textContent = '';

    try {
        const resp = await fetch(`/api/zt/pool?date=${encodeURIComponent(date)}`);
        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || '请求失败');
        }
        ztPoolData = await resp.json();
        renderZTPool();
        btn.textContent = '✅ 已更新';
        setTimeout(() => { btn.textContent = '🔄 获取涨停数据'; btn.disabled = false; }, 2000);
    } catch (e) {
        error.textContent = '❌ ' + e.message;
        error.style.display = 'block';
        tableBody.innerHTML = '';
        btn.textContent = '🔄 获取涨停数据';
        btn.disabled = false;
    }
}

function renderZTPool() {
    if (!ztPoolData || !ztPoolData.stocks) return;
    const { stocks, total, multi_board_total, date } = ztPoolData;
    const tableBody = document.getElementById('ztTableBody');
    const summary = document.getElementById('ztSummary');
    const detailPanel = document.getElementById('ztDetailPanel');

    summary.textContent = `📅 ${date.slice(0,4)}-${date.slice(4,6)}-${date.slice(6,8)}  ·  涨停 ${total} 只  ·  二板以上 ${multi_board_total} 只`;
    detailPanel.style.display = 'none';

    tableBody.innerHTML = stocks.map(s => {
        const board = s['连板数'] || 0;
        const isMulti = board >= 2;
        return `<tr class="${isMulti ? 'row-multi' : ''}" onclick="showZTDetail('${s['代码']}','${s['名称']}',${board},'${s['所属行业']||''}')" style="cursor:pointer;">
            <td>${s['序号']}</td>
            <td><strong>${s['代码']}</strong></td>
            <td>${s['名称']}</td>
            <td style="color:${board>=2?'#e74c3c':'#e67e22'};font-weight:${board>=2?'700':'400'};">${board}连板</td>
            <td>${s['涨跌幅']?s['涨跌幅'].toFixed(2):'-'}%</td>
            <td>${s['所属行业']||'-'}</td>
            <td>${s['封板资金']?fmtMoney(s['封板资金']):'-'}</td>
        </tr>`;
    }).join('');
}

async function showZTDetail(code, name, board, industry) {
    const panel = document.getElementById('ztDetailPanel');
    const header = document.getElementById('ztDetailHeader');
    const logicArea = document.getElementById('ztLogicArea');
    const zygcArea = document.getElementById('ztZygcArea');
    const analysisArea = document.getElementById('ztAnalysisArea');
    const loading = document.getElementById('ztDetailLoading');

    header.textContent = `${name}(${code}) — ${board}连板 · ${industry}`;
    panel.style.display = 'block';
    loading.style.display = 'block';
    logicArea.textContent = '';
    zygcArea.textContent = '';
    analysisArea.textContent = '';

    const defaultLogics = {
        "300069": ["跨界收购商业航天标的(中科西光82.5%股权)，涉足高光谱遥感卫星领域", "核心玻璃绝缘子业务受益特高压电网投资，浙江扩产已投产，山西新项目预计2026年投产", "2026年5月20日发布非公开增发预案", "2026年Q1业绩扭亏为盈(净利润303.96万)"],
        "603779": ["淄博国资入主: 齐信数科(淄博财政局)以股抵债方式受让23.12%股份", "国资承诺36个月不减持，带来信用背书和资金支持", "产品结构升级，有机葡萄酒占营收超6成", "公司紧急辟谣: 无算力资产注入计划", "7天暴涨94.9%，换手率42.63%，纯情绪炒作风险极高"],
        "000518": ["2026年5月20日起撤销退市风险警示(摘帽)", "摘帽条件靠绿化工程业务营收暴增38倍，而非医药主业回暖", "绿化工程毛利率极低(苗木3.55%)，可持续性存疑"],
        "600611": ["'两翼四柱'战略转型，数智交通+数据算力业务占比超70%", "特斯拉FSD入华催化无人驾驶板块情绪", "参股基金间接持有长江存储约0.051%股份", "2026Q1归母净利润-1.66亿(-360.62%)，业绩大幅下滑"],
        "002442": ["炭黑行业景气度回升，90天内炭黑价格涨6.32%", "全国产能布局完成，总产能居行业前三", "董事长刘鹏达5月15日增持164.81万股", "炭黑毛利率仅4.99%，主业盈利能力极弱"],
        "603316": ["从传统生态环境成功转型'生态+半导体存储'双主业", "半导体存储业务收入同比增长超200%", "近1亿元定增募资落地，用于嵌入式存储芯片扩产", "存储业务毛利率14.91%偏低"],
    };
    const logics = defaultLogics[code] || ["（暂未搜集到上涨逻辑）"];
    logicArea.textContent = logics.map((l, i) => `${i+1}. ${l}`).join('\n');

    try {
        const resp = await fetch('/api/zt/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                code, name, board, industry,
                logic: logics.map((l, i) => `${i+1}. ${l}`).join('\n'),
            }),
        });
        const result = await resp.json();
        zygcArea.textContent = result.zygc || '暂无数据';
        analysisArea.textContent = result.risk_analysis || '暂无分析';
    } catch (e) {
        analysisArea.textContent = '分析请求失败: ' + e.message;
    }

    loading.style.display = 'none';
}
