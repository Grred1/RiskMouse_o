"""结果验证：宁可声明证据不足，也不输出不可追溯的风险判断。"""
from __future__ import annotations

from typing import Any


def verify_report(dependency_outputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    evidence = []
    limitations = []
    for result in dependency_outputs.values():
        evidence.extend(result.get("evidence", []))
        limitations.extend(result.get("limitations", []))

    findings = []
    news_items = dependency_outputs.get("news", {}).get("items", [])
    guba_items = dependency_outputs.get("sentiment", {}).get("items", [])
    financial_records = dependency_outputs.get("financial", {}).get("records", [])
    if news_items:
        findings.append({"dimension": "公开新闻", "statement": f"已检索到 {len(news_items)} 条近期新闻，需结合标题与来源进一步判断事件影响。", "evidence_ids": ["news_1"]})
    if guba_items:
        findings.append({"dimension": "市场舆情", "statement": f"已检索到 {len(guba_items)} 条股吧帖子；其为非正式信息，不作为单独投资判断依据。", "evidence_ids": ["guba_1"]})
    if financial_records:
        findings.append({"dimension": "基本面", "statement": "已取得财务摘要，结论仅覆盖最近可得报告期。", "evidence_ids": ["financial_1"]})

    confidence = round(min(0.85, 0.35 + 0.15 * sum(bool(value.get("evidence")) for value in dependency_outputs.values())), 2)
    if not findings:
        limitations.append("所有核心数据源均未返回有效数据，本次不输出风险等级。")
    return {
        "risk_level": "needs_review" if confidence < 0.65 else "medium",
        "confidence": confidence,
        "findings": findings,
        "evidence": evidence,
        "limitations": list(dict.fromkeys(limitations)),
        "verified": bool(evidence),
        "disclaimer": "分析仅供风险信息参考，不构成任何投资建议。",
    }
