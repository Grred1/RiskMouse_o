"""
API 模块 - 路由定义
"""
from .finance import router as finance_router
from .sentiment import router as sentiment_router
from .watchlist import router as watchlist_router
from .mouse_agent import router as mouse_agent_router
from .macro import router as macro_router
from .agent_workflow import router as agent_workflow_router

__all__ = ["finance_router", "sentiment_router", "watchlist_router", "mouse_agent_router", "macro_router", "agent_workflow_router"]
