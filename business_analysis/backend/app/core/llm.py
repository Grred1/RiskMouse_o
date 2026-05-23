"""
LLM 调用封装模块
支持双模式：
  - LLM_PROVIDER=coze     → 使用 Coze SDK (Coze 平台内)
  - LLM_PROVIDER=deepseek → 使用 DeepSeek API (本地开发)
"""
from __future__ import annotations

import os
import json
from typing import Any

from .config import AI_CACHE_DIR

LLM_PROVIDER_ENV = "LLM_PROVIDER"
DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"
DEFAULT_MODEL_DEEPSEEK = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# Coze SDK 仅 Coze 平台可用，做条件导入
_coze_available = False
try:
    from coze_coding_dev_sdk import LLMClient  # noqa: F401
    from coze_coding_utils.runtime_ctx.context import new_context  # noqa: F401

    _coze_available = True
except ImportError:
    pass


def _get_provider() -> str:
    return os.environ.get(LLM_PROVIDER_ENV, "deepseek").strip().lower()


# ---------------------------------------------------------------------------
# DeepSeek 客户端（单例）
# ---------------------------------------------------------------------------
_deepseek_client: Any = None


def _get_deepseek_client():
    global _deepseek_client
    if _deepseek_client is None:
        from openai import OpenAI

        api_key = os.environ.get(DEEPSEEK_API_KEY_ENV, "")
        if not api_key:
            raise ValueError(
                f"DeepSeek API Key 未设置。请在环境变量 {DEEPSEEK_API_KEY_ENV} 中配置。"
            )
        _deepseek_client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)
    return _deepseek_client


# ---------------------------------------------------------------------------
# Coze 客户端（单例）
# ---------------------------------------------------------------------------
_coze_client: Any = None


def _get_coze_client():
    global _coze_client
    if _coze_client is None:
        if not _coze_available:
            raise ImportError(
                "当前环境为 coze 模式，但 coze-coding-dev-sdk 不可用。"
                "请在 Coze 平台中运行，或设置 LLM_PROVIDER=deepseek 使用 DeepSeek。"
            )
        from coze_coding_dev_sdk import LLMClient
        from coze_coding_utils.runtime_ctx.context import new_context

        ctx = new_context(method="invoke")
        _coze_client = LLMClient(ctx=ctx)
    return _coze_client


# ---------------------------------------------------------------------------
# 公开接口
# ---------------------------------------------------------------------------


def get_llm_client():
    provider = _get_provider()
    if provider == "coze":
        return _get_coze_client()
    return _get_deepseek_client()


def _safe_get_text_content(content) -> str:
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, str):
                texts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))
        return " ".join(texts)
    return str(content)


def call_llm(
    prompt: str,
    max_tokens: int = 600,
    temperature: float = 0.7,
    model: str | None = None,
) -> str:
    provider = _get_provider()
    try:
        if provider == "coze":
            client = _get_coze_client()
            response = client.invoke(
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_completion_tokens=max_tokens,
            )
            return _safe_get_text_content(response.content)
        else:
            client = _get_deepseek_client()
            response = client.chat.completions.create(
                model=model or DEFAULT_MODEL_DEEPSEEK,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
    except (ValueError, ImportError) as e:
        return str(e)
    except Exception as e:
        return f"AI 调用失败: {str(e)}"


def cached_llm_call(
    symbol: str,
    cache_key: str,
    prompt_fn,
) -> str:
    cache_file = os.path.join(AI_CACHE_DIR, f"{symbol}_{cache_key}.json")

    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f).get("result", "")
        except Exception:
            pass

    result = prompt_fn()

    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"result": result}, f, ensure_ascii=False)
    except Exception:
        pass

    return result
