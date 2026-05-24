"""
舆论情绪分析 Agent
分析股票的市场舆论情绪（股吧观点、情绪倾向、风险信号）。
"""
from .base import Agent

agent = Agent(
    name="analyze_sentiment",
    description="分析股票的市场舆论情绪（股吧观点、情绪倾向、风险信号）",
    category="sentiment",
    prompt_name="zt_risk",
    input_keys=["name", "code", "board", "industry", "zygc", "logic", "extra_info"],
    cache_key_pattern="sentiment:risk_analyze:{code}",
    cache_ttl=600,
    max_tokens=1000,
    temperature=0.3,
)
