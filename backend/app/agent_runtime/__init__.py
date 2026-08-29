from .planner import create_plan, create_patrol_plan

__all__ = ["start", "store", "create_plan", "create_patrol_plan"]


def __getattr__(name):
    """延迟加载执行器，保持计划与验证层可脱离外部数据源进行测试。"""
    if name in {"start", "store"}:
        from .orchestrator import start, store
        return {"start": start, "store": store}[name]
    raise AttributeError(name)
