"""面向前端与调试的 Agent 工作流 API。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..agent_runtime import create_plan, create_patrol_plan, start, store
from ..agent_runtime.schemas import to_dict
from ..core import extract_pure_code, normalize_symbol
from .. import db
from ..tools import list_tools

router = APIRouter(prefix="/api/agent", tags=["Agent工作流"])


class WorkflowRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    symbol: str = Field(..., min_length=1, max_length=20)
    session_id: str = Field(default="", max_length=100)


@router.get("/tools")
def get_tools():
    """返回 Agent 可调用工具白名单，供调试和前端展示。"""
    return {"tools": list_tools()}


@router.post("/plan")
def plan_workflow(req: WorkflowRequest):
    """仅生成计划，不会访问外部数据源。"""
    try:
        symbol = extract_pure_code(normalize_symbol(req.symbol))
        return {"plan": to_dict(create_plan(req.question, symbol, req.session_id))}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"无法生成任务计划: {exc}")


@router.post("/run")
def run_workflow(req: WorkflowRequest):
    """异步启动工作流；客户端可用 run_id 查询每一步状态。"""
    try:
        symbol = extract_pure_code(normalize_symbol(req.symbol))
        plan = create_plan(req.question, symbol, req.session_id)
        run_id = start(plan)
        return {"run_id": run_id, "status": "pending", "plan": to_dict(plan)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"无法启动工作流: {exc}")


@router.post("/patrol")
def run_global_patrol(session_id: str = ""):
    """通过全局编排器启动小老鼠深度巡检。"""
    run_id = start(create_patrol_plan(session_id=session_id[:100]))
    return {"run_id": run_id, "status": "pending", "kind": "global_patrol"}


@router.get("/runs/{run_id}")
def get_workflow_run(run_id: str):
    run = store.snapshot(run_id)
    if not run:
        run = db.get_workflow_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="未找到该工作流运行记录")
    return run
