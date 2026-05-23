/**
 * 全局函数库
 * 提供 HTML 中 onclick 等事件处理器需要的函数
 */

import * as api from './services/api.js';

// ==================== 财报分析 ====================

/**
 * 搜索股票
 */
async function search() {
    const symbol = document.getElementById('symbolInput')?.value?.trim();
    if (!symbol) {
        alert('请输入股票代码');
        return;
    }
    
    // 显示加载状态
    const loadingOverlay = document.getElementById('loadingOverlay');
    const loadingText = document.getElementById('loadingText');
    if (loadingOverlay) {
        loadingOverlay.style.display = 'flex';
        loadingText.textContent = '正在获取主营构成...';
    }
    const mainContent = document.getElementById('mainContent');
    const aiSection = document.getElementById('aiSection');
    const aiLoading = document.getElementById('aiLoading');
    const aiContent = document.getElementById('aiContent');
    
    try {
        const zygcData = await api.getZygc(symbol);
        
        if (loadingOverlay) loadingOverlay.style.display = 'none';
        if (mainContent) mainContent.style.display = 'block';
        
        // 更新主营表格
        renderZygcData(zygcData);
        
        if (aiSection) aiSection.style.display = 'block';
        if (aiLoading) {
            aiLoading.style.display = 'block';
            aiContent.innerHTML = '';
        }
        
        // 调用 AI 分析
        const aiAnalysis = await api.analyzeZygc(symbol, zygcData.zygc);
        if (aiLoading) aiLoading.style.display = 'none';
        if (aiContent) aiContent.innerHTML = aiAnalysis.analysis || aiAnalysis.result || '暂无分析结果';
        
    } catch (error) {
        console.error('搜索失败:', error);
        if (loadingOverlay) loadingOverlay.style.display = 'none';
        const errorMsg = document.getElementById('errorMsg');
        if (errorMsg) errorMsg.textContent = `搜索失败: ${error.message}`;
    }
}

/**
 * 渲染主营构成数据
 */
function renderZygcData(zygcData) {
    // 更新标题
    const titleEl = document.getElementById('stockTitle');
    if (titleEl) titleEl.textContent = `${zygcData.name || ''}(${zygcData.code || ''}) 主营构成`;
    
    // 更新报告期选择器
    const reportSelect = document.getElementById('reportSelect');
    if (reportSelect && zygcData.allDates) {
        reportSelect.innerHTML = zygcData.allDates.map(d => 
            `<option value="${d}" ${d === zygcData.latestDate ? 'selected' : ''}>${d}</option>`
        ).join('');
    }
    
    // 按行业分类
    const industryData = zygcData.industry || [];
    renderTable('table-industry', industryData, '按行业分类');
    renderChart('chart-industry', industryData, '行业占比');
    
    // 按产品分类
    const productData = zygcData.product || [];
    renderTable('table-product', productData, '按产品分类');
    renderChart('chart-product', productData, '产品占比');
    
    // 按地区分类
    const regionData = zygcData.region || [];
    renderTable('table-region', regionData, '按地区分类');
    renderChart('chart-region', regionData, '地区占比');
}

function renderTable(tableId, data, title) {
    const table = document.getElementById(tableId);
    if (!table) return;
    
    if (!data || data.length === 0) {
        table.innerHTML = `<tr><td colspan="5" style="text-align:center;color:#666;">暂无${title}数据</td></tr>`;
        return;
    }
    
    let html = `<thead><tr>
        <th>分类</th><th>收入(万)</th><th>收入占比</th><th>毛利率</th><th>利润占比</th>
    </tr></thead><tbody>`;
    data.forEach(item => {
        html += `<tr>
            <td>${item.name || '-'}</td>
            <td>${formatNumber(item.revenue)}</td>
            <td>${item.ratio}%</td>
            <td>${item.grossMargin}%</td>
            <td>${item.profitRatio}%</td>
        </tr>`;
    });
    html += '</tbody>';
    table.innerHTML = html;
}

function formatNumber(num) {
    if (!num && num !== 0) return '-';
    return parseFloat(num).toLocaleString('zh-CN', { maximumFractionDigits: 2 });
}

function renderChart(chartId, data, title) {
    const chartDom = document.getElementById(chartId);
    if (!chartDom || !data || data.length === 0) return;
    
    const chart = echarts.init(chartDom);
    chart.setOption({
        title: { text: title, left: 'center', textStyle: { fontSize: 14 } },
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        series: [{
            type: 'pie',
            radius: ['40%', '70%'],
            data: data.map(item => ({ name: item.name || '-', value: parseFloat(item.amount || item.revenue || 0) })),
            label: { show: true, formatter: '{b}' }
        }]
    });
}

/**
 * 快捷搜索
 */
function quickSearch(symbol) {
    const input = document.getElementById('symbolInput');
    if (input) {
        input.value = symbol;
        search();
    }
}

/**
 * 更新数据
 */
async function refreshData() {
    await search();
}

/**
 * 报告期变化
 */
function onReportChange() {
    const select = document.getElementById('reportSelect');
    if (select) {
        console.log('报告期切换:', select.value);
    }
}

// ==================== 标签页切换 ====================

/**
 * 切换标签页
 */
function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(t => {
        t.classList.toggle('active', t.dataset.tab === tab);
    });
    
    document.querySelectorAll('.tab-content').forEach(c => {
        c.classList.toggle('active', c.dataset.tab === tab);
    });
}

/**
 * 切换子标签页
 */
function switchSubTab(tab) {
    document.querySelectorAll('.sub-tab').forEach(t => {
        t.classList.toggle('active', t.textContent.includes(tab === 'health' ? '风险' : '增长'));
    });
}

// ==================== 舆论分析 ====================

/**
 * 获取涨停池
 */
async function fetchZTPool() {
    const btn = document.getElementById('ztFetchBtn');
    const summary = document.getElementById('ztSummary');
    const tableBody = document.getElementById('ztTableBody');
    const errorDiv = document.getElementById('ztError');
    
    if (btn) btn.disabled = true;
    if (errorDiv) errorDiv.textContent = '';
    
    try {
        const data = await api.getZTPool();
        
        // 更新统计
        if (summary) {
            summary.textContent = `共 ${data.stocks?.length || 0} 只涨停`;
        }
        
        // 更新表格
        if (tableBody) {
            if (data.stocks && data.stocks.length > 0) {
                let html = '';
                data.stocks.forEach((stock, i) => {
                    html += `<tr style="cursor:pointer;" onclick="analyzeStock('${stock.code}', '${stock.name}', '${stock.industry || ''}')">
                        <td style="text-align:center;">${i + 1}</td>
                        <td>${stock.code}</td>
                        <td>${stock.name}</td>
                        <td style="text-align:center;color:#e74c3c;font-weight:bold;">${stock.board}</td>
                        <td style="text-align:right;color:#2ecc71;">${stock.price || '-'}</td>
                        <td>${stock.industry || '-'}</td>
                        <td style="text-align:right;">${stock.seal || '-'}</td>
                    </tr>`;
                });
                tableBody.innerHTML = html;
            } else {
                tableBody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#999;padding:30px;">暂无涨停数据</td></tr>';
            }
        }
    } catch (error) {
        console.error('获取涨停池失败:', error);
        if (errorDiv) errorDiv.textContent = `获取失败: ${error.message}`;
        if (tableBody) tableBody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#e74c3c;padding:30px;">加载失败</td></tr>';
    } finally {
        if (btn) btn.disabled = false;
    }
}

/**
 * 分析单只股票
 */
async function analyzeStock(code, name, industry) {
    const detailPanel = document.getElementById('ztDetailPanel');
    const detailHeader = document.getElementById('ztDetailHeader');
    const detailLoading = document.getElementById('ztDetailLoading');
    const analysisArea = document.getElementById('ztAnalysisArea');
    
    if (detailPanel) detailPanel.style.display = 'block';
    if (detailHeader) detailHeader.textContent = `${code} ${name}`;
    if (detailLoading) detailLoading.style.display = 'flex';
    if (analysisArea) analysisArea.textContent = '';
    
    try {
        const analysis = await api.analyzeZT(code, name, industry);
        if (detailLoading) detailLoading.style.display = 'none';
        if (analysisArea) {
            analysisArea.textContent = analysis.analysis || analysis.result || '暂无分析结果';
        }
    } catch (error) {
        console.error('分析失败:', error);
        if (detailLoading) detailLoading.style.display = 'none';
        if (analysisArea) analysisArea.textContent = `分析失败: ${error.message}`;
    }
}

// 挂载到全局
window.search = search;
window.quickSearch = quickSearch;
window.refreshData = refreshData;
window.onReportChange = onReportChange;
window.switchTab = switchTab;
window.switchSubTab = switchSubTab;
window.fetchZTPool = fetchZTPool;
window.analyzeStock = analyzeStock;
