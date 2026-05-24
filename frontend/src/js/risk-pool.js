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

function updateFilters() {
    const industrySelect = document.getElementById('industryFilter');
    const industries = [...new Set(riskPoolData.map(s => s.industry).filter(Boolean))];
    industrySelect.innerHTML = '<option value="all">全部行业</option>';
    industries.forEach(ind => {
        industrySelect.innerHTML += `<option value="${ind}">${ind}</option>`;
    });
    document.getElementById('ztFilters').style.display = 'flex';
}

function filterRiskPool() {
    currentFilter = document.getElementById('sourceFilter').value;
    renderRiskPool();
}

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

async function showRiskDetail(code, name, source, industry) {
    currentRiskStock = { code, name, source, industry };

    const panel = document.getElementById('ztDetailPanel');
    const header = document.getElementById('ztDetailHeader');
    const loading = document.getElementById('ztDetailLoading');
    const content = document.getElementById('ztDetailContent');
    const logicArea = document.getElementById('ztLogicArea');
    const analysisArea = document.getElementById('ztAnalysisArea');

    if (!header || !loading || !content || !logicArea || !analysisArea) return;

    header.textContent = `${name} (${code})`;

    loading.style.display = 'flex';
    content.style.display = 'none';

    try {
        const pureCode = code.replace(/^(SH|SZ|BJ)/, '');

        const stockInfo = riskPoolData.find(s => s.code === code);
        const board = stockInfo ? stockInfo.board : 0;

        const [analysisRes, gubaRes] = await Promise.all([
            fetch(`/api/risk/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code: code,
                    name: name,
                    source: source,
                    industry: industry,
                    board: board
                })
            }),
            fetch(`/api/risk/guba?code=${pureCode}`)
        ]);

        const analysisData = await analysisRes.json();
        const gubaData = await gubaRes.json();

        const starRow = document.getElementById('ztStarRow');
        if (starRow) {
            if (analysisData.scores && analysisData.scores.length > 0) {
                starRow.innerHTML = renderStarBadges(analysisData.scores);
                starRow.style.display = 'flex';
            } else {
                starRow.style.display = 'none';
            }
        }

        if (analysisData.error) {
            analysisArea.innerHTML = `<div class="risk-error">风险分析失败: ${analysisData.error}</div>`;
        } else if (analysisData.scores && analysisData.scores.length > 0) {
            analysisArea.innerHTML = renderRiskScores(analysisData);
        } else if (analysisData.risk_analysis) {
            analysisArea.innerHTML = renderFallbackText(analysisData.risk_analysis);
        } else if (analysisData.analysis) {
            analysisArea.innerHTML = `<div class="risk-fallback-text">${analysisData.analysis}</div>`;
        } else {
            analysisArea.innerHTML = '<div class="risk-error">暂无风险分析数据</div>';
        }

        renderGubaData(logicArea, gubaData);

    } catch (err) {
        console.error('获取详情失败:', err);
        analysisArea.textContent = '获取详情失败: ' + err.message;
    } finally {
        loading.style.display = 'none';
        content.style.display = 'block';
    }

    renderRiskPool();
}
