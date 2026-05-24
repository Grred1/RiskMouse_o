"""
LLM 调用封装模块
支持双模式：
  - LLM_PROVIDER=coze     → 优先使用 Coze SDK，SDK 不可用时回退到 Coze HTTP API
  - LLM_PROVIDER=deepseek → 使用 DeepSeek API (本地开发)
"""
from __future__ import annotations

import os
import json
import logging
import requests as http_requests
from typing import Any

from .config import AI_CACHE_DIR

logger = logging.getLogger(__name__)

LLM_PROVIDER_ENV = "LLM_PROVIDER"
DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"
DEFAULT_MODEL_DEEPSEEK = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# Coze SDK 条件导入
_coze_sdk_available = False
try:
    from coze_coding_dev_sdk import LLMClient as _CozeLLMClient  # noqa: F401
    from coze_coding_utils.runtime_ctx.context import new_context  # noqa: F401
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage  # noqa: F401

    _coze_sdk_available = True
    logger.info("Coze SDK 可用，将使用 SDK 模式")
except ImportError:
    logger.info("Coze SDK 不可用，将使用 HTTP API 模式")


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
# Coze HTTP API 回退（当 SDK 不可用时使用）
# ---------------------------------------------------------------------------
def _get_coze_env(key: str, default: str = "") -> str:
    """延迟读取 .env 中的 Coze 配置"""
    val = os.environ.get(key, "").strip()
    if val:
        return val
    # 回退读 .env 文件
    import pathlib
    env_file = pathlib.Path(__file__).parent.parent.parent.parent / ".env"
    if env_file.exists():
        try:
            with open(env_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(f"{key}="):
                        return line[len(key) + 1:].strip().strip('"').strip("'")
        except Exception:
            pass
    return default


def _call_coze_http_api(messages: list[dict], max_tokens: int = 600, temperature: float = 0.7, model: str = "doubao-seed-1-8-251228") -> str:
    """
    当 Coze SDK 不可用时，直接通过 HTTP API 调用 Coze LLM。
    使用 Coze Integration API（与 SDK 相同的端点和认证方式）。
    响应为 SSE 流式格式，需要逐行解析拼接。
    """
    # 优先使用 Integration 环境变量（部署环境自动注入）
    base_url = (
        os.environ.get("COZE_INTEGRATION_MODEL_BASE_URL", "").strip()
        or "https://integration.coze.cn/api/v3"
    )
    # 认证：使用 Workload Identity API Key（与 SDK 一致）
    api_key = (
        os.environ.get("COZE_WORKLOAD_IDENTITY_API_KEY", "").strip()
        or os.environ.get("COZE_WORKLOAD_API_TOKEN", "").strip()
        or os.environ.get("COZE_LOOP_API_TOKEN", "").strip()
        or _get_coze_env("COZE_LOOP_API_TOKEN")
    )

    if not api_key:
        raise ValueError("Coze API Token 未设置（COZE_WORKLOAD_IDENTITY_API_KEY / COZE_LOOP_API_TOKEN）")

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }

    logger.info(f"Coze HTTP API 调用: {url}, model={model}")
    resp = http_requests.post(url, headers=headers, json=payload, stream=True, timeout=60)
    resp.raise_for_status()

    # 解析 SSE 流式响应，拼接完整文本
    full_text = ""
    resp.encoding = "utf-8"
    for line in resp.iter_lines(decode_unicode=False):
        if not line:
            continue
        # 处理 bytes 和 str 两种情况
        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="replace")
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data_text = line[5:].strip()
        if data_text in ("", "[DONE]"):
            continue
        try:
            chunk = json.loads(data_text)
            # 检查错误
            if "error" in chunk:
                err = chunk["error"]
                raise RuntimeError(f"Coze API 错误: {err.get('message', str(err))}")
            # 提取 delta content
            choices = chunk.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    full_text += content
        except json.JSONDecodeError:
            continue

    return full_text


# ---------------------------------------------------------------------------
# Coze SDK 客户端（单例）
# ---------------------------------------------------------------------------
_coze_client: Any = None


def _get_coze_sdk_client():
    global _coze_client
    if _coze_client is None:
        if not _coze_sdk_available:
            return None
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
        client = _get_coze_sdk_client()
        if client is not None:
            return client
        # SDK 不可用时返回 None，call_llm 会走 HTTP 回退
        return None
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

    Coze 模式优先使用 SDK，SDK 不可用时自动回退到 HTTP API。
    """
    provider = _get_provider()
    try:
        # 优先使用 messages，否则从 prompt 构造
        if messages is None:
            msgs: list[dict] = [{"role": "user", "content": prompt}]
        else:
            msgs = list(messages)  # 浅拷贝避免修改原列表

        # 确保有 user/human 消息
        if not any(m.get("role") in ("user", "human") for m in msgs):
            msgs.append({"role": "user", "content": "请继续"})

        if provider == "coze":
            # 路径 1：尝试 SDK
            if _coze_sdk_available:
                try:
                    from langchain_core.messages import HumanMessage as HM, SystemMessage as SM, AIMessage as AM

                    _ROLE_MAP = {
                        "system": SM,
                        "user": HM,
                        "human": HM,
                        "assistant": AM,
                        "ai": AM,
                    }
                    lc_msgs = []
                    for m in msgs:
                        cls = _ROLE_MAP.get(m.get("role", ""), HM)
                        lc_msgs.append(cls(content=m.get("content", "")))

                    if not any(isinstance(m, HM) for m in lc_msgs):
                        lc_msgs.append(HM(content="请继续"))

                    client = _get_coze_sdk_client()
                    if client is not None:
                        response = client.invoke(
                            messages=lc_msgs,
                            temperature=temperature,
                            max_completion_tokens=max_tokens,
                        )
                        return _safe_get_text_content(response.content)
                except Exception as e:
                    logger.warning(f"Coze SDK 调用失败，回退到 HTTP API: {e}")

            # 路径 2：HTTP API 回退
            return _call_coze_http_api(
                messages=msgs,
                max_tokens=max_tokens,
                temperature=temperature,
                model=model or "doubao-seed-1-8-251228",
            )
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
