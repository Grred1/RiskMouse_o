/**
 * 舆论风险分析组件
 */

import * as api from '../../services/api.js';

/**
 * 初始化舆论分析
 */
export function initSentimentModule() {
    const analyzeBtn = document.getElementById('analyze-zt-btn');
    const dateInput = document.getElementById('zt-date');
    
    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', handleAnalyzeZt);
    }
}

/**
 * 处理涨停股风险分析
 */
async function handleAnalyzeZt() {
    const dateInput = document.getElementById('zt-date');
    const date = dateInput?.value || '';
    const content = document.getElementById('zt-content');
    const aiResult = document.getElementById('zt-ai-result');
    
    if (content) content.innerHTML = '<div class="loading">加载中...</div>';
    if (aiResult) {
        aiResult.style.display = 'block';
        aiResult.innerHTML = '<div class="loading"><span class="ai-label">Coze AI 分析中...</span></div>';
    }

    try {
        // 获取涨停池数据
        const ztData = await api.getZtPool(date);
        
        if (content) {
            let html = '<h4>涨停股票池</h4>';
            if (ztData.data && ztData.data.length > 0) {
                html += '<table class="zt-table"><thead><tr><th>股票名称</th><th>代码</th><th>连板数</th><th>行业</th></tr></thead><tbody>';
                ztData.data.slice(0, 20).forEach(item => {
                    html += `<tr>
                        <td class="stock-name">${item.name || '-'}</td>
                        <td>${item.code || '-'}</td>
                        <td><span class="board-tag">${item.board || 1}板</span></td>
                        <td>${item.industry || '-'}</td>
                    </tr>`;
                });
                html += '</tbody></table>';
                html += `<p class="data-count">共 ${ztData.data.length} 只涨停股</p>`;
            } else {
                html += '<p>暂无涨停数据</p>';
            }
            content.innerHTML = html;
        }

        // AI 分析第一只涨停股
        if (aiResult && ztData.data && ztData.data.length > 0) {
            const stock = ztData.data[0];
            const aiAnalysis = await api.analyzeZtStock({
                name: stock.name,
                code: stock.code,
                board: stock.board || 1,
                industry: stock.industry || '未知',
                zygc: stock.zygc || [],
                logic: stock.logic || '',
            });
            aiResult.innerHTML = `<div class="ai-result">
                <span class="ai-label">Coze AI 风险分析 (${stock.name}):</span>
                <div class="ai-content">${aiAnalysis.analysis || aiAnalysis.result || '暂无分析结果'}</div>
            </div>`;
        }
    } catch (error) {
        console.error('分析失败:', error);
        if (content) content.innerHTML = `<p class="error">分析失败: ${error.message}</p>`;
        if (aiResult) aiResult.innerHTML = `<p class="error">AI 分析失败</p>`;
    }
}

// 导出给全局使用
window.initSentimentModule = initSentimentModule;
