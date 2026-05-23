// 风险挖掘模块
// 数据来源：涨停板 + 龙虎榜，统一称为"热门关注"

let riskPoolData = [];
let currentRiskStock = null;
let currentFilter = 'all';

// 获取热门关注池
async function fetchRiskPool(showFirst = true) {
    const dateInput = document.getElementById('ztDateInput');
    const date = dateInput.value.replace(/-/g, '');
    const errorDiv = document.getElementById('ztError');
    const tbody = document.getElementById('ztTableBody');

    errorDiv.textContent = '';
    tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:#999;padding:30px;">加载中...</td></tr>';

    try {
        const response = await fetch(`/api/risk/pool?date=${date}`);
        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        riskPoolData = data.stocks || [];
        updateFilters();
        renderRiskPool();

        const summary = document.getElementById('ztSummary');
        summary.textContent = `· 热门关注 ${riskPoolData.length} 只`;

        // 自动展示第一个股票详情
        if (showFirst && riskPoolData.length > 0) {
            const first = riskPoolData[0];
            showRiskDetail(first.code, first.name, first.source, first.industry || '');
        }

    } catch (err) {
        errorDiv.textContent = '获取失败: ' + err.message;
        tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:#999;padding:30px;">获取失败，请重试</td></tr>';
        console.error('获取热门关注失败:', err);
    }
}

// 更新筛选器
function updateFilters() {
    const industrySelect = document.getElementById('industryFilter');
    const industries = [...new Set(riskPoolData.map(s => s.industry).filter(Boolean))];
    industrySelect.innerHTML = '<option value="all">全部行业</option>';
    industries.forEach(ind => {
        industrySelect.innerHTML += `<option value="${ind}">${ind}</option>`;
    });
    document.getElementById('ztFilters').style.display = 'flex';
}

// 筛选热门关注池
function filterRiskPool() {
    currentFilter = document.getElementById('sourceFilter').value;
    renderRiskPool();
}

// 渲染热门关注列表
function renderRiskPool() {
    const tbody = document.getElementById('ztTableBody');
    const industryFilter = document.getElementById('industryFilter').value;

    let filtered = riskPoolData;

    if (currentFilter !== 'all') {
        filtered = filtered.filter(s => s.source === currentFilter);
    }
    if (industryFilter !== 'all') {
        filtered = filtered.filter(s => s.industry === industryFilter);
    }

    if (filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:#999;padding:30px;">暂无数据</td></tr>';
        return;
    }

    let html = '';
    filtered.forEach((stock) => {
        const sourceTag = stock.source === '涨停'
            ? '<span class="zt-tag zt-tag-purple">🟣</span>'
            : '<span class="zt-tag zt-tag-orange">🔥</span>';

        const isActive = currentRiskStock && currentRiskStock.code === stock.code;

        html += `
            <tr class="zt-row ${isActive ? 'active' : ''}" onclick="showRiskDetail('${stock.code}', '${stock.name}', '${stock.source}', '${stock.industry || ''}')">
                <td style="text-align:left;">${stock.code}</td>
                <td style="text-align:left;font-weight:600;">${stock.name}</td>
                <td style="text-align:center;">${sourceTag}</td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
}

// 显示风险详情
async function showRiskDetail(code, name, source, industry) {
    currentRiskStock = { code, name, source, industry };

    const panel = document.getElementById('ztDetailPanel');
    const header = document.getElementById('ztDetailHeader');
    const loading = document.getElementById('ztDetailLoading');
    const content = document.getElementById('ztDetailContent');
    const logicArea = document.getElementById('ztLogicArea');
    const zygcArea = document.getElementById('ztZygcArea');
    const analysisArea = document.getElementById('ztAnalysisArea');

    // 更新头部
    header.textContent = `${name} (${code})`;

    // 显示加载中
    loading.style.display = 'flex';
    content.style.display = 'none';

    try {
        // 并行获取主营构成和 AI 分析
        const [zygcRes, analysisRes] = await Promise.all([
            fetch(`/api/zygc?symbol=${code}`),
            fetch(`/api/risk/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code: code,
                    name: name,
                    source: source,
                    industry: industry
                })
            })
        ]);

        const zygcData = await zygcRes.json();
        const analysisData = await analysisRes.json();

        // 显示主营构成
        if (zygcData.records && zygcData.records.length > 0) {
            const latest = zygcData.records[0];
            const records = Object.entries(latest)
                .filter(([k]) => k.startsWith('按'))
                .map(([k, v]) => `${k}: ${v}`)
                .join('\n');
            zygcArea.textContent = records || '暂无主营数据';
        } else {
            zygcArea.textContent = '暂无主营数据';
        }

        // 显示 AI 风险分析
        if (analysisData.error) {
            analysisArea.textContent = '风险分析失败: ' + analysisData.error;
        } else if (analysisData.analysis) {
            analysisArea.textContent = analysisData.analysis;
        } else {
            analysisArea.textContent = '暂无风险分析数据';
        }

        // 显示关注点（来源相关）
        logicArea.textContent = getSourceInfo(code, name, source);

    } catch (err) {
        console.error('获取详情失败:', err);
        analysisArea.textContent = '获取详情失败: ' + err.message;
    } finally {
        loading.style.display = 'none';
        content.style.display = 'block';
    }

    // 高亮当前行
    renderRiskPool();
}

// 获取来源相关信息
function getSourceInfo(code, name, source) {
    if (source === '涨停') {
        return `${name}（${code}）今日涨停，市场关注度较高。\n\n请关注：\n- 涨停原因及持续性\n- 封板资金情况\n- 同行业个股表现`;
    } else if (source === '龙虎榜') {
        return `${name}（${code}）今日上榜龙虎榜。\n\n请关注：\n- 机构席位买卖情况\n- 营业部游资动向\n- 资金净流入流出情况`;
    }
    return `${name}（${code}）为当前市场热门关注标的。\n\n请关注相关风险因素。`;
}

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    // 设置默认日期为今天
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('ztDateInput').value = today;

    // 启动时自动加载
    fetchRiskPool(true);
});
