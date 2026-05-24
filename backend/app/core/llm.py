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


def _read_key_from_dotenv_file() -> str:
    """直接解析 .env 文件，不依赖 python-dotenv 库"""
    import pathlib
    env_file = pathlib.Path(__file__).parent.parent.parent.parent / ".env"
    if not env_file.exists():
        return ""
    try:
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{DEEPSEEK_API_KEY_ENV}="):
                    value = line[len(DEEPSEEK_API_KEY_ENV) + 1:].strip().strip('"').strip("'")
                    return value
    except Exception:
        pass
    return ""


def _get_deepseek_client():
    global _deepseek_client
    if _deepseek_client is None:
        from openai import OpenAI

        api_key = os.environ.get(DEEPSEEK_API_KEY_ENV, "") or _read_key_from_dotenv_file()
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
    prompt: str = "",
    max_tokens: int = 600,
    temperature: float = 0.7,
    model: str | None = None,
    messages: list[dict] | None = None,
) -> str:
    """
    调用大模型。
    支持两种传参方式：
      1. messages=[...]  — 直接传入完整消息列表（推荐，兼容 Coze 平台）
      2. prompt="..."    — 传入单条文本，自动包装为 user 消息

    Coze 平台要求必须包含 human message（role=user）。
    """
    provider = _get_provider()
    try:
        # 优先使用 messages，否则从 prompt 构造
        if messages is None:
            msgs: list[dict] = [{"role": "user", "content": prompt}]
        else:
            msgs = messages

        # 确保有 user/human 消息（Coze 平台要求）
        if not any(m.get("role") in ("user", "human") for m in msgs):
            msgs.append({"role": "user", "content": "请继续"})

        if provider == "coze":
            client = _get_coze_client()
            response = client.invoke(
                messages=msgs,
                temperature=temperature,
                max_completion_tokens=max_tokens,
            )
            return _safe_get_text_content(response.content)
        else:
            client = _get_deepseek_client()
            response = client.chat.completions.create(
                model=model or DEFAULT_MODEL_DEEPSEEK,
                messages=msgs,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
    except (ValueError, ImportError) as e:
        return str(e)
    except Exception as e:
        return f"AI 调用失败: {str(e)}"


_ERROR_PREFIXES = ("AI 调用失败", "DeepSeek API Key", "DEEPSEEK_API_KEY", "未配置")


def cached_llm_call(
    symbol: str,
    cache_key: str,
    prompt_fn,
) -> str:
    cache_file = os.path.join(AI_CACHE_DIR, f"{symbol}_{cache_key}.json")

    if os.path.exists(cache_file):
        try:
            cached = json.load(open(cache_file, "r", encoding="utf-8")).get("result", "")
            # 跳过缓存的错误结果，重新调用
            if cached and not any(cached.startswith(p) for p in _ERROR_PREFIXES):
                return cached
        except Exception:
            pass

    result = prompt_fn()

    # 只缓存成功的结果
    if result and any(result.startswith(p) for p in _ERROR_PREFIXES):
        return result

    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"result": result}, f, ensure_ascii=False)
    except Exception:
        pass

    return result
