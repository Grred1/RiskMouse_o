"""Agent 工作流的稳定数据契约。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskSpec:
    id: str
    tool: str
    depends_on: list[str] = field(default_factory=list)
    input: dict[str, Any] = field(default_factory=dict)
    retries: int = 1
    timeout_seconds: int = 20


@dataclass
class TaskResult:
    task_id: str
    tool: str
    status: TaskStatus = TaskStatus.PENDING
    output: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    attempts: int = 0
    duration_ms: int = 0


@dataclass
class TaskPlan:
    goal: str
    symbol: str
    tasks: list[TaskSpec]
    planner: str = "rule_based_v1"
    session_id: str = ""
    kind: str = "risk_analysis"


def to_dict(value: Any) -> dict:
    """将 dataclass / enum 递归转换为 API 可序列化数据。"""
    if hasattr(value, "__dataclass_fields__"):
        return to_dict(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: to_dict(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_dict(item) for item in value]
    return value
