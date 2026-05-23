/**
 * API 服务层
 * 封装所有后端 API 调用
 */

const API_BASE = '';

// ============ 财报 API ============

/**
 * 获取主营构成数据（已转换为前端格式）
 */
export async function getZygc(symbol, refresh = false) {
    const params = new URLSearchParams({ symbol, refresh });
    const res = await fetch(`${API_BASE}/api/zygc?${params}`);
    if (!res.ok) throw new Error('获取主营构成失败');
    const raw = await res.json();
    return transformZygcData(raw);
}

/**
 * 将后端主营构成数据转换为前端渲染格式
 */
function transformZygcData(raw) {
    const records = raw.records || [];
    
    // 找最新报告期
    const dates = [...new Set(records.map(r => r['报告日期']))].sort().reverse();
    const latestDate = dates[0] || '';
    
    // 只取最新报告期的数据
    const latestRecords = records.filter(r => r['报告日期'] === latestDate);
    
    // 按分类类型分组
    const grouped = {};
    latestRecords.forEach(r => {
        const type = r['分类类型'] || '';
        if (!grouped[type]) grouped[type] = [];
        grouped[type].push({
            name: r['主营构成'] || '-',
            amount: r['主营收入'] ? (r['主营收入'] / 10000).toFixed(2) : 0,
            revenue: r['主营收入'] ? (r['主营收入'] / 10000).toFixed(2) : 0,
            ratio: r['收入比例'] || 0,
            cost: r['主营成本'] ? (r['主营成本'] / 10000).toFixed(2) : 0,
            profit: r['主营利润'] ? (r['主营利润'] / 10000).toFixed(2) : 0,
            profitRatio: r['利润比例'] || 0,
            grossMargin: r['毛利率'] || 0,
        });
    });
    
    return {
        symbol: raw.symbol,
        code: raw.code,
        name: raw.name,
        industry: grouped['按行业分类'] || [],
        product: grouped['按产品分类'] || [],
        region: grouped['按地区分类'] || [],
        latestDate,
        allDates: dates,
        zygc: grouped, // 传给 AI 分析用
    };
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
