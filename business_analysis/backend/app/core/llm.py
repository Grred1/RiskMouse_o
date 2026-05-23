"""
LLM 调用封装模块
统一管理 AI 模型调用
"""
from __future__ import annotations

import os
import json
from typing import Optional

from coze_coding_dev_sdk import LLMClient
from coze_coding_utils.runtime_ctx.context import new_context
from langchain_core.messages import HumanMessage

from .config import AI_CACHE_DIR


# 全局 LLM 客户端
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """获取 LLM 客户端（单例）"""
    global _llm_client
    if _llm_client is None:
        ctx = new_context(method="invoke")
        _llm_client = LLMClient(ctx=ctx)
    return _llm_client


def _safe_get_text_content(content) -> str:
    """安全获取文本内容，处理多种响应格式"""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        if content and isinstance(content[0], str):
            return " ".join(content)
        else:
            # 处理 dict 格式的多模态响应
            text_parts = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            return " ".join(text_parts)
    return str(content)


def call_llm(
    prompt: str,
    max_tokens: int = 600,
    temperature: float = 0.7,
    model: str = "doubao-seed-2-0-lite-260215",
) -> str:
    """
    调用 LLM 生成文本

    Args:
        prompt: 输入提示词
        max_tokens: 最大输出 token 数
        temperature: 温度参数
        model: 模型名称

    Returns:
        LLM 生成的文本内容
    """
    try:
        client = get_llm_client()
        messages = [HumanMessage(content=prompt)]
        response = client.invoke(
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_tokens,
        )
        return _safe_get_text_content(response.content)
    except Exception as e:
        return f"AI 调用失败: {str(e)}"


def cached_llm_call(
    symbol: str,
    cache_key: str,
    prompt_fn,
) -> str:
    """
    带缓存的 LLM 调用

    Args:
        symbol: 股票代码（用于缓存目录）
        cache_key: 缓存键名
        prompt_fn: 生成提示词的函数

    Returns:
        AI 分析结果
    """
    cache_file = os.path.join(AI_CACHE_DIR, f"{symbol}_{cache_key}.json")

    # 检查缓存
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f).get("result", "")
        except Exception:
            pass

    # 执行 AI 调用
    result = prompt_fn()

    # 保存缓存
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"result": result}, f, ensure_ascii=False)
    except Exception:
        pass

    return result
