/**
 * API 服务层
 * 封装所有后端 API 调用
 */

const API_BASE = '';

// ============ 财报 API ============

/**
 * 获取主营构成数据
 */
export async function getZygc(symbol, refresh = false) {
    const params = new URLSearchParams({ symbol, refresh });
    const res = await fetch(`${API_BASE}/api/zygc?${params}`);
    if (!res.ok) throw new Error('获取主营构成失败');
    return res.json();
}

/**
 * AI 解读主营构成
 */
export async function analyzeZygc(symbol, latestData) {
    const res = await fetch(`${API_BASE}/api/analyze/zygc`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, latestData }),
    });
    if (!res.ok) throw new Error('AI 解读失败');
    return res.json();
}

/**
 * 获取财务数据
 */
export async function getFinancial(symbol, refresh = false) {
    const params = new URLSearchParams({ symbol, refresh });
    const res = await fetch(`${API_BASE}/api/financial?${params}`);
    if (!res.ok) throw new Error('获取财务数据失败');
    return res.json();
}

/**
 * AI 分析财务数据
 */
export async function analyzeFinancial(data) {
    const res = await fetch(`${API_BASE}/api/analyze/financial`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('财务分析失败');
    return res.json();
}

// ============ 舆论 API ============

/**
 * 获取涨停池数据
 */
export async function getZtPool(date = '') {
    const params = new URLSearchParams(date ? { date } : {});
    const res = await fetch(`${API_BASE}/api/zt/pool?${params}`);
    if (!res.ok) throw new Error('获取涨停池失败');
    return res.json();
}

/**
 * AI 分析涨停股风险
 */
export async function analyzeZtStock(data) {
    const res = await fetch(`${API_BASE}/api/zt/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('风险分析失败');
    return res.json();
}
