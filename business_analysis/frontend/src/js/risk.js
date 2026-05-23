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
        const pureCode = code.replace(/^(SH|SZ|BJ)/, '');
        // 并行获取主营构成、AI 分析和股吧数据
        const [zygcRes, analysisRes, gubaRes] = await Promise.all([
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
            }),
            fetch(`/api/risk/guba?code=${pureCode}`)
        ]);

        const zygcData = await zygcRes.json();
        const analysisData = await analysisRes.json();
        const gubaData = await gubaRes.json();

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
        } else if (analysisData.risk_analysis) {
            analysisArea.textContent = analysisData.risk_analysis;
        } else if (analysisData.analysis) {
            analysisArea.textContent = analysisData.analysis;
        } else {
            analysisArea.textContent = '暂无风险分析数据';
        }

        // 显示股吧关注点（真实数据）
        renderGubaData(logicArea, gubaData);

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

function renderGubaData(container, data) {
    if (!data || data.error) {
        container.textContent = '暂无股吧数据';
        return;
    }

    const keywords = data.keywords || [];
    const postTitles = data.post_titles || [];
    const stats = data.stats || {};
    const analysis = data.analysis || '';
    const rank = data.rank || {};

    const totalPoints = stats.total_data_points || 0;

    let html = '';

    // 数据统计可视化
    html += `<div style="margin-bottom:12px;padding:12px;background:#f0f4ff;border-radius:8px;border:1px solid #d0e0ff;">`;
    html += `<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
        <span style="font-size:14px;font-weight:600;color:#2952a3;">📊 股吧数据分析</span>
        <span style="font-size:12px;color:#888;">共挖掘 <strong style="color:#c0392b;font-size:16px;">${totalPoints}</strong> 条数据</span>
    </div>`;
    html += `<div style="display:flex;gap:16px;flex-wrap:wrap;">`;
    if (stats.keyword_count > 0) {
        html += `<div style="text-align:center;min-width:60px;">
            <div style="font-size:20px;font-weight:700;color:#2952a3;">${stats.keyword_count}</div>
            <div style="font-size:11px;color:#888;">热门关键词</div>
        </div>`;
    }
    if (stats.post_count > 0) {
        html += `<div style="text-align:center;min-width:60px;">
            <div style="font-size:20px;font-weight:700;color:#e67e22;">${stats.post_count}</div>
            <div style="font-size:11px;color:#888;">帖子标题</div>
        </div>`;
    }
    if (stats.relate_count > 0) {
        html += `<div style="text-align:center;min-width:60px;">
            <div style="font-size:20px;font-weight:700;color:#27ae60;">${stats.relate_count}</div>
            <div style="font-size:11px;color:#888;">相关股票</div>
        </div>`;
    }
    if (stats.rank_days > 0) {
        html += `<div style="text-align:center;min-width:60px;">
            <div style="font-size:20px;font-weight:700;color:#8e44ad;">${stats.rank_days}</div>
            <div style="font-size:11px;color:#888;">排名天数</div>
        </div>`;
    }
    html += `</div></div>`;

    // 人气排名
    if (rank.rank) {
        html += `<div style="margin-bottom:8px;font-size:13px;color:#555;">
            人气排名: <strong>第${rank.rank}名</strong>
            ${rank.rankChange ? `（较昨日 ${rank.rankChange > 0 ? '↑' : '↓'} ${rank.rankChange}）` : ''}
            共 ${rank.marketAllCount || '--'} 只股票参评
        </div>`;
    }

    // 热门关键词
    if (keywords.length > 0) {
        html += `<div style="margin-bottom:8px;">
            <span style="font-size:13px;font-weight:600;color:#555;">热门概念：</span>`;
        const maxHot = Math.max(...keywords.map(k => k.hotness), 1);
        keywords.forEach(kw => {
            const intensity = Math.round((kw.hotness / maxHot) * 5);
            const colors = ['#e8ecf1','#d5e5ff','#a8c8ff','#7aaaff','#4d8cff','#2952a3'];
            html += `<span style="display:inline-block;padding:2px 10px;margin:2px 4px;border-radius:12px;
                font-size:12px;background:${colors[intensity] || colors[0]};color:${intensity > 3 ? '#fff' : '#555'};
                white-space:nowrap;">${kw.keyword} ${kw.hotness}</span>`;
        });
        html += `</div>`;
    }

    // 帖子标题（可展开）
    if (postTitles.length > 0) {
        html += `<details style="margin-bottom:8px;font-size:12px;">
            <summary style="cursor:pointer;color:#555;font-weight:600;">📝 最新股吧热帖（${postTitles.length}条）</summary>
            <div style="margin-top:4px;max-height:120px;overflow-y:auto;background:#f9f9f9;padding:8px;border-radius:6px;">`;
        postTitles.forEach(t => {
            html += `<div style="padding:3px 0;border-bottom:1px solid #eee;color:#444;">${t}</div>`;
        });
        html += `</div></details>`;
    }

    // AI 分析的市场逻辑
    if (analysis) {
        html += `<div style="margin-top:8px;padding:10px;background:#fef9e7;border-radius:8px;border:1px solid #fdebd0;">
            <div style="font-size:13px;font-weight:600;color:#e67e22;margin-bottom:4px;">🤖 AI 股吧舆情分析</div>
            <div style="font-size:13px;line-height:1.7;color:#444;white-space:pre-wrap;">${analysis}</div>
        </div>`;
    }

    container.innerHTML = html;
}

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    // 设置默认日期为今天
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('ztDateInput').value = today;

    // 启动时自动加载
    fetchRiskPool(true);
});
