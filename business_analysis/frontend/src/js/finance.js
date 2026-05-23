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

    document.getElementById('loadingOverlay').style.display = 'block';
    document.getElementById('loadingText').textContent = '正在获取主营构成数据...';
    document.getElementById('mainContent').style.display = 'none';
    document.getElementById('financialContent').style.display = 'none';
    document.getElementById('finSectionHeader').style.display = 'none';
    document.getElementById('stockInfo').style.display = 'none';
    document.getElementById('kpiGrid').style.display = 'none';
    document.getElementById('kpiGrid').innerHTML = '';
    document.getElementById('reportSelector').style.display = 'none';
    document.getElementById('tabs').style.display = 'none';
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

    document.getElementById('loadingOverlay').style.display = 'block';
    document.getElementById('loadingText').textContent = '正在更新主营构成数据...';
    document.getElementById('mainContent').style.display = 'none';
    document.getElementById('financialContent').style.display = 'none';
    document.getElementById('finSectionHeader').style.display = 'none';
    document.getElementById('stockInfo').style.display = 'none';
    document.getElementById('kpiGrid').style.display = 'none';
    document.getElementById('kpiGrid').innerHTML = '';
    document.getElementById('reportSelector').style.display = 'none';
    document.getElementById('tabs').style.display = 'none';
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
    document.getElementById('tabs').style.display = 'flex';

    onReportChange();
}

function onReportChange() {
    const date = document.getElementById('reportSelect').value;
    if (!date) return;

    hideError();
    document.getElementById('mainContent').style.display = 'block';

    const categories = ['industry', 'product', 'region'];
    categories.forEach(cat => renderCategory(cat, date));

    requestAIAnalysis(date);
}

function renderCategory(catKey, date) {
    const catName = REVERSE_MAP[catKey];
    const records = allData.records.filter(r => r.分类类型 === catName && r.报告日期 === date);
    const sorted = [...records].sort((a, b) => b.收入比例 - a.收入比例);

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

function renderChart(catKey, data) {
    const dom = document.getElementById('chart-' + catKey);
    if (chartInstances[catKey]) {
        chartInstances[catKey].dispose();
    }
    const chart = echarts.init(dom);
    chartInstances[catKey] = chart;

    const names = data.map(r => r.主营构成);
    const revenue = data.map(r => +(r.主营收入 / 1e8).toFixed(2));
    const profit = data.map(r => +(r.主营利润 / 1e8).toFixed(2));
    const margin = data.map(r => +r.毛利率.toFixed(2));

    const option = {
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            formatter: function(params) {
                let s = `<b>${params[0].name}</b><br/>`;
                params.forEach(p => {
                    if (p.seriesName === '毛利率') {
                        s += `${p.seriesName}: ${p.value}%<br/>`;
                    } else {
                        s += `${p.seriesName}: ${p.value} 亿<br/>`;
                    }
                });
                return s;
            }
        },
        legend: {
            data: ['主营收入(亿)', '主营利润(亿)', '毛利率'],
            top: 0,
            left: 'center',
            textStyle: { fontSize: 12 }
        },
        grid: { left: '3%', right: '4%', bottom: '3%', top: '18%', containLabel: true },
        xAxis: {
            type: 'category',
            data: names,
            axisLabel: { fontSize: 11 }
        },
        yAxis: [
            {
                type: 'value',
                name: '金额(亿)',
                nameTextStyle: { fontSize: 11 },
                axisLabel: { fontSize: 11 }
            },
            {
                type: 'value',
                name: '毛利率(%)',
                min: 0,
                max: 100,
                nameTextStyle: { fontSize: 11 },
                axisLabel: { fontSize: 11, formatter: '{value}%' }
            }
        ],
        series: [
            {
                name: '主营收入(亿)',
                type: 'bar',
                barWidth: '28%',
                itemStyle: { color: '#4facfe', borderRadius: [4, 4, 0, 0] },
                data: revenue
            },
            {
                name: '主营利润(亿)',
                type: 'bar',
                barWidth: '28%',
                itemStyle: { color: '#43e97b', borderRadius: [4, 4, 0, 0] },
                data: profit
            },
            {
                name: '毛利率',
                type: 'line',
                yAxisIndex: 1,
                symbol: 'circle',
                symbolSize: 8,
                lineStyle: { color: '#f093fb', width: 2 },
                itemStyle: { color: '#f093fb' },
                data: margin
            }
        ]
    };

    chart.setOption(option);
    window.addEventListener('resize', () => chart.resize());
}

function switchTab(catKey) {
    document.querySelectorAll('.tabs .tab').forEach(el => el.classList.remove('active'));
    document.querySelector(`.tabs .tab[data-tab="${catKey}"]`).classList.add('active');
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    const tabEl = document.getElementById('tab-' + catKey);
    if (tabEl) {
        tabEl.classList.add('active');
        setTimeout(() => {
            if (chartInstances[catKey]) chartInstances[catKey].resize();
        }, 100);
    }
}

async function requestAIAnalysis(date) {
    const section = document.getElementById('aiSection');
    const loading = document.getElementById('aiHealthLoading');
    const content = document.getElementById('aiHealthContent');
    if (!section || !loading || !content) return;
    section.style.display = 'block';
    loading.style.display = 'block';
    content.textContent = '';

    const latestData = {};
    for (const [catName, catKey] of Object.entries(CATEGORY_MAP)) {
        latestData[catName] = allData.records.filter(r => r.分类类型 === catName && r.报告日期 === date);
    }

    try {
        const resp = await fetch('/api/analyze/zygc', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol: currentSymbol, latestData }),
        });
        const result = await resp.json();
        loading.style.display = 'none';
        if (result.analysis) {
            content.textContent = result.analysis;
        } else {
            content.textContent = result.zygc_analysis || '暂无解读';
        }
    } catch (e) {
        loading.style.display = 'none';
        content.textContent = 'AI 解读请求失败: ' + e.message;
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

    requestFinancialAI(latest, profit, balance, cash);
}

function renderGrowthCharts() {
    if (!financialData) return;
    const profit = financialData.profit_sheet || [];
    const balance = financialData.balance_sheet || [];
    const abstract = financialData.financial_abstract || [];

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
        legend: { data: ['营收(亿)', '净利润(亿)'], top: 0, left: 'center', textStyle: { fontSize: 12 } },
        grid: { left: '3%', right: '4%', bottom: '3%', top: '18%', containLabel: true },
        xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
        yAxis: { type: 'value', name: '金额(亿)', axisLabel: { fontSize: 11 } },
        series: [
            { name: '营收(亿)', type: 'bar', barWidth: '30%', itemStyle: { color: '#4facfe', borderRadius: [4,4,0,0] }, data: revenue },
            { name: '净利润(亿)', type: 'bar', barWidth: '30%', itemStyle: { color: '#43e97b', borderRadius: [4,4,0,0] }, data: netProfit },
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
        legend: { data: ['总资产(亿)', '总负债(亿)', '净资产(亿)'], top: 0, left: 'center', textStyle: { fontSize: 12 } },
        grid: { left: '3%', right: '4%', bottom: '3%', top: '18%', containLabel: true },
        xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
        yAxis: { type: 'value', name: '金额(亿)', axisLabel: { fontSize: 11 } },
        series: [
            { name: '总资产(亿)', type: 'bar', barWidth: '22%', itemStyle: { color: '#4facfe', borderRadius: [4,4,0,0] }, data: totalAssets },
            { name: '总负债(亿)', type: 'bar', barWidth: '22%', itemStyle: { color: '#f093fb', borderRadius: [4,4,0,0] }, data: totalLiab },
            { name: '净资产(亿)', type: 'bar', barWidth: '22%', itemStyle: { color: '#43e97b', borderRadius: [4,4,0,0] }, data: equity },
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
        legend: { data: ['经营现金流(亿)', '投资现金流(亿)', '筹资现金流(亿)'], top: 0, left: 'center', textStyle: { fontSize: 12 } },
        grid: { left: '3%', right: '4%', bottom: '3%', top: '18%', containLabel: true },
        xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
        yAxis: { type: 'value', name: '金额(亿)', axisLabel: { fontSize: 11 } },
        series: [
            { name: '经营现金流(亿)', type: 'bar', barWidth: '22%', itemStyle: { color: '#43e97b', borderRadius: [4,4,0,0] }, data: operate },
            { name: '投资现金流(亿)', type: 'bar', barWidth: '22%', itemStyle: { color: '#f093fb', borderRadius: [4,4,0,0] }, data: invest },
            { name: '筹资现金流(亿)', type: 'bar', barWidth: '22%', itemStyle: { color: '#ffa726', borderRadius: [4,4,0,0] }, data: finance },
        ]
    });
    window.addEventListener('resize', () => chart.resize());
}

function renderRDExpense(profit) {
    const dom = document.getElementById('chart-rd');
    if (finChartInstances['rd']) finChartInstances['rd'].dispose();
    const chart = echarts.init(dom); finChartInstances['rd'] = chart;

    const annual = profit.filter(d => d.REPORT_TYPE === '年报').slice(-6);
    if (annual.length === 0 || !annual.some(d => d.RESEARCH_EXPENSE)) {
        chart.setOption({ title: { text: '研发投入数据不可用', left: 'center', top: 'center', textStyle: { fontSize: 14, color: '#999' } } });
        return;
    }
    const labels = annual.map(d => d.REPORT_DATE.slice(0, 4));
    const rd = annual.map(d => d.RESEARCH_EXPENSE ? +(d.RESEARCH_EXPENSE / 1e8).toFixed(2) : 0);
    const rdYoy = annual.map(d => d.RESEARCH_EXPENSE_YOY ? +d.RESEARCH_EXPENSE_YOY.toFixed(2) : null);

    chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['研发投入(亿)', '同比增速(%)'], top: 0, left: 'center', textStyle: { fontSize: 12 } },
        grid: { left: '3%', right: '4%', bottom: '3%', top: '18%', containLabel: true },
        xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
        yAxis: [
            { type: 'value', name: '金额(亿)', axisLabel: { fontSize: 11 } },
            { type: 'value', name: '增速(%)', axisLabel: { fontSize: 11, formatter: '{value}%' } }
        ],
        series: [
            { name: '研发投入(亿)', type: 'bar', barWidth: '30%', itemStyle: { color: '#4facfe', borderRadius: [4,4,0,0] }, data: rd },
            { name: '同比增速(%)', type: 'line', yAxisIndex: 1, symbol: 'circle', symbolSize: 8, itemStyle: { color: '#f093fb' }, data: rdYoy },
        ]
    });
    window.addEventListener('resize', () => chart.resize());
}

function renderExpenseRate(profit) {
    const dom = document.getElementById('chart-expense');
    if (finChartInstances['expense']) finChartInstances['expense'].dispose();
    const chart = echarts.init(dom); finChartInstances['expense'] = chart;

    const annual = profit.filter(d => d.REPORT_TYPE === '年报').slice(-5);
    if (annual.length === 0) { chart.setOption({ title: { text: '费用数据不可用', left: 'center', top: 'center', textStyle: { fontSize: 14, color: '#999' } } }); return; }
    const labels = annual.map(d => d.REPORT_DATE.slice(0, 4));

    const calcRate = (exp, rev) => { return exp && rev ? +((exp / rev) * 100).toFixed(2) : 0; };
    const rdRate = annual.map(d => calcRate(d.RESEARCH_EXPENSE, d.TOTAL_OPERATE_INCOME));
    const saleRate = annual.map(d => calcRate(d.SALE_EXPENSE, d.TOTAL_OPERATE_INCOME));
    const mgmtRate = annual.map(d => calcRate(d.MANAGE_EXPENSE, d.TOTAL_OPERATE_INCOME));

    chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['研发费用率', '销售费用率', '管理费用率'], top: 0, left: 'center', textStyle: { fontSize: 12 } },
        grid: { left: '3%', right: '4%', bottom: '3%', top: '18%', containLabel: true },
        xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
        yAxis: { type: 'value', name: '占比(%)', axisLabel: { fontSize: 11, formatter: '{value}%' }, min: 0 },
        series: [
            { name: '研发费用率', type: 'line', symbol: 'circle', symbolSize: 8, lineStyle: { color: '#4facfe', width: 2 }, itemStyle: { color: '#4facfe' }, data: rdRate },
            { name: '销售费用率', type: 'line', symbol: 'circle', symbolSize: 8, lineStyle: { color: '#f093fb', width: 2 }, itemStyle: { color: '#f093fb' }, data: saleRate },
            { name: '管理费用率', type: 'line', symbol: 'circle', symbolSize: 8, lineStyle: { color: '#ffa726', width: 2 }, itemStyle: { color: '#ffa726' }, data: mgmtRate },
        ]
    });
    window.addEventListener('resize', () => chart.resize());
}

function renderAssetExpansion(balance) {
    const dom = document.getElementById('chart-asset-expansion');
    if (finChartInstances['assetExp']) finChartInstances['assetExp'].dispose();
    const chart = echarts.init(dom); finChartInstances['assetExp'] = chart;

    const annual = balance.filter(d => d.REPORT_TYPE === '年报').slice(-5);
    if (annual.length === 0) { chart.setOption({ title: { text: '资产数据不可用', left: 'center', top: 'center', textStyle: { fontSize: 14, color: '#999' } } }); return; }
    const labels = annual.map(d => d.REPORT_DATE.slice(0, 4));
    const fixed = annual.map(d => d.FIXED_ASSET ? +(d.FIXED_ASSET / 1e8).toFixed(2) : 0);
    const inProgress = annual.map(d => d.CIP ? +(d.CIP / 1e8).toFixed(2) : 0);

    chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['固定资产(亿)', '在建工程(亿)'], top: 0, left: 'center', textStyle: { fontSize: 12 } },
        grid: { left: '3%', right: '4%', bottom: '3%', top: '18%', containLabel: true },
        xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
        yAxis: { type: 'value', name: '金额(亿)', axisLabel: { fontSize: 11 } },
        series: [
            { name: '固定资产(亿)', type: 'bar', barWidth: '28%', itemStyle: { color: '#4facfe', borderRadius: [4,4,0,0] }, data: fixed },
            { name: '在建工程(亿)', type: 'bar', barWidth: '28%', itemStyle: { color: '#ffa726', borderRadius: [4,4,0,0] }, data: inProgress },
        ]
    });
    window.addEventListener('resize', () => chart.resize());
}

function renderProfitabilityTrend(abstract) {
    const dom = document.getElementById('chart-profitability');
    if (finChartInstances['profitability']) finChartInstances['profitability'].dispose();
    const chart = echarts.init(dom); finChartInstances['profitability'] = chart;

    const annual = abstract.filter(d => d['报告期'] && d['报告期'].endsWith('12-31')).slice(-5);
    if (annual.length === 0) { chart.setOption({ title: { text: '盈利能力数据不可用', left: 'center', top: 'center', textStyle: { fontSize: 14, color: '#999' } } }); return; }
    const labels = annual.map(d => String(d['报告期']).slice(0, 4));
    const parsePct = (v) => { if (!v) return 0; const n = parseFloat(String(v).replace('%', '')); return isNaN(n) ? 0 : n; };
    const roe = annual.map(d => parsePct(d['净资产收益率']));
    const gross = annual.map(d => parsePct(d['销售毛利率']));
    const net = annual.map(d => parsePct(d['销售净利率']));

    chart.setOption({
        tooltip: { trigger: 'axis', formatter: function(p) { let s = `<b>${p[0].name}</b><br/>`; p.forEach(v => s += `${v.seriesName}: ${v.value}%<br/>`); return s; } },
        legend: { data: ['ROE', '毛利率', '净利率'], top: 0, left: 'center', textStyle: { fontSize: 12 } },
        grid: { left: '3%', right: '4%', bottom: '3%', top: '18%', containLabel: true },
        xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 11 } },
        yAxis: { type: 'value', name: '%', axisLabel: { fontSize: 11, formatter: '{value}%' } },
        series: [
            { name: 'ROE', type: 'line', symbol: 'circle', symbolSize: 8, lineStyle: { color: '#4facfe', width: 2 }, itemStyle: { color: '#4facfe' }, data: roe },
            { name: '毛利率', type: 'line', symbol: 'circle', symbolSize: 8, lineStyle: { color: '#43e97b', width: 2 }, itemStyle: { color: '#43e97b' }, data: gross },
            { name: '净利率', type: 'line', symbol: 'circle', symbolSize: 8, lineStyle: { color: '#f093fb', width: 2 }, itemStyle: { color: '#f093fb' }, data: net },
        ]
    });
    window.addEventListener('resize', () => chart.resize());
}

async function requestFinancialAI(latest, profit, balance, cash) {
    const healthSection = document.getElementById('aiHealthSection');
    const growthSection = document.getElementById('aiGrowthSection');
    const healthLoading = document.getElementById('aiHealthLoading');
    const growthLoading = document.getElementById('aiGrowthLoading');
    const healthContent = document.getElementById('aiHealthContent');
    const growthContent = document.getElementById('aiGrowthContent');
    healthSection.style.display = 'block';
    growthSection.style.display = 'block';
    healthLoading.style.display = 'block';
    growthLoading.style.display = 'block';
    healthContent.textContent = '';
    growthContent.textContent = '';

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
        const resp = await fetch('/api/analyze/financial', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const result = await resp.json();
        healthLoading.style.display = 'none';
        growthLoading.style.display = 'none';
        healthContent.textContent = result.health || '暂无解读';
        growthContent.textContent = result.growth || '暂无解读';
    } catch (e) {
        healthLoading.style.display = 'none';
        growthLoading.style.display = 'none';
        healthContent.textContent = 'AI 健康性分析请求失败: ' + e.message;
        growthContent.textContent = 'AI 增长分析请求失败: ' + e.message;
    }
}
