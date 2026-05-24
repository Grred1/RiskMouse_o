let chartInstances = {};
let allData = null;
let financialData = null;
let currentSymbol = '';
const CATEGORY_MAP = { '按行业分类': 'industry', '按产品分类': 'product', '按地区分类': 'region' };
const REVERSE_MAP = { 'industry': '按行业分类', 'product': '按产品分类', 'region': '按地区分类' };

document.addEventListener('DOMContentLoaded', function() {
    const input = document.getElementById('symbolInput');
    if (input) {
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') search();
        });
    }
});

function quickSearch(symbol) {
    document.getElementById('symbolInput').value = symbol;
    search();
}

function showError(msg) {
    const el = document.getElementById('errorMsg');
    el.textContent = msg;
    el.style.display = 'block';
}

function hideError() {
    document.getElementById('errorMsg').style.display = 'none';
}

async function search() {
    const input = document.getElementById('symbolInput').value.trim().toUpperCase();
    if (!input) { showError('请输入股票代码'); return; }
    hideError();

    // 重置切股状态
    growthChartsRendered = false;
    // 重置所有财务图表面板、grid 行、sub-tab 按钮为可见（避免上一只股票隐藏状态残留）
    document.querySelectorAll('#financialContent .panel').forEach(p => p.style.display = '');
    document.querySelectorAll('.fin-chart-grid').forEach(g => g.style.display = '');
    document.querySelectorAll('#finSectionHeader .sub-tab').forEach(t => t.style.display = '');

    document.getElementById('loadingOverlay').style.display = 'block';
    document.getElementById('loadingText').textContent = '正在获取主营构成数据...';
    document.getElementById('zygcLayout').style.display = 'none';
    document.getElementById('financialContent').style.display = 'none';
    document.getElementById('finSectionHeader').style.display = 'none';
    document.getElementById('stockInfo').style.display = 'none';
    document.getElementById('kpiGrid').style.display = 'none';
    document.getElementById('kpiGrid').innerHTML = '';
    document.getElementById('reportSelector').style.display = 'none';
    document.getElementById('aiSection').style.display = 'none';

    try {
        const resp = await fetch(`/api/zygc?symbol=${encodeURIComponent(input)}`);
        if (!resp.ok) {
            const err = await resp.json();
            showError(err.detail || '请求失败');
            document.getElementById('loadingOverlay').style.display = 'none';
            return;
        }
        allData = await resp.json();
        financialData = null;
        currentSymbol = input;
        render();
        document.getElementById('loadingText').textContent = '正在加载财务全景数据...';
        loadFinancialData();
    } catch (e) {
        showError('网络错误: ' + e.message);
    }
    document.getElementById('loadingOverlay').style.display = 'none';
}

async function refreshData() {
    if (!currentSymbol) return;
    const input = document.getElementById('symbolInput').value.trim().toUpperCase();
    hideError();

    // 重置所有财务图表面板、grid 行、sub-tab 按钮为可见（避免上一只股票隐藏状态残留）
    document.querySelectorAll('#financialContent .panel').forEach(p => p.style.display = '');
    document.querySelectorAll('.fin-chart-grid').forEach(g => g.style.display = '');
    document.querySelectorAll('#finSectionHeader .sub-tab').forEach(t => t.style.display = '');

    document.getElementById('loadingOverlay').style.display = 'block';
    document.getElementById('loadingText').textContent = '正在更新主营构成数据...';
    document.getElementById('zygcLayout').style.display = 'none';
    document.getElementById('financialContent').style.display = 'none';
    document.getElementById('finSectionHeader').style.display = 'none';
    document.getElementById('stockInfo').style.display = 'none';
    document.getElementById('kpiGrid').style.display = 'none';
    document.getElementById('kpiGrid').innerHTML = '';
    document.getElementById('reportSelector').style.display = 'none';
    document.getElementById('aiSection').style.display = 'none';

    try {
        const resp = await fetch(`/api/zygc?symbol=${encodeURIComponent(input)}&refresh=true`);
        if (!resp.ok) {
            const err = await resp.json();
            showError(err.detail || '请求失败');
            document.getElementById('loadingOverlay').style.display = 'none';
            return;
        }
        allData = await resp.json();
        financialData = null;
        currentSymbol = input;
        render();
        document.getElementById('loadingText').textContent = '正在更新财务全景数据...';
        loadFinancialData();
    } catch (e) {
        showError('网络错误: ' + e.message);
    }
    document.getElementById('loadingOverlay').style.display = 'none';
}

function render() {
    if (!allData || !allData.records || allData.records.length === 0) {
        showError('未获取到数据');
        return;
    }

    const dates = allData.report_dates;
    const symbols = allData.records.map(r => r.股票代码);
    const code = symbols[0] || allData.symbol;

    document.getElementById('stockInfo').style.display = 'block';
    document.getElementById('stockName').textContent = `${allData.name || ''} (${code})`;
    document.getElementById('stockMeta').textContent = `共 ${allData.total} 条记录 · ${dates.length} 个报告期 · ${allData.categories.length} 种分类维度`;

    const cacheBadge = document.getElementById('cacheBadge');
    const refreshBtn = document.getElementById('refreshBtn');
    if (allData.from_cache) {
        cacheBadge.style.display = 'inline';
        refreshBtn.style.display = 'inline-block';
    } else {
        cacheBadge.style.display = 'none';
        refreshBtn.style.display = 'none';
    }

    const sel = document.getElementById('reportSelect');
    sel.innerHTML = '';
    dates.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d;
        opt.textContent = d;
        sel.appendChild(opt);
    });

    document.getElementById('reportSelector').style.display = 'flex';
    document.getElementById('zygcLayout').style.display = 'flex';

    // 仅显示有数据的分类 Tab
    const availableCategories = new Set(allData.records.map(r => r.分类类型));
    document.querySelectorAll('.zygc-nav-item').forEach(el => {
        const catKey = el.dataset.tab;
        const catName = REVERSE_MAP[catKey];
        el.style.display = availableCategories.has(catName) ? '' : 'none';
    });

    // 如果当前激活的 Tab 被隐藏，切换到第一个可见 Tab
    const activeNav = document.querySelector('.zygc-nav-item.active');
    if (activeNav && activeNav.style.display === 'none') {
        const firstVisible = Array.from(document.querySelectorAll('.zygc-nav-item'))
            .find(el => el.style.display !== 'none');
        if (firstVisible) switchTab(firstVisible.dataset.tab);
    }

    onReportChange();
}

function onReportChange() {
    const date = document.getElementById('reportSelect').value;
    if (!date) return;

    hideError();

    const categories = ['industry', 'product', 'region'];
    categories.forEach(cat => renderCategory(cat, date));
    adjustFinLayout();
}

function renderCategory(catKey, date) {
    const catName = REVERSE_MAP[catKey];
    const records = allData.records.filter(r => r.分类类型 === catName && r.报告日期 === date);
    const sorted = [...records].sort((a, b) => b.收入比例 - a.收入比例);

    const tabContent = document.getElementById('tab-' + catKey);
    if (sorted.length === 0) {
        if (tabContent) tabContent.style.display = 'none';
        return;
    }
    if (tabContent) tabContent.style.display = '';

    renderTable(catKey, sorted);
    renderChart(catKey, sorted);
}

function renderTable(catKey, data) {
    const table = document.getElementById('table-' + catKey);
    let html = `<thead><tr>
        <th>构成项</th><th>主营收入(元)</th><th>收入比例</th><th>主营成本(元)</th><th>成本比例</th>
        <th>主营利润(元)</th><th>利润比例</th><th>毛利率</th>
    </tr></thead><tbody>`;
    data.forEach(row => {
        html += `<tr>
            <td>${row.主营构成}</td>
            <td>${fmtMoney(row.主营收入)}</td>
            <td>${row.收入比例}%</td>
            <td>${fmtMoney(row.主营成本)}</td>
            <td>${row.成本比例}%</td>
            <td>${fmtMoney(row.主营利润)}</td>
            <td>${row.利润比例}%</td>
            <td>${row.毛利率}%</td>
        </tr>`;
    });
    html += '</tbody>';
    table.innerHTML = html;
}

const ZYGC_COLORS = ['#4f8fdc', '#34d399', '#a78bfa', '#fb923c', '#f472b6', '#fbbf24', '#60a5fa', '#4ade80'];

function renderChart(catKey, data) {
    const dom = document.getElementById('chart-' + catKey);
    if (chartInstances[catKey]) chartInstances[catKey].dispose();
    const chart = echarts.init(dom);
    chartInstances[catKey] = chart;

    const names = data.map(r => r.主营构成);
    const revenue = data.map(r => +(r.主营收入 / 1e8).toFixed(2));
    const profit = data.map(r => +(r.主营利润 / 1e8).toFixed(2));
    const margin = data.map(r => +r.毛利率.toFixed(2));

    chart.setOption({
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            formatter(params) {
                let s = `<b>${params[0].name}</b><br/>`;
                params.forEach(p => {
                    if (p.seriesName === '毛利率') {
                        s += `${p.marker}${p.seriesName}: ${p.value}%<br/>`;
                    } else {
                        s += `${p.marker}${p.seriesName}: ${p.value} 亿<br/>`;
                    }
                });
                return s;
            }
        },
        legend: { data: ['主营收入(亿)', '主营利润(亿)', '毛利率'], bottom: 2, left: 'center', textStyle: { fontSize: 10 }, itemHeight: 8, itemWidth: 12 },
        grid: { left: '4%', right: '5%', bottom: 42, top: 8, containLabel: true },
        xAxis: { type: 'category', data: names, axisLabel: { fontSize: 10, overflow: 'truncate', width: 60 } },
        yAxis: [
            {
                type: 'value',
                name: '亿',
                nameLocation: 'end', nameTextStyle: { fontSize: 10, color: '#8fa3b8' },
                axisLabel: { fontSize: 10 }
            },
            {
                type: 'value',
                name: '%',
                nameLocation: 'end', nameTextStyle: { fontSize: 10, color: '#8fa3b8' },
                min: value => Math.floor(Math.min(0, value.min) * 1.15 - 5),
                max: value => Math.max(100, Math.ceil(value.max * 1.08)),
                axisLabel: { fontSize: 10, formatter: '{value}%' }
            }
        ],
        series: [
            { name: '主营收入(亿)', type: 'bar', barWidth: '28%', itemStyle: { color: '#4f8fdc', borderRadius: [4,4,0,0] }, data: revenue },
            { name: '主营利润(亿)', type: 'bar', barWidth: '28%', itemStyle: { color: '#34d399', borderRadius: [4,4,0,0] }, data: profit },
            { name: '毛利率', type: 'line', yAxisIndex: 1, symbol: 'circle', symbolSize: 8, lineStyle: { color: '#a78bfa', width: 2 }, itemStyle: { color: '#a78bfa' }, data: margin }
        ]
    });
    window.addEventListener('resize', () => chart.resize());
}

function switchTab(catKey) {
    document.querySelectorAll('.zygc-nav-item').forEach(el => el.classList.remove('active'));
    const target = document.querySelector(`.zygc-nav-item[data-tab="${catKey}"]`);
    if (target) target.classList.add('active');
    document.querySelectorAll('.tab-content').forEach(el => {
        el.classList.toggle('active', el.id === 'tab-' + catKey);
    });
    setTimeout(() => {
        if (chartInstances[catKey]) chartInstances[catKey].resize();
    }, 100);
}

// ===== 布局自适应 =====

function adjustFinLayout() {
    // 1. fin-chart-grid 内无可见 panel 时隐藏整个 grid 容器
    document.querySelectorAll('.fin-chart-grid').forEach(grid => {
        const hasVisible = Array.from(grid.querySelectorAll('.fin-panel'))
            .some(p => p.style.display !== 'none');
        grid.style.display = hasVisible ? '' : 'none';
    });

    // 2. sub-tab 下所有 panel 均无数据时，隐藏对应 tab 按钮
    document.querySelectorAll('.sub-tab-content').forEach(content => {
        const hasVisible = Array.from(content.querySelectorAll('.fin-panel'))
            .some(p => p.style.display !== 'none');
        const key = content.id.replace('subtab-', '');
        const tabBtn = document.querySelector(`#finSectionHeader .sub-tab[data-tab="${key}"]`);
        if (tabBtn) tabBtn.style.display = hasVisible ? '' : 'none';
    });

    // 3. 若所有 sub-tab 均隐藏，隐藏整个财务全景区域
    const anyVisibleTab = Array.from(document.querySelectorAll('#finSectionHeader .sub-tab'))
        .some(t => t.style.display !== 'none');
    if (!anyVisibleTab) {
        document.getElementById('finSectionHeader').style.display = 'none';
        document.getElementById('financialContent').style.display = 'none';
    }

    // 4. 若主营构成三个分类 nav 全部无数据，隐藏整个 zygcLayout
    const anyVisibleNav = Array.from(document.querySelectorAll('.zygc-nav-item'))
        .some(n => n.style.display !== 'none');
    if (!anyVisibleNav) {
        document.getElementById('zygcLayout').style.display = 'none';
    }
}

// ===== 财务全景 =====

let finChartInstances = {};
let growthChartsRendered = false;

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

    // 重置所有图表面板为可见，各 render 函数会根据数据有无自行隐藏
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

    // 只显示有数据的费用线
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

async function requestFinancialAI(latest, profit, balance, cash) {
    const section = document.getElementById('aiSection');
    const loading = document.getElementById('aiCombinedLoading');
    const content = document.getElementById('aiCombinedContent');
    section.style.display = 'block';
    loading.style.display = 'block';
    content.innerHTML = '';

    const code = financialData.code || '';
    const name = financialData.name || '';
    const annualProfit = profit.filter(d => d.REPORT_TYPE === '年报');
    const annualBalance = balance.filter(d => d.REPORT_TYPE === '年报');
    const latestBal = annualBalance.length > 0 ? annualBalance[annualBalance.length - 1] : {};
    const latestCashRaw = (cash.filter(d => d.REPORT_TYPE === '年报'));
    const latestCash = latestCashRaw.length > 0 ? latestCashRaw[latestCashRaw.length - 1] : {};
    const rdData = annualProfit.map(d => ({ date: d.REPORT_DATE, rd: d.RESEARCH_EXPENSE, rdYoy: d.RESEARCH_EXPENSE_YOY }));
    const trend = annualProfit.map(d => ({ date: d.REPORT_DATE, revenue: d.TOTAL_OPERATE_INCOME, profit: d.NETPROFIT }));

    const payload = {
        symbol: code, code, name,
        latestAbstract: latest,
        profitTrend: trend,
        balanceLatest: latestBal,
        cashLatest: latestCash,
        rdData: rdData,
        businessGrowth: {},
        assetExpansion: annualBalance.map(d => ({ date: d.REPORT_DATE, fixed: d.FIXED_ASSET, inProgress: d.CIP })),
    };

    try {
        const resp = await fetch('/api/analyze/financial-combined', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const result = await resp.json();
        loading.style.display = 'none';

        const scores = result.scores || {};
        const scoreConfig = [
            { key: 'solvency', label: '偿债', color: '#3498db' },
            { key: 'operating_capacity', label: '营运', color: '#e67e22' },
            { key: 'profitability', label: '盈利', color: '#27ae60' },
            { key: 'growth_and_cashflow', label: '成长', color: '#9b59b6' },
        ];

        // 评分行（标题后面）
        const scoreRow = document.getElementById('aiScoreRow');
        if (scoreRow) {
            scoreRow.innerHTML = scoreConfig.map(c => {
                const s = scores[c.key] || 0;
                const stars = '★'.repeat(s) + '☆'.repeat(5 - s);
                return `<span style="display:inline-flex;align-items:center;gap:3px;font-size:12px;color:${c.color};font-weight:600;background:#f5f6fa;padding:3px 10px;border-radius:12px;white-space:nowrap;">
                    ${c.label} ${s}${stars}
                </span>`;
            }).join('');
        }

        // 总体结论（右侧）
        const badge = document.getElementById('aiOverallBadge');
        if (badge && result.overall_conclusion) {
            badge.textContent = '📌 ' + result.overall_conclusion;
        }

        let html = '';

        // 详细分析 - 按关键指标分段格式化
        if (result.final_conclusion) {
            const text = result.final_conclusion;
            // 用 \n 分段
            const paragraphs = text.split('\n').filter(p => p.trim());
            html += `<div style="background:#f8f9fa;border-radius:10px;padding:14px;border:1px solid #e8ecf1;">
                <div style="font-size:13px;line-height:1.9;color:#444;white-space:pre-wrap;">`;
            paragraphs.forEach((p, i) => {
                const trimmed = p.trim();
                // 识别关键指标行（含数字/百分比/-/趋势词）
                const hasData = /[\d.]+%|[\d.]+亿|-?\d+\.\d+/.test(trimmed);
                const isKeyPoint = /风险|健康|稳定|恶化|改善|优秀|不足|关注/.test(trimmed);
                if (hasData) {
                    html += `<span style="display:block;padding:2px 0;">${trimmed}</span>`;
                } else if (isKeyPoint) {
                    html += `<span style="display:block;padding:3px 0;font-weight:600;color:#333;">${trimmed}</span>`;
                } else {
                    html += `<span style="display:block;padding:1px 0;">${trimmed}</span>`;
                }
            });
            html += `</div></div>`;
        }

        content.innerHTML = html || '<div style="color:#999;text-align:center;padding:20px;">暂无分析结果</div>';
    } catch (e) {
        loading.style.display = 'none';
        content.innerHTML = '<div style="color:#c0392b;text-align:center;padding:20px;">AI 分析请求失败: ' + e.message + '</div>';
    }
}
