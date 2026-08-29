"""将已有的后台能力包装成受控任务，统一由编排器管理。"""
from __future__ import annotations

from .registry import register_tool


@register_tool("run_deep_surf", "执行宏观新闻与自选股股吧的全局风险巡检", timeout_seconds=180)
def run_deep_surf() -> dict:
    # 延迟导入，避免 API 初始化时与 mouse_agent 发生循环依赖。
    from ..api.mouse_agent import _deep_surf, _get_screen

    _deep_surf()
    return {"screen": _get_screen(), "evidence": [], "limitations": []}
