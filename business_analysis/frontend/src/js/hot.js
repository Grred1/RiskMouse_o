// ============================================================
// 风险挖掘模块 - 热门标的 + 人气榜 + AI 风险分析
// ============================================================

// API 基础路径
const API_BASE = '/api';

// 当前数据
let currentHotStocks = [];
let currentDetailCode = null;

// -----------------------------------------------
// 1. 获取热门标的（涨停板 + 人气榜）
// -----------------------------------------------
async function fetchHotStocks() {
    const dateInput = document.getElementById('hotDateInput');
    const date = dateInput ? dateInput.value.replace(/-/g, '') : '';

    showLoading('◈ 获取热门标的中...');

    try {
        const response = await fetch(`${API_BASE}/hot/pool?date=${date}`);
        if (!response.ok) throw new Error('获取数据失败');

        const data = await response.json();
        currentHotStocks = data.stocks || [];

        // 更新统计
        updateHotStats(data.stats);

        // 渲染表格
        renderHotTable(currentHotStocks);

        hideLoading();
    } catch (error) {
        console.error('获取热门标的失败:', error);
        showError('获取热门标的失败，请重试');
        hideLoading();
    }
}

// 更新统计
function updateHotStats(stats) {
    const totalEl = document.getElementById('hotTotalCount');
    const ztEl = document.getElementById('hotZtCount');
    const highEl = document.getElementById('hotHighRiskCount');
    const medEl = document.getElementById('hotMediumRiskCount');

    if (totalEl) totalEl.textContent = stats?.total || currentHotStocks.length;
    if (ztEl) ztEl.textContent = stats?.ztCount || '-';
    if (highEl) highEl.textContent = stats?.highRisk || '-';
    if (medEl) medEl.textContent = stats?.mediumRisk || '-';
}

// 渲染表格
function renderHotTable(stocks) {
    const tbody = document.getElementById('hotTableBody');
    if (!tbody) return;

    if (!stocks || stocks.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:40px;color:var(--cyber-text-dim);">暂无数据</td></tr>`;
        return;
    }

    let html = '';
    stocks.forEach((stock, index) => {
        // 风险等级样式
        const riskClass = stock.riskLevel === 'high' ? 'danger' :
                          stock.riskLevel === 'medium' ? 'warning' : 'success';
        const riskText = stock.riskLevel === 'high' ? '高风险' :
                         stock.riskLevel === 'medium' ? '中风险' : '低风险';

        // 来源样式
        let sourceHtml = '';
        if (stock.source === '涨停板') {
            sourceHtml = '<span class="tag-secondary">涨停</span>';
        } else if (stock.source === '人气榜') {
            sourceHtml = '<span class="tag-primary">人气</span>';
        } else {
            sourceHtml = '<span class="tag-secondary">涨停</span><span class="tag-primary" style="margin-left:4px;">人气</span>';
        }

        // 热度条
        const heatPercent = Math.min((stock.heatScore || 0) / 10 * 100, 100);
        const heatBar = `<div style="width:80px;height:6px;background:var(--cyber-border);border-radius:3px;overflow:hidden;"><div style="width:${heatPercent}%;height:100%;background:linear-gradient(90deg,var(--cyber-primary),var(--cyber-secondary));border-radius:3px;"></div></div>`;

        html += `
            <tr class="stock-row" onclick="showHotDetail('${stock.code}')">
                <td style="text-align:center;color:var(--cyber-text-dim);font-size:12px;">${index + 1}</td>
                <td style="font-family:monospace;color:var(--cyber-primary);">${stock.code}</td>
                <td style="font-weight:600;color:var(--cyber-text);">${stock.name}</td>
                <td style="text-align:center;">${sourceHtml}</td>
                <td style="text-align:center;">
                    ${heatBar}
                    <span style="font-size:11px;color:var(--cyber-text-dim);margin-top:2px;display:block;">${stock.heatScore || 0}</span>
                </td>
                <td style="color:var(--cyber-text-dim);font-size:12px;">${stock.industry || '-'}</td>
                <td style="text-align:center;">
                    <span class="tag-${riskClass}">${riskText}</span>
                </td>
                <td style="text-align:center;">
                    <button class="cyber-btn-small" onclick="event.stopPropagation();showHotDetail('${stock.code}')">分析</button>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
}

// -----------------------------------------------
// 2. 显示详情
// -----------------------------------------------
async function showHotDetail(code) {
    currentDetailCode = code;
    const panel = document.getElementById('hotDetailPanel');
    const header = document.getElementById('hotDetailHeader');
    const loading = document.getElementById('hotDetailLoading');
    const content = document.getElementById('hotDetailContent');
    const mainContent = document.getElementById('hotMainContent');
    const aiContent = document.getElementById('hotAiContent');

    if (!panel) return;

    // 查找股票信息
    const stock = currentHotStocks.find(s => s.code === code);
    if (!stock) return;

    // 更新头部
    if (header) header.textContent = `${stock.name} (${stock.code})`;

    // 显示面板
    panel.style.display = 'block';

    // 重置 tab
    resetSubTabs('hot-detail');
    switchSubTab('hot-detail', 'risk');

    // 加载数据
    loading.style.display = 'block';
    content.style.display = 'none';
    mainContent.style.display = 'none';
    aiContent.style.display = 'none';

    try {
        // 并行获取主营构成和 AI 分析
        const [zygcRes, analysisRes] = await Promise.all([
            fetch(`${API_BASE}/zygc?symbol=${code}`),
            fetch(`${API_BASE}/hot/analyze`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    code: stock.code,
                    name: stock.name,
                    source: stock.source,
                    industry: stock.industry || ''
                })
            })
        ]);

        const zygcData = zygcRes.ok ? await zygcRes.json() : null;
        const analysisData = analysisRes.ok ? await analysisRes.json() : null;

        // 更新风险线索
        const logicArea = document.getElementById('hotLogicArea');
        if (logicArea) {
            logicArea.textContent = analysisData?.logic || '暂无风险线索';
        }

        // 更新主营构成
        const zygcArea = document.getElementById('hotZygcArea');
        if (zygcArea) {
            if (zygcData && zygcData.records && zygcData.records.length > 0) {
                zygcArea.textContent = formatZygcData(zygcData);
            } else {
                zygcArea.textContent = '暂无主营构成数据';
            }
        }

        // 更新 AI 分析
        const analysisArea = document.getElementById('hotAnalysisArea');
        if (analysisArea) {
            analysisArea.innerHTML = analysisData?.analysis || '暂无 AI 分析';
        }

        // 更新风险标签
        const riskTag = document.getElementById('hotDetailRiskTag');
        if (riskTag && analysisData?.riskLevel) {
            const riskClass = analysisData.riskLevel === 'high' ? 'danger' :
                              analysisData.riskLevel === 'medium' ? 'warning' : 'success';
            riskTag.className = `tag-${riskClass}`;
            riskTag.textContent = analysisData.riskLevel === 'high' ? '高风险' :
                                  analysisData.riskLevel === 'medium' ? '中风险' : '低风险';
        }

        // 更新股票基本信息
        if (stock.industry) {
            const infoHtml = `
                <div style="background:rgba(0,0,0,0.3);padding:12px;border-radius:6px;">
                    <div style="color:var(--cyber-text-dim);font-size:11px;margin-bottom:4px;">行业</div>
                    <div style="color:var(--cyber-text);font-size:14px;">${stock.industry}</div>
                </div>
                <div style="background:rgba(0,0,0,0.3);padding:12px;border-radius:6px;">
                    <div style="color:var(--cyber-text-dim);font-size:11px;margin-bottom:4px;">关注来源</div>
                    <div style="color:var(--cyber-text);font-size:14px;">${stock.source}</div>
                </div>
                <div style="background:rgba(0,0,0,0.3);padding:12px;border-radius:6px;">
                    <div style="color:var(--cyber-text-dim);font-size:11px;margin-bottom:4px;">关注热度</div>
                    <div style="color:var(--cyber-primary);font-size:14px;">${stock.heatScore || 0}</div>
                </div>
            `;
        }

        // 默认显示风险线索 tab
        content.style.display = 'block';
        loading.style.display = 'none';

    } catch (error) {
        console.error('加载详情失败:', error);
        loading.textContent = '加载失败，请重试';
    }
}

// 格式化主营数据
function formatZygcData(data) {
    if (!data.records || data.records.length === 0) return '暂无数据';

    const records = data.records;
    const latestDate = records[0]?.REPORT_DATE || '';

    let text = `报告期: ${latestDate}\n`;
    text += '=' .repeat(40) + '\n\n';

    // 按类型分组
    const types = {};
    records.forEach(r => {
        const type = r['分类类型'] || '其他';
        if (!types[type]) types[type] = [];
        types[type].push(r);
    });

    for (const [type, items] of Object.entries(types)) {
        text += `[${type}]\n`;
        items.forEach(item => {
            const name = item['分类名称'] || item['name'] || '-';
            const amount = item['营业收入'] || item['amount'] || '-';
            const ratio = item['收入比例'] || item['ratio'] || '-';
            if (amount !== '-') {
                text += `  • ${name}: ${amount}`;
                if (ratio !== '-' && ratio !== '') text += ` (${ratio})`;
                text += '\n';
            }
        });
        text += '\n';
    }

    return text.trim();
}

// -----------------------------------------------
// 3. Tab 切换
// -----------------------------------------------
function switchSubTab(context, tab) {
    // 重置所有 tab
    const tabs = document.querySelectorAll(`[data-context="${context}"] .sub-tab`);
    tabs.forEach(t => t.classList.remove('active'));

    // 激活当前 tab
    const activeTab = document.querySelector(`[data-context="${context}"] .sub-tab[onclick*="'${tab}'"]`);
    if (activeTab) activeTab.classList.add('active');

    // 切换内容
    if (context === 'hot-detail') {
        document.getElementById('hotDetailContent').style.display = tab === 'risk' ? 'block' : 'none';
        document.getElementById('hotMainContent').style.display = tab === 'main' ? 'block' : 'none';
        document.getElementById('hotAiContent').style.display = tab === 'ai' ? 'block' : 'none';
    }
}

function resetSubTabs(context) {
    const tabs = document.querySelectorAll(`[data-context="${context}"] .sub-tab`);
    tabs.forEach(t => t.classList.remove('active'));
}

// -----------------------------------------------
// 4. 工具函数
// -----------------------------------------------
function showLoading(text) {
    const overlay = document.getElementById('loadingOverlay');
    const loadingText = document.getElementById('loadingText');
    if (overlay) {
        overlay.style.display = 'flex';
        if (loadingText) loadingText.textContent = text || '◈ 处理中';
    }
}

function hideLoading() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.style.display = 'none';
}

function showError(msg) {
    const errorEl = document.getElementById('errorMsg');
    if (errorEl) {
        errorEl.textContent = msg;
        errorEl.style.display = 'block';
        setTimeout(() => {
            errorEl.style.display = 'none';
        }, 3000);
    }
}
