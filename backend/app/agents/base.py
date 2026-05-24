"""
Agent 基类
所有 Agent 继承此基类，核心能力：
  1. run() — 查缓存 → 拼 prompt → call_llm → 缓存 → 返回
  2. 支持两种模式：
     a) prompt_template + input_keys → 自动格式化
     b) inputs 传 prompt_text → 直接使用（兼容现有 API 层的 prompt 拼装）
  3. 自动从 prompts/ 目录加载提示词文件
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from ..core import call_llm, read_cache, write_cache

# Agent 自带的 prompts 目录
_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROMPTS_DIR = os.path.join(_AGENT_DIR, "prompts")
_PROMPT_CACHE: dict[str, str] = {}


def load_prompt(name: str) -> str:
    """从 prompts 目录加载提示词文件

    用法:
        prompt = load_prompt("zygc_analysis")  # → prompts/zygc_analysis.txt
    """
    if name in _PROMPT_CACHE:
        return _PROMPT_CACHE[name]

    path = os.path.join(_PROMPTS_DIR, f"{name}.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            _PROMPT_CACHE[name] = content
            return content

    raise FileNotFoundError(f"提示词文件不存在: {path}")


@dataclass
class Agent:
    name: str
    description: str
    category: str                       # finance / sentiment / macro / super
    prompt_name: str = ""               # 对应 prompts/{name}.txt，优先于 prompt_template
    prompt_template: str = ""
    input_keys: list[str] = field(default_factory=list)
    cache_key_pattern: str = ""         # 如 "finance:zygc_analysis:{code}"
    cache_ttl: int = 86400
    max_tokens: int = 600
    temperature: float = 0.3
    input_builder: Optional[Callable] = None   # 预处理 inputs，返回完整 inputs
    output_parser: Optional[Callable] = None   # 解析 LLM 返回值

    def _get_prompt(self, inputs: dict) -> str:
        # 1. 优先使用传入的 prompt_text（兼容现有 API 层的拼装逻辑）
        prompt_text = inputs.get("prompt_text", "")
        if prompt_text:
            return prompt_text

        # 2. 从文件加载
        if self.prompt_name:
            template = load_prompt(self.prompt_name)
            if self.input_keys:
                return template.format(**inputs)
            return template.format(**inputs) if "{" in template else template

        # 3. 从 prompt_template 字段
        if self.prompt_template:
            return self.prompt_template.format(**inputs)

        raise ValueError(f"Agent '{self.name}': 未提供 prompt_text/prompt_name/prompt_template")

    def _build_cache_key(self, inputs: dict) -> str:
        if not self.cache_key_pattern:
            return ""
        try:
            return self.cache_key_pattern.format(**inputs)
        except KeyError:
            return ""

    def run(self, inputs: dict) -> str:
        if self.input_builder:
            inputs = self.input_builder(inputs)

        if self.cache_key_pattern:
            cache_key = self._build_cache_key(inputs)
            if cache_key:
                cached = read_cache(cache_key, module="agent")
                if cached and "data" in cached:
                    return cached["data"]

        prompt = self._get_prompt(inputs)

        result = call_llm(
            messages=[
                {"role": "system", "content": self.description or ""},
                {"role": "user", "content": prompt},
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )

        if self.output_parser:
            result = self.output_parser(result)

        if self.cache_key_pattern:
            cache_key = self._build_cache_key(inputs)
            if cache_key:
                write_cache(cache_key, {"data": result}, module="agent")

        return result

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "input_keys": self.input_keys,
        }
