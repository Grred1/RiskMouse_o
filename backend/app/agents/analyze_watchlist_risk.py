"""
自选风控 AI 解读 Agent
解读自选股的四维算法评分结果，输出简洁的风险/亮点结论。
"""
from .base import Agent

agent = Agent(
    name="analyze_watchlist_risk",
    description="解读自选股的四维量化评分，输出核心风险与亮点",
    category="sentiment",
    prompt_name="watchlist_risk",
    input_keys=[
        "name", "code",
        "fundamental_stars", "fundamental_basis",
        "news_stars", "news_basis",
        "risk_stars", "risk_basis",
        "overall_stars",
        "news_titles",
    ],
    cache_key_pattern="watchlist:risk_interpret:{code}:{date}",
    cache_ttl=86400,
    max_tokens=200,
    temperature=0.3,
)
