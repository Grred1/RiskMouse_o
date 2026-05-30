async function search() {
    let input = document.getElementById('symbolInput').value.trim().toUpperCase();
    if (!input) { showError('请输入股票代码或名称'); return; }
    hideError();

    // 如果不是标准的股票代码格式（6位数字或带 SH/SZ/BJ 前缀），尝试名称搜索
    if (!/^[SHBJSZ]{0,4}\d{6}$/.test(input)) {
        document.getElementById('loadingOverlay').style.display = 'block';
        document.getElementById('loadingText').textContent = '正在搜索股票...';
        try {
            const resp = await fetch(`/api/stock/search?q=${encodeURIComponent(input)}&limit=5`);
            const data = await resp.json();
            const results = data.results || [];
            if (results.length === 0) {
                showError(`未找到匹配「${input}」的股票`);
                document.getElementById('loadingOverlay').style.display = 'none';
                return;
            }
            if (results.length > 1) {
                // 多只匹配，让用户选
                const names = results.map(r => `${r.name}(${r.code})`).join('、');
                showError(`找到多只匹配：${names}，请输入精确代码`);
                document.getElementById('loadingOverlay').style.display = 'none';
                return;
            }
            input = results[0].code;
            document.getElementById('symbolInput').value = input;
        } catch (e) {
            showError('搜索失败: ' + e.message);
            document.getElementById('loadingOverlay').style.display = 'none';
            return;
        }
    }

    growthChartsRendered = false;
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

    const availableCategories = new Set(allData.records.map(r => r.分类类型));
    document.querySelectorAll('.zygc-nav-item').forEach(el => {
        const catKey = el.dataset.tab;
        const catName = REVERSE_MAP[catKey];
        el.style.display = availableCategories.has(catName) ? '' : 'none';
    });

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
