"""受控工具注册表：编排器只能调用显式注册的工具。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    handler: Callable[..., dict[str, Any]]
    timeout_seconds: int = 20


_TOOLS: dict[str, Tool] = {}


def register_tool(name: str, description: str, timeout_seconds: int = 20):
    def decorator(handler: Callable[..., dict[str, Any]]):
        if name in _TOOLS:
            raise ValueError(f"重复注册工具: {name}")
        _TOOLS[name] = Tool(name, description, handler, timeout_seconds)
        return handler
    return decorator


def get_tool(name: str) -> Tool:
    tool = _TOOLS.get(name)
    if not tool:
        raise ValueError(f"未注册工具: {name}")
    return tool


def list_tools() -> list[dict[str, str | int]]:
    return [
        {"name": tool.name, "description": tool.description, "timeout_seconds": tool.timeout_seconds}
        for tool in _TOOLS.values()
    ]
