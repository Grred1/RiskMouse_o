from __future__ import annotations

from ..agent_runtime.verifier import verify_report
from .registry import register_tool


@register_tool("generate_risk_report", "汇总工具结果并生成经证据校验的风险报告", timeout_seconds=15)
def generate_risk_report(question: str, symbol: str, dependency_outputs: dict) -> dict:
    report = verify_report(dependency_outputs)
    return {"symbol": symbol, "question": question, "report": report, "evidence": report["evidence"], "limitations": report["limitations"]}
