async function requestFinancialAI(latest, profit, balance, cash) {
    const section = document.getElementById('aiSection');
    const loading = document.getElementById('aiCombinedLoading');
    const content = document.getElementById('aiCombinedContent');
    section.style.display = 'block';
    loading.style.display = 'block';
    content.innerHTML = '';

    const code = financialData.code || '';
    const name = financialData.name || '';
    const annualProfit = profit.filter(d => d.REPORT_TYPE === '年报');
    const annualBalance = balance.filter(d => d.REPORT_TYPE === '年报');
    const latestBal = annualBalance.length > 0 ? annualBalance[annualBalance.length - 1] : {};
    const latestCashRaw = (cash.filter(d => d.REPORT_TYPE === '年报'));
    const latestCash = latestCashRaw.length > 0 ? latestCashRaw[latestCashRaw.length - 1] : {};
    const rdData = annualProfit.map(d => ({ date: d.REPORT_DATE, rd: d.RESEARCH_EXPENSE, rdYoy: d.RESEARCH_EXPENSE_YOY }));
    const trend = annualProfit.map(d => ({ date: d.REPORT_DATE, revenue: d.TOTAL_OPERATE_INCOME, profit: d.NETPROFIT }));

    const payload = {
        symbol: code, code, name,
        latestAbstract: latest,
        profitTrend: trend,
        balanceLatest: latestBal,
        cashLatest: latestCash,
        rdData: rdData,
        businessGrowth: {},
        assetExpansion: annualBalance.map(d => ({ date: d.REPORT_DATE, fixed: d.FIXED_ASSET, inProgress: d.CIP })),
    };

    try {
        const resp = await fetch('/api/analyze/financial-combined', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const result = await resp.json();
        loading.style.display = 'none';

        const scores = result.scores || {};
        const scoreConfig = [
            { key: 'solvency', label: '偿债', color: '#3498db' },
            { key: 'operating_capacity', label: '营运', color: '#e67e22' },
            { key: 'profitability', label: '盈利', color: '#27ae60' },
            { key: 'growth_and_cashflow', label: '成长', color: '#9b59b6' },
        ];

        const scoreRow = document.getElementById('aiScoreRow');
        if (scoreRow) {
            scoreRow.innerHTML = scoreConfig.map(c => {
                const s = scores[c.key] || 0;
                const stars = '★'.repeat(s) + '☆'.repeat(5 - s);
                return `<span style="display:inline-flex;align-items:center;gap:3px;font-size:12px;color:${c.color};font-weight:600;background:#f5f6fa;padding:3px 10px;border-radius:12px;white-space:nowrap;">
                    ${c.label} ${s}${stars}
                </span>`;
            }).join('');
        }

        const badge = document.getElementById('aiOverallBadge');
        if (badge && result.overall_conclusion) {
            badge.textContent = '📌 ' + result.overall_conclusion;
        }

        let html = '';

        if (result.final_conclusion) {
            const text = result.final_conclusion;
            const paragraphs = text.split('\n').filter(p => p.trim());
            html += `<div style="background:#f8f9fa;border-radius:10px;padding:14px;border:1px solid #e8ecf1;">
                <div style="font-size:13px;line-height:1.9;color:#444;white-space:pre-wrap;">`;
            paragraphs.forEach((p, i) => {
                const trimmed = p.trim();
                const hasData = /[\d.]+%|[\d.]+亿|-?\d+\.\d+/.test(trimmed);
                const isKeyPoint = /风险|健康|稳定|恶化|改善|优秀|不足|关注/.test(trimmed);
                if (hasData) {
                    html += `<span style="display:block;padding:2px 0;">${trimmed}</span>`;
                } else if (isKeyPoint) {
                    html += `<span style="display:block;padding:3px 0;font-weight:600;color:#333;">${trimmed}</span>`;
                } else {
                    html += `<span style="display:block;padding:1px 0;">${trimmed}</span>`;
                }
            });
            html += `</div></div>`;
        }

        content.innerHTML = html || '<div style="color:#999;text-align:center;padding:20px;">暂无分析结果</div>';
    } catch (e) {
        loading.style.display = 'none';
        content.innerHTML = '<div style="color:#c0392b;text-align:center;padding:20px;">AI 分析请求失败: ' + e.message + '</div>';
    }
}
