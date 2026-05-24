"""
宏观事件时间分析 Agent
分析宏观风险事件的时间特征（发生时间、持续时长、状态）。
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
    name="analyze_event_timing",
    description="分析宏观风险事件的时间特征（发生时间、持续时长、状态）",
    category="macro",
    prompt_name="macro_time_analysis",
    input_keys=["current_date", "events_data"],
    cache_key_pattern="",
    cache_ttl=0,
    max_tokens=3000,
    temperature=0.3,
    output_parser=_parse_llm_list,
)
