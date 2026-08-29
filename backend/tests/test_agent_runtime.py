"""离线评测：不访问 AKShare 或 LLM，也能验证编排安全性与降级行为。"""
from __future__ import annotations

import unittest

from backend.app.agent_runtime.planner import create_plan, create_patrol_plan
from backend.app.agent_runtime.memory import _tokens
from backend.app.agent_runtime.verifier import verify_report


class PlannerTests(unittest.TestCase):
    def test_plan_only_uses_allowlisted_tools(self):
        plan = create_plan("分析宁德时代近期风险", "300750")
        self.assertEqual([task.id for task in plan.tasks], ["financial", "news", "sentiment", "report"])
        self.assertEqual(plan.tasks[-1].depends_on, ["financial", "news", "sentiment"])

    def test_global_patrol_has_one_controlled_task(self):
        plan = create_patrol_plan("session-1")
        self.assertEqual(plan.kind, "global_patrol")
        self.assertEqual(plan.session_id, "session-1")
        self.assertEqual([(task.id, task.tool) for task in plan.tasks], [("patrol", "run_deep_surf")])


class MemoryRetrievalTests(unittest.TestCase):
    def test_chinese_tokens_contain_reusable_bigrams(self):
        tokens = _tokens("新能源板块风险")
        self.assertIn("新能源板块风险", tokens)
        self.assertIn("风险", tokens)


class VerificationTests(unittest.TestCase):
    def test_no_evidence_returns_needs_review(self):
        report = verify_report({
            "financial": {"records": [], "evidence": [], "limitations": ["财务数据缺失"]},
            "news": {"items": [], "evidence": [], "limitations": ["新闻数据缺失"]},
            "sentiment": {"items": [], "evidence": [], "limitations": ["股吧数据缺失"]},
        })
        self.assertFalse(report["verified"])
        self.assertEqual(report["risk_level"], "needs_review")
        self.assertTrue(report["limitations"])

    def test_evidence_is_preserved_in_final_report(self):
        report = verify_report({
            "financial": {"records": [{"报告期": "2025-12-31"}], "evidence": [{"id": "financial_1"}], "limitations": []},
            "news": {"items": [{"title": "测试新闻"}], "evidence": [{"id": "news_1"}], "limitations": []},
            "sentiment": {"items": [], "evidence": [], "limitations": []},
        })
        self.assertTrue(report["verified"])
        self.assertEqual({item["id"] for item in report["evidence"]}, {"financial_1", "news_1"})

    def test_empty_tool_output_cannot_create_evidence(self):
        report = verify_report({
            "financial": {"records": [], "evidence": [], "limitations": ["无数据"]},
            "news": {"items": [], "evidence": [], "limitations": ["无数据"]},
            "sentiment": {"items": [], "evidence": [], "limitations": ["无数据"]},
        })
        self.assertEqual(report["evidence"], [])
        self.assertFalse(report["verified"])


if __name__ == "__main__":
    unittest.main()
