"""
宏观风险事件过滤 Agent
从新闻中筛选出真正具有宏观风险影响的事件，过滤日常噪音。
"""
import json
import re

from .base import Agent


def _parse_llm_list(text: str) -> list:
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\[[\s\S]*\]", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return []


agent = Agent(
    name="filter_risk_events",
    description="从新闻中过滤出真正的宏观风险事件",
    category="macro",
    prompt_name="macro_risk_filter",
    input_keys=["news_data"],
    cache_key_pattern="",
    cache_ttl=0,
    max_tokens=3000,
    temperature=0.3,
    output_parser=_parse_llm_list,
)
