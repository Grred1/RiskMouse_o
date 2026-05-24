function switchSubTab(key) {
    document.querySelectorAll('.sub-tab').forEach(el => el.classList.remove('active'));
    const targetTab = document.querySelector(`.sub-tab[data-tab="${key}"]`);
    if (targetTab) targetTab.classList.add('active');
    document.querySelectorAll('.sub-tab-content').forEach(el => el.classList.remove('active'));
    document.getElementById('subtab-' + key).classList.add('active');

    if (key === 'growth' && !growthChartsRendered) {
        renderGrowthCharts();
        growthChartsRendered = true;
    }

    Object.keys(finChartInstances).forEach(k => {
        if (finChartInstances[k]) {
            setTimeout(() => finChartInstances[k].resize(), 100);
        }
    });
}

async function loadFinancialData() {
    const input = document.getElementById('symbolInput').value.trim().toUpperCase();
    if (!input) return;
    try {
        const resp = await fetch(`/api/financial?symbol=${encodeURIComponent(input)}`);
        if (!resp.ok) { showError('获取财务数据失败'); return; }
        financialData = await resp.json();
        document.getElementById('finSectionHeader').style.display = 'flex';
        document.getElementById('financialContent').style.display = 'block';
        renderFinancialCharts();
    } catch (e) {
        showError('财务数据请求失败: ' + e.message);
    }
}

function renderFinancialCharts() {
    if (!financialData) return;
    const abstract = financialData.financial_abstract || [];
    const profit = financialData.profit_sheet || [];
    const balance = financialData.balance_sheet || [];
    const cash = financialData.cash_flow || [];
    const code = financialData.code || '';
    const name = financialData.name || '';

    const latest = abstract.length > 0 ? abstract[abstract.length - 1] : {};
    const latestDate = latest['报告期'] || (profit.length > 0 ? profit[profit.length - 1].REPORT_DATE : '');

    renderKPI(latest);
    renderRevenueTrend(profit, abstract);
    renderBalanceStructure(balance);
    renderCashFlow(cash);
    renderGrowthCharts();
    growthChartsRendered = true;
    adjustFinLayout();

    requestFinancialAI(latest, profit, balance, cash);
}

function renderGrowthCharts() {
    if (!financialData) return;
    const profit = financialData.profit_sheet || [];
    const balance = financialData.balance_sheet || [];
    const abstract = financialData.financial_abstract || [];

    ['chart-rd', 'chart-expense', 'chart-asset-expansion', 'chart-profitability',
     'chart-revenue-trend', 'chart-balance', 'chart-cashflow'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            const panel = el.closest('.panel');
            if (panel) panel.style.display = '';
        }
    });

    renderRDExpense(profit);
    renderExpenseRate(profit);
    renderAssetExpansion(balance);
    renderProfitabilityTrend(abstract);
}

function renderKPI(latest) {
    const grid = document.getElementById('kpiGrid');
    grid.style.display = '';
    if (Object.keys(latest).length === 0) { grid.innerHTML = '<div style="color:#888;text-align:center;padding:20px;">暂无数据</div>'; return; }

    const items = [
        { label: '营业总收入', value: latest['营业总收入'], change: latest['营业总收入同比增长率'] },
        { label: '归母净利润', value: latest['净利润'], change: latest['净利润同比增长率'] },
        { label: '毛利率', value: latest['销售毛利率'] },
        { label: '净利率', value: latest['销售净利率'] },
        { label: 'ROE', value: latest['净资产收益率'] },
        { label: '资产负债率', value: latest['资产负债率'] },
        { label: '每股收益', value: latest['基本每股收益'] },
        { label: '每股经营现金流', value: latest['每股经营现金流'] },
    ];

    grid.innerHTML = items.map(item => {
        let val = item.value;
        let displayVal = val !== undefined && val !== null && val !== '' ? String(val) : '-';

        let changeHtml = '';
        if (item.change !== undefined && item.change !== null && item.change !== '') {
            const raw = String(item.change).replace('%', '').trim();
            const c = parseFloat(raw);
            if (!isNaN(c)) {
                const cls = c >= 0 ? 'up' : 'down';
                changeHtml = `<div class="kpi-change ${cls}">${c >= 0 ? '↑' : '↓'} ${Math.abs(c).toFixed(2)}%</div>`;
            } else {
                changeHtml = `<div class="kpi-change" style="color:#888">${item.change}</div>`;
            }
        }
        return `<div class="kpi-card"><div class="kpi-value">${displayVal}</div><div class="kpi-label">${item.label}</div>${changeHtml}</div>`;
    }).join('');
}

function renderRevenueTrend(profit, abstract) {
    const dom = document.getElementById('chart-revenue-trend');
    if (finChartInstances['revenue']) finChartInstances['revenue'].dispose();
    const chart = echarts.init(dom); finChartInstances['revenue'] = chart;

    const annualData = profit.filter(d => d.REPORT_TYPE === '年报').slice(-6);
    const labels = annualData.map(d => d.REPORT_DATE.slice(0, 4));
    const revenue = annualData.map(d => d.TOTAL_OPERATE_INCOME ? +(d.TOTAL_OPERATE_INCOME / 1e8).toFixed(2) : 0);
    const netProfit = annualData.map(d => d.NETPROFIT ? +(d.NETPROFIT / 1e8).toFixed(2) : 0);

    chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['营收(亿)', '净利润(亿)'], bottom: 5, left: 'center', textStyle: { fontSize: 12 } },
        grid: { left: '6%', right: '7%', bottom: 62, top: 20, containLabel: true },
        xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
        yAxis: { type: 'value', name: '金额(亿)', nameLocation: 'middle', nameRotate: 90, nameGap: 45, nameTextStyle: { fontSize: 11 }, axisLabel: { fontSize: 11 } },
        series: [
            { name: '营收(亿)', type: 'bar', barWidth: '30%', itemStyle: { color: '#4f8fdc', borderRadius: [4,4,0,0] }, data: revenue },
            { name: '净利润(亿)', type: 'bar', barWidth: '30%', itemStyle: { color: '#34d399', borderRadius: [4,4,0,0] }, data: netProfit },
        ]
    });
    window.addEventListener('resize', () => chart.resize());
}

function renderBalanceStructure(balance) {
    const dom = document.getElementById('chart-balance');
    if (finChartInstances['balance']) finChartInstances['balance'].dispose();
    const chart = echarts.init(dom); finChartInstances['balance'] = chart;

    const annual = balance.filter(d => d.REPORT_TYPE === '年报').slice(-5);
    const labels = annual.map(d => d.REPORT_DATE.slice(0, 4));
    const totalAssets = annual.map(d => d.TOTAL_ASSETS ? +(d.TOTAL_ASSETS / 1e8).toFixed(2) : 0);
    const totalLiab = annual.map(d => d.TOTAL_LIABILITIES ? +(d.TOTAL_LIABILITIES / 1e8).toFixed(2) : 0);
    const equity = annual.map(d => d.TOTAL_EQUITY ? +(d.TOTAL_EQUITY / 1e8).toFixed(2) : 0);

    chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['总资产(亿)', '总负债(亿)', '净资产(亿)'], bottom: 5, left: 'center', textStyle: { fontSize: 12 } },
        grid: { left: '6%', right: '7%', bottom: 62, top: 20, containLabel: true },
        xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
        yAxis: { type: 'value', name: '金额(亿)', nameLocation: 'middle', nameRotate: 90, nameGap: 45, nameTextStyle: { fontSize: 11 }, axisLabel: { fontSize: 11 } },
        series: [
            { name: '总资产(亿)', type: 'bar', barWidth: '22%', itemStyle: { color: '#4f8fdc', borderRadius: [4,4,0,0] }, data: totalAssets },
            { name: '总负债(亿)', type: 'bar', barWidth: '22%', itemStyle: { color: '#a78bfa', borderRadius: [4,4,0,0] }, data: totalLiab },
            { name: '净资产(亿)', type: 'bar', barWidth: '22%', itemStyle: { color: '#34d399', borderRadius: [4,4,0,0] }, data: equity },
        ]
    });
    window.addEventListener('resize', () => chart.resize());
}

function renderCashFlow(cash) {
    const dom = document.getElementById('chart-cashflow');
    if (finChartInstances['cashflow']) finChartInstances['cashflow'].dispose();
    const chart = echarts.init(dom); finChartInstances['cashflow'] = chart;

    const annual = cash.filter(d => d.REPORT_TYPE === '年报').slice(-5);
    const labels = annual.map(d => d.REPORT_DATE.slice(0, 4));
    const operate = annual.map(d => d.NETCASH_OPERATE ? +(d.NETCASH_OPERATE / 1e8).toFixed(2) : 0);
    const invest = annual.map(d => d.NETCASH_INVEST ? +(d.NETCASH_INVEST / 1e8).toFixed(2) : 0);
    const finance = annual.map(d => d.NETCASH_FINANCE ? +(d.NETCASH_FINANCE / 1e8).toFixed(2) : 0);

    chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['经营现金流(亿)', '投资现金流(亿)', '筹资现金流(亿)'], bottom: 5, left: 'center', textStyle: { fontSize: 12 } },
        grid: { left: '6%', right: '7%', bottom: 62, top: 20, containLabel: true },
        xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
        yAxis: { type: 'value', name: '金额(亿)', nameLocation: 'middle', nameRotate: 90, nameGap: 45, nameTextStyle: { fontSize: 11 }, axisLabel: { fontSize: 11 } },
        series: [
            { name: '经营现金流(亿)', type: 'bar', barWidth: '22%', itemStyle: { color: '#34d399', borderRadius: [4,4,0,0] }, data: operate },
            { name: '投资现金流(亿)', type: 'bar', barWidth: '22%', itemStyle: { color: '#a78bfa', borderRadius: [4,4,0,0] }, data: invest },
            { name: '筹资现金流(亿)', type: 'bar', barWidth: '22%', itemStyle: { color: '#fb923c', borderRadius: [4,4,0,0] }, data: finance },
        ]
    });
    window.addEventListener('resize', () => chart.resize());
}

function renderRDExpense(profit) {
    const dom = document.getElementById('chart-rd');
    const panel = dom ? dom.closest('.panel') : null;
    if (finChartInstances['rd']) finChartInstances['rd'].dispose();

    const annual = profit.filter(d => d.REPORT_TYPE === '年报').slice(-6);
    if (annual.length === 0 || !annual.some(d => d.RESEARCH_EXPENSE)) {
        if (panel) panel.style.display = 'none';
        if (finChartInstances['rd']) { finChartInstances['rd'].dispose(); delete finChartInstances['rd']; }
        return;
    }
    if (panel) panel.style.display = '';

    const chart = echarts.init(dom); finChartInstances['rd'] = chart;
    const labels = annual.map(d => d.REPORT_DATE.slice(0, 4));
    const rd = annual.map(d => d.RESEARCH_EXPENSE ? +(d.RESEARCH_EXPENSE / 1e8).toFixed(2) : 0);
    const rdYoy = annual.map(d => d.RESEARCH_EXPENSE_YOY ? +d.RESEARCH_EXPENSE_YOY.toFixed(2) : null);

    chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['研发投入(亿)', '同比增速(%)'], bottom: 5, left: 'center', textStyle: { fontSize: 12 } },
        grid: { left: '6%', right: '7%', bottom: 62, top: 20, containLabel: true },
        xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
        yAxis: [
            { type: 'value', name: '金额(亿)', nameLocation: 'middle', nameRotate: 90, nameGap: 45, nameTextStyle: { fontSize: 11 }, axisLabel: { fontSize: 11 } },
            { type: 'value', name: '增速(%)', nameLocation: 'middle', nameRotate: -90, nameGap: 40, nameTextStyle: { fontSize: 11 }, axisLabel: { fontSize: 11, formatter: '{value}%' } }
        ],
        series: [
            { name: '研发投入(亿)', type: 'bar', barWidth: '30%', itemStyle: { color: '#4f8fdc', borderRadius: [4,4,0,0] }, data: rd },
            { name: '同比增速(%)', type: 'line', yAxisIndex: 1, symbol: 'circle', symbolSize: 8, itemStyle: { color: '#a78bfa' }, data: rdYoy },
        ]
    });
    window.addEventListener('resize', () => chart.resize());
}

function renderExpenseRate(profit) {
    const dom = document.getElementById('chart-expense');
    const panel = dom ? dom.closest('.panel') : null;
    if (finChartInstances['expense']) finChartInstances['expense'].dispose();

    const annual = profit.filter(d => d.REPORT_TYPE === '年报').slice(-5);
    if (annual.length === 0 || !annual.some(d => d.RESEARCH_EXPENSE || d.SALE_EXPENSE || d.MANAGE_EXPENSE)) {
        if (panel) panel.style.display = 'none';
        if (finChartInstances['expense']) { finChartInstances['expense'].dispose(); delete finChartInstances['expense']; }
        return;
    }
    if (panel) panel.style.display = '';

    const chart = echarts.init(dom); finChartInstances['expense'] = chart;
    const labels = annual.map(d => d.REPORT_DATE.slice(0, 4));
    const calcRate = (exp, rev) => { return exp && rev ? +((exp / rev) * 100).toFixed(2) : 0; };
    const rdRate = annual.map(d => calcRate(d.RESEARCH_EXPENSE, d.TOTAL_OPERATE_INCOME));
    const saleRate = annual.map(d => calcRate(d.SALE_EXPENSE, d.TOTAL_OPERATE_INCOME));
    const mgmtRate = annual.map(d => calcRate(d.MANAGE_EXPENSE, d.TOTAL_OPERATE_INCOME));

    const legendData = [];
    const seriesData = [];
    if (rdRate.some(v => v > 0)) { legendData.push('研发费用率'); seriesData.push({ name: '研发费用率', type: 'line', symbol: 'circle', symbolSize: 8, lineStyle: { color: '#4facfe', width: 2 }, itemStyle: { color: '#4facfe' }, data: rdRate }); }
    if (saleRate.some(v => v > 0)) { legendData.push('销售费用率'); seriesData.push({ name: '销售费用率', type: 'line', symbol: 'circle', symbolSize: 8, lineStyle: { color: '#f093fb', width: 2 }, itemStyle: { color: '#f093fb' }, data: saleRate }); }
    if (mgmtRate.some(v => v > 0)) { legendData.push('管理费用率'); seriesData.push({ name: '管理费用率', type: 'line', symbol: 'circle', symbolSize: 8, lineStyle: { color: '#ffa726', width: 2 }, itemStyle: { color: '#ffa726' }, data: mgmtRate }); }

    chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: legendData, top: 0, left: 'center', textStyle: { fontSize: 12 } },
        grid: { left: '3%', right: '4%', bottom: '3%', top: '18%', containLabel: true },
        xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
        yAxis: { type: 'value', name: '占比(%)', axisLabel: { fontSize: 11, formatter: '{value}%' }, min: 0 },
        series: seriesData,
    });
    window.addEventListener('resize', () => chart.resize());
}

function renderAssetExpansion(balance) {
    const dom = document.getElementById('chart-asset-expansion');
    const panel = dom ? dom.closest('.panel') : null;
    if (finChartInstances['assetExp']) finChartInstances['assetExp'].dispose();

    const annual = balance.filter(d => d.REPORT_TYPE === '年报').slice(-5);
    if (annual.length === 0 || !annual.some(d => d.FIXED_ASSET)) {
        if (panel) panel.style.display = 'none';
        if (finChartInstances['assetExp']) { finChartInstances['assetExp'].dispose(); delete finChartInstances['assetExp']; }
        return;
    }
    if (panel) panel.style.display = '';

    const chart = echarts.init(dom); finChartInstances['assetExp'] = chart;
    const labels = annual.map(d => d.REPORT_DATE.slice(0, 4));
    const fixed = annual.map(d => d.FIXED_ASSET ? +(d.FIXED_ASSET / 1e8).toFixed(2) : 0);
    const inProgress = annual.map(d => d.CIP ? +(d.CIP / 1e8).toFixed(2) : 0);

    chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['固定资产(亿)', '在建工程(亿)'], bottom: 5, left: 'center', textStyle: { fontSize: 12 } },
        grid: { left: '6%', right: '7%', bottom: 62, top: 20, containLabel: true },
        xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
        yAxis: { type: 'value', name: '金额(亿)', nameLocation: 'middle', nameRotate: 90, nameGap: 45, nameTextStyle: { fontSize: 11 }, axisLabel: { fontSize: 11 } },
        series: [
            { name: '固定资产(亿)', type: 'bar', barWidth: '28%', itemStyle: { color: '#4f8fdc', borderRadius: [4,4,0,0] }, data: fixed },
            { name: '在建工程(亿)', type: 'bar', barWidth: '28%', itemStyle: { color: '#fb923c', borderRadius: [4,4,0,0] }, data: inProgress },
        ]
    });
    window.addEventListener('resize', () => chart.resize());
}

function renderProfitabilityTrend(abstract) {
    const dom = document.getElementById('chart-profitability');
    const panel = dom ? dom.closest('.panel') : null;
    if (finChartInstances['profitability']) finChartInstances['profitability'].dispose();

    const annual = abstract.filter(d => d['报告期'] && d['报告期'].endsWith('12-31')).slice(-5);
    if (annual.length === 0) {
        if (panel) panel.style.display = 'none';
        if (finChartInstances['profitability']) { finChartInstances['profitability'].dispose(); delete finChartInstances['profitability']; }
        return;
    }
    if (panel) panel.style.display = '';

    const chart = echarts.init(dom); finChartInstances['profitability'] = chart;
    const labels = annual.map(d => String(d['报告期']).slice(0, 4));
    const parsePct = (v) => { if (!v) return 0; const n = parseFloat(String(v).replace('%', '')); return isNaN(n) ? 0 : n; };
    const roe = annual.map(d => parsePct(d['净资产收益率']));
    const gross = annual.map(d => parsePct(d['销售毛利率']));
    const net = annual.map(d => parsePct(d['销售净利率']));

    chart.setOption({
        tooltip: { trigger: 'axis', formatter: function(p) { let s = `<b>${p[0].name}</b><br/>`; p.forEach(v => s += `${v.seriesName}: ${v.value}%<br/>`); return s; } },
        legend: { data: ['ROE', '毛利率', '净利率'], bottom: 5, left: 'center', textStyle: { fontSize: 12 } },
        grid: { left: '6%', right: '7%', bottom: 62, top: 20, containLabel: true },
        xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
        yAxis: { type: 'value', name: '%', nameLocation: 'middle', nameRotate: 90, nameGap: 45, nameTextStyle: { fontSize: 11 }, axisLabel: { fontSize: 11, formatter: '{value}%' }, max: value => Math.ceil(value.max * 1.10) },
        series: [
            { name: 'ROE', type: 'line', symbol: 'circle', symbolSize: 8, lineStyle: { color: '#4f8fdc', width: 2 }, itemStyle: { color: '#4f8fdc' }, data: roe },
            { name: '毛利率', type: 'line', symbol: 'circle', symbolSize: 8, lineStyle: { color: '#34d399', width: 2 }, itemStyle: { color: '#34d399' }, data: gross },
            { name: '净利率', type: 'line', symbol: 'circle', symbolSize: 8, lineStyle: { color: '#a78bfa', width: 2 }, itemStyle: { color: '#a78bfa' }, data: net },
        ]
    });
    window.addEventListener('resize', () => chart.resize());
}
