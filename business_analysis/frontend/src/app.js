/**
 * 前端入口
 * 初始化各模块组件
 */

import { initMacroCalendar } from './components/macro/MacroCalendar.js';
import { initFinanceModule } from './components/finance/FinanceAnalysis.js';
import { initSentimentModule } from './components/sentiment/SentimentAnalysis.js';

/**
 * 切换功能模块
 */
function switchFeature(feature) {
    // 更新导航状态
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.feature === feature);
    });
    
    // 切换内容面板 (HTML 中是 feature-{name})
    document.querySelectorAll('.feature-section').forEach(panel => {
        panel.classList.toggle('active', panel.id === `feature-${feature}`);
    });
    
    console.log('切换到:', feature);
}

// 挂载到全局作用域，供 onclick 调用
window.switchFeature = switchFeature;

/**
 * 初始化应用
 */
function initApp() {
    console.log('风控系统初始化...');
    
    // 初始化各模块
    initMacroCalendar();
    initFinanceModule();
    initSentimentModule();
    
    // 默认显示财报风险面板
    switchFeature('finance');
    
    // 设置默认日期为今天
    const dateInputs = document.querySelectorAll('input[type="date"]');
    const today = new Date().toISOString().split('T')[0];
    dateInputs.forEach(input => {
        if (!input.value) input.value = today;
    });
    
    console.log('风控系统初始化完成');
}

// DOM 加载完成后初始化
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}

export { initMacroCalendar, initFinanceModule, initSentimentModule };
