"""
Agent 注册表
所有 Agent 在此集中注册，提供统一 list / run 入口。

用法:
    from ..agents import list_agents, run_agent
    agents = list_agents(category="finance")
    result = run_agent("analyze_zygc", inputs={...})
"""
from __future__ import annotations

from .base import Agent
from .analyze_zygc import agent as analyze_zygc
from .analyze_financial import agent as analyze_financial
from .analyze_sentiment import agent as analyze_sentiment
from .analyze_guba import agent as analyze_guba
from .analyze_watchlist_risk import agent as analyze_watchlist_risk
from .filter_risk_events import agent as filter_risk_events
from .analyze_event_timing import agent as analyze_event_timing
from .super_agent import agent as super_agent

AGENT_REGISTRY: list[Agent] = [
    analyze_zygc,
    analyze_financial,
    analyze_sentiment,
    analyze_guba,
    analyze_watchlist_risk,
    filter_risk_events,
    analyze_event_timing,
    super_agent,
]

AGENT_MAP: dict[str, Agent] = {a.name: a for a in AGENT_REGISTRY}


def list_agents(category: str = "") -> list[dict]:
    agents = AGENT_REGISTRY
    if category:
        agents = [a for a in agents if a.category == category]
    return [a.to_dict() for a in agents]


def run_agent(name: str, inputs: dict) -> str:
    agent = AGENT_MAP.get(name)
    if not agent:
        raise ValueError(f"Agent '{name}' 未注册，可用: {list(AGENT_MAP.keys())}")
    return agent.run(inputs)
