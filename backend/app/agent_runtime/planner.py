"""规则优先的 Planner，避免让模型自由生成不受控工具调用。"""
from __future__ import annotations

from .schemas import TaskPlan, TaskSpec


def create_plan(question: str, symbol: str, session_id: str = "") -> TaskPlan:
    """生成白名单内的分析 DAG；后续可在此接入经过校验的 LLM Planner。"""
    question = question.strip() or f"分析 {symbol} 的近期风险"
    tasks = [
        TaskSpec(id="financial", tool="get_financials", input={"symbol": symbol}),
        TaskSpec(id="news", tool="get_stock_news", input={"symbol": symbol}),
        TaskSpec(id="sentiment", tool="get_guba_posts", input={"symbol": symbol}),
        TaskSpec(
            id="report", tool="generate_risk_report",
            depends_on=["financial", "news", "sentiment"], input={"question": question, "symbol": symbol},
            retries=0, timeout_seconds=15,
        ),
    ]
    return TaskPlan(goal=question, symbol=symbol, tasks=tasks, session_id=session_id)


def create_patrol_plan(session_id: str = "") -> TaskPlan:
    """将既有的小老鼠巡检纳入同一编排器，而非另起一个不可追踪线程。"""
    return TaskPlan(
        goal="执行全局风险巡检：宏观新闻与自选股股吧",
        symbol="",
        kind="global_patrol",
        session_id=session_id,
        tasks=[TaskSpec(id="patrol", tool="run_deep_surf", retries=0, timeout_seconds=180)],
    )
