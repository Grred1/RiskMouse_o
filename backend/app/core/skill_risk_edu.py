"""
风险教育工具 (Risk Education Skill)

只保留关键词匹配逻辑。具体的金融风险知识内容均从
backend/prompts/skills/risk_edu_*.md 文件动态加载，
便于独立维护和扩充知识库。

知识库涵盖：止损纪律、仓位管理、估值风险、宏观传导、
高波动品种风险、基本面陷阱、流动性风险。
"""
from __future__ import annotations
from .config import load_skill_md

# ── 知识库索引（关键词 → skill 文件名） ───────────────────────────
# 每条记录：keywords（触发词）、skill（对应 .md 文件名，不含扩展名）、concept（展示用名称）

_KNOWLEDGE_INDEX: list[dict] = [
    {
        "keywords": ["止损", "亏多少", "跌多少卖", "设止损", "止损位"],
        "skill": "risk_edu_stoploss",
        "concept": "止损纪律 (Stop-Loss Discipline)",
    },
    {
        "keywords": ["仓位", "买多少", "加仓", "配置", "分散"],
        "skill": "risk_edu_position",
        "concept": "仓位管理 (Position Sizing)",
    },
    {
        "keywords": ["涨停", "连板", "龙头", "热门股", "题材"],
        "skill": "risk_edu_highvol",
        "concept": "高波动品种风险 (High-Volatility Risk)",
    },
    {
        "keywords": ["财报", "业绩", "净利润", "营收", "利润"],
        "skill": "risk_edu_fundamental",
        "concept": "基本面风险 (Fundamental Risk)",
    },
    {
        "keywords": ["宏观", "降息", "加息", "美联储", "通胀", "CPI", "PMI"],
        "skill": "risk_edu_macro",
        "concept": "宏观风险传导 (Macro Risk Transmission)",
    },
    {
        "keywords": ["估值", "PE", "PB", "贵不贵", "泡沫", "高估", "低估"],
        "skill": "risk_edu_valuation",
        "concept": "估值风险 (Valuation Risk)",
    },
    {
        "keywords": ["流动性", "成交量", "换手率", "放量", "缩量"],
        "skill": "risk_edu_liquidity",
        "concept": "流动性风险 (Liquidity Risk)",
    },
]


# ── 公开接口 ─────────────────────────────────────────────────────

def has_edu_match(question: str) -> bool:
    """快速判断是否有匹配的教育内容"""
    return any(
        any(kw in question for kw in entry["keywords"])
        for entry in _KNOWLEDGE_INDEX
    )


def risk_education(question: str) -> str:
    """
    风险教育主入口。
    根据用户问题关键词匹配知识库，加载对应 skill .md 文件，
    返回注入 LLM prompt 的教育内容上下文。
    无匹配时返回空字符串。
    """
    matched_contents: list[str] = []

    for entry in _KNOWLEDGE_INDEX:
        if any(kw in question for kw in entry["keywords"]):
            content = load_skill_md(entry["skill"])
            if content:
                matched_contents.append(content)

    if not matched_contents:
        return ""

    header = "[📚 风险教育工具] 检索到相关知识点："
    return header + "\n\n" + "\n\n---\n\n".join(matched_contents)


def list_all_concepts() -> list[str]:
    """列出知识库中所有概念名，供调试和展示用"""
    return [e["concept"] for e in _KNOWLEDGE_INDEX]
