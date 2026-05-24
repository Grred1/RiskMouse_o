"""
超级 Agent（小老鼠）
可调用其他所有 Agent 来回答问题，具备缓存感知能力。
"""
from __future__ import annotations

from .base import Agent, load_prompt
from ..core import read_cache

SUPER_AGENT_PROMPT = load_prompt("super_agent")


def _fetch_cache_summary() -> tuple[str, str]:
    from . import list_agents
    agents = list_agents()
    cache_lines = []
    for a in agents:
        cache_lines.append(f"  - {a['name']}: {a['description']}")
    agent_list = "\n".join(cache_lines) if cache_lines else "  (暂无可用 Agent)"

    keys = [
        ("macro:timeline", "宏观风险时间轴"),
        ("sentiment:pool", "热门风险股池"),
    ]
    cache_summary_lines = []
    for key, desc in keys:
        cached = read_cache(key, module="")
        status = "✅ 有缓存" if cached else "❌ 无缓存"
        cache_summary_lines.append(f"  {desc}: {status}")
    cache_summary = "\n".join(cache_summary_lines)

    return agent_list, cache_summary


def _build_super_agent_inputs(inputs: dict) -> dict:
    """预处理 inputs，补全 agent_list / cache_summary 等动态字段"""
    agent_list, cache_summary = _fetch_cache_summary()

    question = inputs.get("question", "")
    tool_context = inputs.get("tool_context", "")
    has_skill = bool(tool_context)
    length_instruction = "用 250 字以内回答，" if has_skill else "用 150 字以内回答，"

    return {
        "question": question,
        "agent_list": agent_list,
        "cache_summary": cache_summary,
        "rag_context": inputs.get("rag_context", ""),
        "tool_context": tool_context,
        "usage_guide": inputs.get("usage_guide", ""),
        "length_instruction": length_instruction,
        "status": inputs.get("status", "idle"),
        "last_action": inputs.get("last_action", ""),
        "screen": inputs.get("screen", ""),
    }


agent = Agent(
    name="super_agent",
    description="小老鼠超级助手：可调用财报分析、舆论分析、宏观分析等所有 Agent 回答问题",
    category="super",
    prompt_name="super_agent",
    input_keys=[
        "question", "agent_list", "cache_summary",
        "rag_context", "tool_context", "usage_guide",
        "length_instruction",
        "status", "last_action", "screen",
    ],
    input_builder=_build_super_agent_inputs,
    cache_key_pattern="",
    cache_ttl=0,
    max_tokens=600,
    temperature=0.8,
)
