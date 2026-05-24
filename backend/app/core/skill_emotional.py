"""
情绪急救工具 (Emotional First Aid Skill)

只保留情绪检测逻辑。具体的引导内容、行为金融学框架、
语气要求等均从 backend/prompts/skills/ 的 .md 文件动态加载，
便于独立维护和迭代。

学术依据：
  - Kahneman & Tversky (1979): 前景理论 / 损失厌恶
  - Shefrin & Statman (1985): 处置效应
  - De Bondt & Thaler (1985): 过度反应假说
  - Barber & Odean (2000): 过度自信与过度交易
"""
from __future__ import annotations
from .config import load_skill_md

# ── 情绪信号词 ────────────────────────────────────────────────────

_PANIC_SIGNALS: list[str] = [
    "慌", "怕", "恐慌", "要不要卖", "马上卖", "割肉", "扛不住",
    "跌停", "亏了", "完了", "崩了", "跑路", "清仓", "暴跌",
    "亏损", "救命", "怎么办", "赔了", "赔钱", "跌好多",
]

_GREED_SIGNALS: list[str] = [
    "追涨", "加仓", "梭哈", "全仓", "涨停", "暴涨", "翻倍",
    "发财", "抄底", "一把梭", "满仓", "冲一把", "上车",
]


# ── 公开接口 ─────────────────────────────────────────────────────

def detect_emotion(question: str) -> str:
    """
    识别用户情绪类型。
    返回: "panic" | "greed" | "neutral"
    """
    if any(s in question for s in _PANIC_SIGNALS):
        return "panic"
    if any(s in question for s in _GREED_SIGNALS):
        return "greed"
    return "neutral"


def is_emotional(question: str) -> bool:
    """快速判断是否触发情绪急救"""
    return detect_emotion(question) != "neutral"


def emotional_first_aid(question: str) -> str:
    """
    情绪急救主入口。
    根据检测到的情绪类型，加载对应 skill .md 文件内容，
    返回注入 LLM prompt 的引导上下文。
    无情绪信号时返回空字符串，不干扰正常对话。
    """
    emotion = detect_emotion(question)

    if emotion == "panic":
        content = load_skill_md("emotional_panic")
        label = "[🆘 情绪急救 · 恐慌模式]"
    elif emotion == "greed":
        content = load_skill_md("emotional_greed")
        label = "[🆘 情绪急救 · 过度乐观模式]"
    else:
        return ""

    if not content:
        return ""

    return f"{label}\n{content}"
