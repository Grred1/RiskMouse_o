/**
 * 财报风险分析组件
 */

import * as api from '../../services/api.js';

/**
 * 初始化财报分析
 */
export function initFinanceModule() {
    const symbolInput = document.getElementById('stock-symbol');
    const analyzeBtn = document.getElementById('analyze-finance-btn');
    
    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', handleAnalyzeFinance);
    }
}

/**
 * 处理财报分析
 */
async function handleAnalyzeFinance() {
    const symbolInput = document.getElementById('stock-symbol');
    const symbol = symbolInput?.value?.trim();
    
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
        // 获取主营构成数据
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

        // AI 分析
        if (aiResult) {
            const aiAnalysis = await api.analyzeZygc(symbol, zygcData.zygc);
            aiResult.innerHTML = `<div class="ai-result"><span class="ai-label">Coze AI 分析:</span><div class="ai-content">${aiAnalysis.analysis || aiAnalysis.result || '暂无分析结果'}</div></div>`;
        }
    } catch (error) {
        console.error('分析失败:', error);
        if (content) content.innerHTML = `<p class="error">分析失败: ${error.message}</p>`;
        if (aiResult) aiResult.innerHTML = `<p class="error">AI 分析失败</p>`;
    }
}

// 导出给全局使用
window.initFinanceModule = initFinanceModule;
