"""轻量 DAG 编排器：依赖调度、并发、重试、超时和运行轨迹。"""
from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from copy import deepcopy
from datetime import datetime
from typing import Any

from ..tools import get_tool
from .. import db
from .schemas import TaskPlan, TaskResult, TaskStatus, to_dict


class WorkflowStore:
    def __init__(self):
        self._runs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create(self, plan: TaskPlan) -> str:
        run_id = uuid.uuid4().hex
        with self._lock:
            self._runs[run_id] = {"run_id": run_id, "status": "pending", "created_at": datetime.now().isoformat(), "completed_at": None, "plan": to_dict(plan), "tasks": {task.id: to_dict(TaskResult(task.id, task.tool)) for task in plan.tasks}, "result": None}
            db.create_workflow_run(self._runs[run_id])
        return run_id

    def snapshot(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            run = self._runs.get(run_id)
            return deepcopy(run) if run else None

    def update(self, run_id: str, **fields: Any) -> None:
        with self._lock:
            self._runs[run_id].update(fields)
            db.update_workflow_run(run_id, self._runs[run_id]["status"], self._runs[run_id].get("completed_at"), self._runs[run_id].get("result"))

    def task(self, run_id: str, task_id: str, **fields: Any) -> None:
        with self._lock:
            self._runs[run_id]["tasks"][task_id].update(fields)
            db.update_workflow_task(run_id, self._runs[run_id]["tasks"][task_id])


store = WorkflowStore()


def start(plan: TaskPlan) -> str:
    run_id = store.create(plan)
    threading.Thread(target=execute, args=(run_id, plan), daemon=True).start()
    return run_id


def execute(run_id: str, plan: TaskPlan) -> None:
    store.update(run_id, status="running")
    pending = {task.id: task for task in plan.tasks}
    outputs: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="riskmouse-agent") as pool:
        while pending:
            ready = [task for task in pending.values() if all(task_id in outputs for task_id in task.depends_on)]
            if not ready:
                for task in pending.values():
                    store.task(run_id, task.id, status=TaskStatus.SKIPPED.value, error="依赖任务未成功，已跳过")
                break
            futures = {pool.submit(_run_task, run_id, task, outputs): task for task in ready}
            for future, task in futures.items():
                result = future.result()
                if result.status == TaskStatus.SUCCEEDED:
                    outputs[task.id] = result.output
            for task in ready:
                pending.pop(task.id, None)
    report = outputs.get("report", {}).get("report")
    # 巡检等非报告型任务也应有可查询的最终结果。
    final_result = report or outputs.get("patrol")
    store.update(run_id, status="succeeded" if final_result else "partial", completed_at=datetime.now().isoformat(), result=final_result)


def _run_task(run_id: str, task, outputs: dict[str, dict]) -> TaskResult:
    store.task(run_id, task.id, status=TaskStatus.RUNNING.value)
    started = time.perf_counter()
    result = TaskResult(task.id, task.tool, status=TaskStatus.FAILED)
    tool = get_tool(task.tool)
    payload = {**task.input}
    if task.depends_on:
        payload["dependency_outputs"] = {key: outputs[key] for key in task.depends_on if key in outputs}
    for attempt in range(task.retries + 1):
        result.attempts = attempt + 1
        # 不使用 with：超时后不能等待卡住的网络线程结束，工作流本身必须继续推进。
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(tool.handler, **payload)
        try:
            result.output = future.result(timeout=task.timeout_seconds or tool.timeout_seconds)
            result.status = TaskStatus.SUCCEEDED
            break
        except TimeoutError:
            result.error = f"工具调用超时（{task.timeout_seconds} 秒）"
            future.cancel()
        except Exception as exc:
            result.error = str(exc)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
    result.duration_ms = int((time.perf_counter() - started) * 1000)
    # task_id 已作为定位参数传入，不能再通过 **fields 重复传递。
    stored_result = to_dict(result)
    stored_result.pop("task_id", None)
    store.task(run_id, task.id, **stored_result)
    return result
