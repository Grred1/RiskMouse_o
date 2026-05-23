/**
 * 前端入口
 * 初始化各模块组件
 */

import { initMacroCalendar } from './components/macro/MacroCalendar.js';
import { initFinanceModule } from './components/finance/FinanceAnalysis.js';
import { initSentimentModule } from './components/sentiment/SentimentAnalysis.js';

/**
 * 初始化应用
 */
function initApp() {
    console.log('风控系统初始化...');
    
    // 初始化各模块
    initMacroCalendar();
    initFinanceModule();
    initSentimentModule();
    
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
