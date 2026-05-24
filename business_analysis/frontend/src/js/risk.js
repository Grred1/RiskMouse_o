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
    const analysisArea = document.getElementById('ztAnalysisArea');

    if (!header || !loading || !content || !logicArea || !analysisArea) return;

    // 更新头部
    header.textContent = `${name} (${code})`;

    // 显示加载中
    loading.style.display = 'flex';
    content.style.display = 'none';

    try {
        const pureCode = code.replace(/^(SH|SZ|BJ)/, '');

        // 从 riskPoolData 中查找 board（连板数）
        const stockInfo = riskPoolData.find(s => s.code === code);
        const board = stockInfo ? stockInfo.board : 0;

        // 并行获取 AI 风险评分和股吧数据
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

        // 更新星标行
        const starRow = document.getElementById('ztStarRow');
        if (starRow) {
            if (analysisData.scores && analysisData.scores.length > 0) {
                starRow.innerHTML = renderStarBadges(analysisData.scores);
                starRow.style.display = 'flex';
            } else {
                starRow.style.display = 'none';
            }
        }

        // 显示风险分析
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

        // 显示股吧关注点
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

function renderRiskScores(data) {
    const scores = data.scores || [];
    const overall = data.overall_conclusion || '';
    const finalConclusion = data.final_conclusion || '';

    // 评分对应的颜色（1-5分）
    const scoreColors = {
        1: { bar: '#27ae60', bg: '#e8f8e8', label: '低风险' },
        2: { bar: '#82c91e', bg: '#f0fae0', label: '中低风险' },
        3: { bar: '#f59f00', bg: '#fff3d6', label: '中风险' },
        4: { bar: '#e67e22', bg: '#fde8d0', label: '中高风险' },
        5: { bar: '#c0392b', bg: '#fce4e4', label: '高风险' },
    };

    // 总体结论标签
    let overallBadge = '';
    if (overall) {
        const avgScore = scores.reduce((sum, s) => sum + s.score, 0) / scores.length;
        const level = Math.round(avgScore);
        const color = scoreColors[level] || scoreColors[3];
        overallBadge = `
            <div class="risk-overall-badge" style="background:${color.bg};border:1px solid ${color.bar};">
                <span class="risk-overall-label">总体结论</span>
                <span class="risk-overall-text">${overall}</span>
            </div>
        `;
    }

    // 每个维度的评分条
    let scoresHtml = '';
    scores.forEach(s => {
        const sc = Math.max(1, Math.min(5, s.score));
        const color = scoreColors[sc] || scoreColors[3];
        const pct = (sc / 5) * 100;
        scoresHtml += `
            <div class="risk-dimension-row">
                <div class="risk-dimension-header">
                    <span class="risk-dimension-label">${s.label}</span>
                    <span class="risk-dimension-score" style="color:${color.bar};">
                        ${sc}<span class="risk-dimension-max">/5</span>
                        <span class="risk-dimension-tag" style="background:${color.bg};color:${color.bar};border:1px solid ${color.bar};">${color.label}</span>
                    </span>
                </div>
                <div class="risk-bar-track">
                    <div class="risk-bar-fill" style="width:${pct}%;background:${color.bar};"></div>
                </div>
            </div>
        `;
    });

    // 综合结论
    let conclusionHtml = '';
    if (finalConclusion) {
        conclusionHtml = `
            <div class="risk-final-conclusion">
                <div class="risk-final-title">📋 综合结论</div>
                <div class="risk-final-text">${finalConclusion}</div>
            </div>
        `;
    }

    return `
        ${overallBadge}
        <div class="risk-scores-container">
            ${scoresHtml}
        </div>
        ${conclusionHtml}
    `;
}

function renderStarBadges(scores) {
    const dimensionIcons = {
        logic_match: '🔗',
        financial_health: '💰',
        valuation_bubble: '🎈',
        capital_risk: '💧',
        governance_risk: '🏛️',
    };
    return scores.map(s => {
        const filled = '★'.repeat(s.score);
        const empty = '☆'.repeat(5 - s.score);
        const icon = dimensionIcons[s.key] || '📊';
        return `
            <div class="risk-star-item" title="${s.label}: ${s.score}/5">
                <span class="risk-star-icon">${icon}</span>
                <span class="risk-star-label">${s.label}</span>
                <span class="risk-star-stars">${filled}${empty}</span>
                <span class="risk-star-num">${s.score}</span>
            </div>
        `;
    }).join('');
}

function renderFallbackText(text) {
    if (!text) return '<div class="risk-error">暂无风险分析数据</div>';

    let html = '';

    // 提取综合风险评分行
    const overallMatch = text.match(/【综合风险评分】(.+?)(?:\n|$)/);
    if (overallMatch) {
        const overallText = overallMatch[1].trim();
        let riskLevel = '中风险';
        let barColor = '#f59f00';
        if (overallText.includes('高风险') || overallText.includes('高')) { riskLevel = '高风险'; barColor = '#c0392b'; }
        else if (overallText.includes('低风险') || overallText.includes('低')) { riskLevel = '低风险'; barColor = '#27ae60'; }

        html += `
            <div class="risk-fallback-overall" style="border-color:${barColor};">
                <span class="risk-fallback-overall-label" style="background:${barColor};">综合风险</span>
                <span class="risk-fallback-overall-text">${overallText}</span>
            </div>
        `;
    }

    // 提取各维度评分
    const dimSection = text.match(/【各维度评分】([\s\S]*?)(?=【|$)/);
    if (dimSection) {
        const lines = dimSection[1].split('\n').filter(l => l.trim());
        html += '<div class="risk-fallback-dims">';
        lines.forEach(line => {
            const trimmed = line.replace(/^-\s*\*{0,2}/, '').trim();
            if (!trimmed) return;
            // 匹配 "**基本面风险: 8/10** —— 理由"
            const dimMatch = trimmed.match(/\*{0,2}(.+?)\s*:\s*(\d+)\/10\*{0,2}\s*[—\-–]+\s*(.+)/);
            if (dimMatch) {
                const dimName = dimMatch[1].replace(/\*{0,2}/g, '').trim();
                const dimScore = parseInt(dimMatch[2]);
                const dimReason = dimMatch[3].trim();
                const pct = Math.min(100, (dimScore / 10) * 100);
                const color = dimScore >= 8 ? '#c0392b' : dimScore >= 6 ? '#e67e22' : dimScore >= 4 ? '#f59f00' : '#27ae60';
                html += `
                    <div class="risk-fallback-dim">
                        <div class="risk-fallback-dim-header">
                            <span class="risk-fallback-dim-name">${dimName}</span>
                            <span class="risk-fallback-dim-score" style="color:${color};">${dimScore}<span class="risk-dimension-max">/10</span></span>
                        </div>
                        <div class="risk-bar-track">
                            <div class="risk-bar-fill" style="width:${pct}%;background:${color};"></div>
                        </div>
                        <div class="risk-fallback-dim-reason">${dimReason}</div>
                    </div>
                `;
            }
        });
        html += '</div>';
    }

    // 提取核心风险点
    const riskSection = text.match(/【核心风险点】([\s\S]*?)(?=【|$)/);
    if (riskSection) {
        const items = riskSection[1].split('\n').filter(l => l.trim());
        html += '<div class="risk-fallback-points">';
        html += '<div class="risk-fallback-section-title">⚠️ 核心风险点</div>';
        items.forEach(item => {
            const clean = item.replace(/^\d+[.、]\s*/, '').replace(/^\*\*/, '').replace(/\*\*$/, '').trim();
            if (clean) {
                html += `<div class="risk-fallback-point">${clean}</div>`;
            }
        });
        html += '</div>';
    }

    // 提取风险结论
    const conclusionMatch = text.match(/【风险结论】([\s\S]*?)(?=【|$)/);
    if (conclusionMatch) {
        const conclusionText = conclusionMatch[1].trim();
        html += `
            <div class="risk-final-conclusion">
                <div class="risk-final-title">📋 风险结论</div>
                <div class="risk-final-text">${conclusionText}</div>
            </div>
        `;
    }

    // 如果什么都没解析到，直接当纯文本展示
    if (!html) {
        const escaped = text.replace(/\n/g, '<br>');
        html = `<div class="risk-fallback-text">${escaped}</div>`;
    }

    return html;
}

function renderGubaData(container, data) {
    if (!data || data.error) {
        container.textContent = '暂无股吧数据';
        return;
    }

    const keywords   = data.keywords    || [];
    const postTitles = data.post_titles || [];
    const stats      = data.stats       || {};
    const analysis   = data.analysis    || '';
    const rank       = data.rank        || {};
    const total      = stats.total_data_points || 0;

    // 统计数字小块（紧凑单行）
    const statItems = [
        { val: stats.keyword_count, label: '热门关键词', color: '#4f8fdc' },
        { val: stats.post_count,    label: '帖子标题',   color: '#f97316' },
        { val: stats.relate_count,  label: '相关股票',   color: '#22c55e' },
        { val: stats.rank_days,     label: '排名天数',    color: '#8b5cf6' },
    ].filter(s => s.val > 0);

    const statHtml = statItems.map(s =>
        `<div style="text-align:center;min-width:52px;"><div style="font-size:18px;font-weight:700;color:${s.color};line-height:1.2;">${s.val}</div><div style="font-size:10px;color:#8fa3b8;margin-top:2px;">${s.label}</div></div>`
    ).join('');

    let html = `<div style="margin-bottom:10px;padding:10px 12px;background:rgba(79,143,220,0.07);border:1px solid rgba(79,143,220,0.18);border-radius:10px;">` +
        `<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;"><span style="font-size:13px;font-weight:700;color:#1e3252;">📊 股吧数据分析</span><span style="font-size:11px;color:#8fa3b8;">共挖掘 <strong style="color:#ef4444;">${total}</strong> 条数据</span></div>` +
        `<div style="display:flex;gap:12px;flex-wrap:wrap;">${statHtml}</div>` +
        `</div>`;

    // 人气排名
    if (rank.rank) {
        const changeStr = rank.rankChange
            ? `（较昨日 ${rank.rankChange > 0 ? '↑' : '↓'}${Math.abs(rank.rankChange)}）`
            : '';
        html += `<div style="margin-bottom:8px;font-size:12px;color:#4a6080;">人气排名：<strong style="color:#1e3252;">第${rank.rank}名</strong>${changeStr}，共 ${rank.marketAllCount || '--'} 只参评</div>`;
    }

    // 热门关键词
    if (keywords.length > 0) {
        const maxHot = Math.max(...keywords.map(k => k.hotness), 1);
        const chips = keywords.map(kw => {
            const t = Math.round((kw.hotness / maxHot) * 5);
            const bg = ['rgba(148,163,184,0.12)','rgba(79,143,220,0.10)','rgba(79,143,220,0.20)','rgba(79,143,220,0.35)','rgba(53,120,201,0.55)','rgba(53,120,201,0.80)'][t] || 'rgba(148,163,184,0.12)';
            const fg = t > 3 ? '#fff' : '#1e3252';
            return `<span style="display:inline-block;padding:2px 9px;margin:2px 3px;border-radius:10px;font-size:11px;background:${bg};color:${fg};white-space:nowrap;">${kw.keyword} ${kw.hotness}</span>`;
        }).join('');
        html += `<div style="margin-bottom:8px;"><span style="font-size:12px;font-weight:600;color:#4a6080;">热门概念：</span>${chips}</div>`;
    }

    // 帖子标题（可点击跳转）
    if (postTitles.length > 0) {
        const rows = postTitles.map(p => {
            const t = typeof p === 'string' ? p : p.title;
            const u = typeof p === 'string' ? '' : p.url;
            if (u) {
                return `<div style="padding:3px 0;border-bottom:1px solid rgba(148,163,184,0.12);font-size:12px;"><a href="${u}" target="_blank" rel="noopener noreferrer" style="color:#3578c9;text-decoration:none;" onmouseover="this.style.textDecoration='underline'" onmouseout="this.style.textDecoration='none'">${t}</a></div>`;
            }
            return `<div style="padding:3px 0;border-bottom:1px solid rgba(148,163,184,0.12);font-size:12px;color:#4a6080;">${t}</div>`;
        }).join('');
        html += `<details style="margin-bottom:8px;"><summary style="cursor:pointer;font-size:12px;font-weight:600;color:#4a6080;">📝 最新股吧热帖（${postTitles.length}条）</summary><div style="margin-top:5px;max-height:120px;overflow-y:auto;background:rgba(248,250,252,0.70);padding:8px 10px;border-radius:8px;border:1px solid rgba(148,163,184,0.14);">${rows}</div></details>`;
    }

    // AI 舆情分析（可展开/收起）
    if (analysis) {
        const truncated = analysis.length > 120 ? analysis.slice(0, 120) + '...' : analysis;
        html += `<div style="padding:10px 12px;background:rgba(245,158,11,0.06);border:1px solid rgba(245,158,11,0.22);border-radius:10px;"><div style="font-size:12px;font-weight:700;color:#92400e;margin-bottom:5px;cursor:pointer;" onclick="toggleAnalysis(this)">🤖 AI 股吧舆情分析 <span style="font-size:10px;color:#b45309;">（点击展开/收起）</span></div><div class="guba-analysis-short" style="font-size:12px;line-height:1.7;color:#4a6080;white-space:pre-wrap;">${truncated}</div><div class="guba-analysis-full" style="font-size:12px;line-height:1.7;color:#4a6080;white-space:pre-wrap;display:none;">${analysis}</div></div>`;
    }

    container.innerHTML = html;
}

function toggleAnalysis(el) {
    const container = el.parentElement;
    const short = container.querySelector('.guba-analysis-short');
    const full = container.querySelector('.guba-analysis-full');
    if (!short || !full) return;
    if (full.style.display === 'none') {
        short.style.display = 'none';
        full.style.display = 'block';
        el.querySelector('span').textContent = '（点击收起）';
    } else {
        short.style.display = 'block';
        full.style.display = 'none';
        el.querySelector('span').textContent = '（点击展开/收起）';
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    // 设置默认日期为今天
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('ztDateInput').value = today;

    // 启动时自动加载
    fetchRiskPool(true);
});
