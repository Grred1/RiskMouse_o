function renderRiskScores(data) {
    const scores = data.scores || [];
    const overall = data.overall_conclusion || '';
    const finalConclusion = data.final_conclusion || '';

    const scoreColors = {
        1: { bar: '#27ae60', bg: '#e8f8e8', label: '低风险' },
        2: { bar: '#82c91e', bg: '#f0fae0', label: '中低风险' },
        3: { bar: '#f59f00', bg: '#fff3d6', label: '中风险' },
        4: { bar: '#e67e22', bg: '#fde8d0', label: '中高风险' },
        5: { bar: '#c0392b', bg: '#fce4e4', label: '高风险' },
    };

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

    const dimSection = text.match(/【各维度评分】([\s\S]*?)(?=【|$)/);
    if (dimSection) {
        const lines = dimSection[1].split('\n').filter(l => l.trim());
        html += '<div class="risk-fallback-dims">';
        lines.forEach(line => {
            const trimmed = line.replace(/^-\s*\*{0,2}/, '').trim();
            if (!trimmed) return;
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

    if (rank.rank) {
        const changeStr = rank.rankChange
            ? `（较昨日 ${rank.rankChange > 0 ? '↑' : '↓'}${Math.abs(rank.rankChange)}）`
            : '';
        html += `<div style="margin-bottom:8px;font-size:12px;color:#4a6080;">人气排名：<strong style="color:#1e3252;">第${rank.rank}名</strong>${changeStr}，共 ${rank.marketAllCount || '--'} 只参评</div>`;
    }

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
