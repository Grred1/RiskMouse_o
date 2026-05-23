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
    const symbol = document.getElementById('stock-symbol')?.value?.trim();
    if (!symbol) {
        alert('请输入股票代码');
        return;
    }
    
    const content = document.getElementById('finance-content');
    const aiResult = document.getElementById('finance-ai-result');
    
    if (content) content.innerHTML = '<div class="loading">加载中...</div>';
    if (aiResult) {
        aiResult.style.display = 'block';
        aiResult.innerHTML = '<div class="loading"><span class="ai-label">Coze AI 分析中...</span></div>';
    }
    
    try {
        const zygcData = await api.getZygc(symbol);
        
        if (content) {
            let html = '<h4>主营构成</h4>';
            if (zygcData.zygc && zygcData.zygc.length > 0) {
                html += '<table class="zygc-table"><thead><tr><th>业务</th><th>收入(万)</th><th>占比</th></tr></thead><tbody>';
                zygcData.zygc.forEach(item => {
                    html += `<tr><td>${item.business || '-'}</td><td>${item.revenue || '-'}</td><td>${item.ratio || '-'}</td></tr>`;
                });
                html += '</tbody></table>';
            } else {
                html += '<p>暂无数据</p>';
            }
            html += `<p class="data-source">数据来源: ${zygcData.source || '网络'}</p>`;
            content.innerHTML = html;
        }
        
        if (aiResult) {
            const aiAnalysis = await api.analyzeZygc(symbol, zygcData.zygc);
            aiResult.innerHTML = `<div class="ai-result"><span class="ai-label">Coze AI 分析:</span><div class="ai-content">${aiAnalysis.analysis || aiAnalysis.result || '暂无分析结果'}</div></div>`;
        }
    } catch (error) {
        console.error('搜索失败:', error);
        if (content) content.innerHTML = `<p class="error">搜索失败: ${error.message}</p>`;
        if (aiResult) aiResult.innerHTML = `<p class="error">AI 分析失败</p>`;
    }
}

/**
 * 快捷搜索
 */
function quickSearch(symbol) {
    const input = document.getElementById('stock-symbol');
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
    const content = document.getElementById('zt-content');
    
    if (btn) btn.disabled = true;
    if (content) content.innerHTML = '<div class="loading">加载中...</div>';
    
    try {
        const data = await api.getZTPool();
        if (content) {
            let html = '<h4>二板以上涨停股票</h4>';
            if (data.stocks && data.stocks.length > 0) {
                html += '<table class="zt-table"><thead><tr><th>代码</th><th>名称</th><th>连板</th><th>行业</th><th>分析</th></tr></thead><tbody>';
                data.stocks.forEach(stock => {
                    html += `<tr>
                        <td>${stock.code}</td>
                        <td>${stock.name}</td>
                        <td>${stock.board}</td>
                        <td>${stock.industry || '-'}</td>
                        <td><button onclick="analyzeStock('${stock.code}', '${stock.name}', '${stock.industry || ''}')">分析</button></td>
                    </tr>`;
                });
                html += '</tbody></table>';
            } else {
                html += '<p>暂无数据</p>';
            }
            html += `<p class="data-source">数据来源: ${data.source || '财联社'}</p>`;
            content.innerHTML = html;
        }
    } catch (error) {
        console.error('获取涨停池失败:', error);
        if (content) content.innerHTML = `<p class="error">获取失败: ${error.message}</p>`;
    } finally {
        if (btn) btn.disabled = false;
    }
}

/**
 * 分析单只股票
 */
async function analyzeStock(code, name, industry) {
    const aiResult = document.getElementById('zt-ai-result');
    if (aiResult) {
        aiResult.style.display = 'block';
        aiResult.innerHTML = '<div class="loading"><span class="ai-label">Coze AI 风险分析中...</span></div>';
    }
    
    try {
        const analysis = await api.analyzeZT(code, name, industry);
        if (aiResult) {
            aiResult.innerHTML = `<div class="ai-result"><span class="ai-label">Coze AI 风险分析:</span><div class="ai-content">${analysis.analysis || analysis.result || '暂无分析结果'}</div></div>`;
        }
    } catch (error) {
        console.error('分析失败:', error);
        if (aiResult) aiResult.innerHTML = `<p class="error">分析失败: ${error.message}</p>`;
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
