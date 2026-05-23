"""
风险评分引擎 — 纯算法，不依赖 AI，可复用于任意 A 股股票。
所有评分函数返回:
  {"score": 1-5, "basis": "可读文字依据", "detail": {...}}
"""

# ── 风险词库（三级） ────────────────────────────────────────────

HIGH_RISK_WORDS = [
    "立案调查", "强制退市", "退市风险", "暂停上市", "终止上市",
    "*ST", "财务造假", "虚假陈述", "信息披露违规", "重大违法",
    "刑事追诉", "破产重整", "流动性危机", "资不抵债", "债务违约",
    "证监会处罚", "行政处罚", "证监会调查", "欺诈发行",
]

MEDIUM_RISK_WORDS = [
    "亏损", "净利润下滑", "净利润下降", "营收下滑", "营收下降",
    "商誉减值", "存货积压", "应收账款激增", "大股东减持", "高管离职",
    "监管问询", "关注函", "问询函", "业绩预警", "业绩下修",
    "业绩不达预期", "被诉", "仲裁", "违规", "股权质押",
    "ST", "风险提示", "退市整理", "经营困难", "资金紧张",
    "审计意见保留", "无法表示意见", "持续经营存疑",
    "诉讼", "纠纷", "举报", "处罚", "警示",
]

POSITIVE_WORDS = [
    "中标", "重大合同", "战略合作", "签署协议", "获批",
    "股份回购", "回购股份", "高管增持", "大股东增持",
    "业绩超预期", "净利润大增", "营收大增", "业绩增长",
    "新产品", "新技术", "技术突破", "获得专利",
    "国资入主", "央企合作", "重组", "资产注入",
    "特别分红", "高送转", "利润分配",
    "扭亏为盈", "扭亏", "实现盈利",
]


def _clamp(val: float, lo: int = 1, hi: int = 5) -> int:
    return max(lo, min(hi, round(val)))


# ── 基本面评分 ────────────────────────────────────────────────

def score_fundamental(fin_abstract: dict) -> dict:
    """
    基于同花顺财务摘要字段评分。
    fin_abstract: ak.stock_financial_abstract_ths 最新一行 to_dict()
    """
    points = 0.0
    detail = {}
    basis_lines = []

    def _pct(key):
        """解析百分比字段，返回 float 或 None"""
        v = fin_abstract.get(key)
        if v is None:
            return None
        try:
            return float(str(v).replace("%", "").replace("--", "").strip())
        except Exception:
            return None

    # 营收增速
    rev_yoy = _pct("营业总收入同比增长率")
    if rev_yoy is not None:
        if rev_yoy > 20:
            points += 2; basis_lines.append(f"营收增速 {rev_yoy:.1f}% ↑↑(+2)")
        elif rev_yoy > 10:
            points += 1; basis_lines.append(f"营收增速 {rev_yoy:.1f}% ↑(+1)")
        elif rev_yoy < 0:
            points -= 2; basis_lines.append(f"营收增速 {rev_yoy:.1f}% ↓↓(-2)")
        else:
            basis_lines.append(f"营收增速 {rev_yoy:.1f}%(0)")
        detail["rev_yoy"] = rev_yoy

    # 净利润增速
    np_yoy = _pct("净利润同比增长率")
    if np_yoy is not None:
        if np_yoy > 20:
            points += 2; basis_lines.append(f"净利增速 {np_yoy:.1f}% ↑↑(+2)")
        elif np_yoy > 10:
            points += 1; basis_lines.append(f"净利增速 {np_yoy:.1f}% ↑(+1)")
        elif np_yoy < 0:
            points -= 2; basis_lines.append(f"净利增速 {np_yoy:.1f}% ↓↓(-2)")
        else:
            basis_lines.append(f"净利增速 {np_yoy:.1f}%(0)")
        detail["np_yoy"] = np_yoy

    # 毛利率
    gross = _pct("销售毛利率")
    if gross is not None:
        if gross > 40:
            points += 2; basis_lines.append(f"毛利率 {gross:.1f}% ↑↑(+2)")
        elif gross > 20:
            points += 1; basis_lines.append(f"毛利率 {gross:.1f}% ↑(+1)")
        elif gross < 10:
            points -= 1; basis_lines.append(f"毛利率 {gross:.1f}% ↓(-1)")
        else:
            basis_lines.append(f"毛利率 {gross:.1f}%(0)")
        detail["gross_margin"] = gross

    # ROE
    roe = _pct("净资产收益率")
    if roe is not None:
        if roe > 15:
            points += 2; basis_lines.append(f"ROE {roe:.1f}% ↑↑(+2)")
        elif roe > 8:
            points += 1; basis_lines.append(f"ROE {roe:.1f}% ↑(+1)")
        elif roe < 0:
            points -= 2; basis_lines.append(f"ROE {roe:.1f}% ↓↓(-2)")
        else:
            basis_lines.append(f"ROE {roe:.1f}%(0)")
        detail["roe"] = roe

    # 资产负债率
    debt = _pct("资产负债率")
    if debt is not None:
        if debt < 40:
            points += 1; basis_lines.append(f"资产负债率 {debt:.1f}% 低(+1)")
        elif debt > 70:
            points -= 2; basis_lines.append(f"资产负债率 {debt:.1f}% 高(-2)")
        else:
            basis_lines.append(f"资产负债率 {debt:.1f}%(0)")
        detail["debt_ratio"] = debt

    score = _clamp(3 + points)
    return {
        "score": score,
        "basis": "；".join(basis_lines) if basis_lines else "财务数据不足",
        "detail": detail,
    }


# ── 新闻情绪评分 ────────────────────────────────────────────────

def score_news(news_list: list) -> dict:
    """
    news_list: [{"title": str, "url": str, ...}, ...]
    """
    points = 0.0
    found_high = []
    found_medium = []
    found_positive = []

    all_text = " ".join(item.get("title", "") + item.get("content", "")[:100]
                        for item in news_list)

    for w in HIGH_RISK_WORDS:
        cnt = all_text.count(w)
        if cnt:
            points -= 3 * min(cnt, 2)
            found_high.append(w)

    for w in MEDIUM_RISK_WORDS:
        cnt = all_text.count(w)
        if cnt:
            points -= 1.5 * min(cnt, 2)
            found_medium.append(w)

    for w in POSITIVE_WORDS:
        cnt = all_text.count(w)
        if cnt:
            points += 1.5 * min(cnt, 2)
            found_positive.append(w)

    score = _clamp(3 + points / 3)

    basis_parts = []
    if found_high:
        basis_parts.append(f"高危词: {', '.join(found_high[:3])}")
    if found_medium:
        basis_parts.append(f"风险词: {', '.join(found_medium[:4])}")
    if found_positive:
        basis_parts.append(f"正面词: {', '.join(found_positive[:3])}")
    if not basis_parts:
        basis_parts.append("未检测到明显风险或利好词")

    return {
        "score": score,
        "basis": "；".join(basis_parts),
        "detail": {
            "high_risk": found_high,
            "medium_risk": found_medium,
            "positive": found_positive,
            "news_count": len(news_list),
        },
    }


# ── 风险等级评分（越高风险越大） ─────────────────────────────────

def score_risk(fundamental_result: dict, news_result: dict, fin_abstract: dict) -> dict:
    """综合风险等级：负债 40% + 新闻负面 35% + 盈利稳定 25%"""
    f_score = fundamental_result["score"]
    n_score = news_result["score"]

    # 负债风险（资产负债率）
    debt = fundamental_result["detail"].get("debt_ratio")
    if debt is not None:
        debt_risk = min(5, max(1, round(debt / 15)))
    else:
        debt_risk = 3

    # 新闻负面程度（反转新闻情绪）
    news_risk = 6 - n_score

    # 盈利稳定性（基本面反转）
    profit_risk = 6 - f_score

    raw = debt_risk * 0.4 + news_risk * 0.35 + profit_risk * 0.25
    score = _clamp(raw)

    basis = f"负债风险{debt_risk}星·新闻负面{news_risk}星·盈利稳定{profit_risk}星 → 加权{score}星"
    return {"score": score, "basis": basis, "detail": {
        "debt_risk": debt_risk, "news_risk": news_risk, "profit_risk": profit_risk,
    }}


# ── 综合评分 ────────────────────────────────────────────────────

def score_overall(fundamental_result: dict, news_result: dict, risk_result: dict) -> dict:
    """加权综合：基本面40% + 新闻30% + 风险反转30%"""
    f = fundamental_result["score"]
    n = news_result["score"]
    r = 6 - risk_result["score"]  # 风险越低 → 综合越高

    raw = f * 0.4 + n * 0.3 + r * 0.3
    score = _clamp(raw)
    basis = f"基本面{f}★×40% + 新闻{n}★×30% + 低风险{r}★×30% = {score}★"
    return {"score": score, "basis": basis, "detail": {}}
