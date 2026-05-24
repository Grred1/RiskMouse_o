"""
股吧舆情分析 Agent
分析股吧热门关键词、人气数据、帖子标题，给出市场情绪判断。
"""
from .base import Agent

agent = Agent(
    name="analyze_guba",
    description="分析东方财富股吧数据（关键词、人气排名、帖子标题），判断市场情绪和核心逻辑",
    category="sentiment",
    prompt_name="guba_analysis",
    input_keys=["name", "code", "keywords", "rank_data", "post_titles"],
    cache_key_pattern="sentiment:guba_analysis:{code}",
    cache_ttl=600,
    max_tokens=500,
    temperature=0.3,
)
