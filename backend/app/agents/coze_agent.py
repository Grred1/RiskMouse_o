"""
Coze 外部 Agent 调用封装
提供统一的 Coze Stream API 调用接口，用于调用外部 Coze 机器人。

功能：
  - call_coze_agent() — 调用外部 Coze Agent（SSE 流式）
  - verify_news() — 真伪鉴定（调用外部鉴定 Agent）

环境变量配置（.env）：
  COZE_API_URL=https://xks6nwtnyr.coze.site/stream_run
  COZE_BEARER_TOKEN=eyJ...
  COZE_SESSION_ID=8UYU6_W1noNrbFPnE4qeu
  COZE_PROJECT_ID=7643022710771204136
"""
from __future__ import annotations

import json
import os
import time

import requests

# ── 延迟读取环境变量（确保 load_dotenv 已执行） ────────────────────────
def _get_env(key: str, default: str = "") -> str:
    """每次调用时读取环境变量，确保 .env 已加载。"""
    val = os.environ.get(key, default)
    return val.strip() if val else default


def call_coze_agent(
    query_text: str,
    *,
    api_url: str | None = None,
    bearer_token: str | None = None,
    session_id: str | None = None,
    project_id: str | None = None,
    timeout: tuple[int, int] = (10, 60),
) -> str:
    """
    调用 Coze Agent（SSE 流式），返回完整回复文本。

    参数:
        query_text: 要查询/鉴定的文本
        api_url: 覆盖默认 API URL
        bearer_token: 覆盖默认 Token
        session_id: 覆盖默认 Session ID
        project_id: 覆盖默认 Project ID
        timeout: (连接超时, 读取超时)

    返回:
        Agent 完整回复文本。失败时返回空字符串。

    用法:
        >>> reply = call_coze_agent("2026-05-19 欧盟议会通过钢铁关税翻倍")
        >>> print(reply)
    """
    url = api_url or _get_env("COZE_API_URL", "https://xks6nwtnyr.coze.site/stream_run")
    token = bearer_token or _get_env("COZE_BEARER_TOKEN")
    sid = session_id or _get_env("COZE_SESSION_ID", "Wo7hBi1xBAC9pCWEWbQkN")
    pid = project_id or _get_env("COZE_PROJECT_ID", "7643022710771204136")

    if not token:
        return ""

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    payload = {
        "content": {
            "query": {
                "prompt": [
                    {
                        "type": "text",
                        "content": {"text": query_text},
                    }
                ]
            }
        },
        "type": "query",
        "session_id": sid,
        "project_id": pid,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, stream=True, timeout=timeout)
    except Exception:
        return ""

    if response.status_code != 200:
        return ""

    full_reply = ""
    for line in response.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        data_text = line[5:].strip()
        if not data_text:
            continue
        try:
            event = json.loads(data_text)
            if event.get("type") == "answer":
                answer = event.get("content", {}).get("answer", "")
                if isinstance(answer, str):
                    full_reply += answer
        except json.JSONDecodeError:
            pass

    return full_reply


def verify_news(news_text: str) -> dict:
    """
    调用真伪鉴别 Agent 鉴定一条金融消息。

    返回:
        {
            "authentic": True/False,    # 消息是否可信
            "confidence": "高/中/低",    # 置信度
            "reason": "判断理由",
        }
    """
    query = f"请鉴定以下金融消息的真伪：\n{news_text}\n\n请给出判断结果、置信度和理由。"
    reply = call_coze_agent(query)

    if not reply:
        import logging
        logging.getLogger("coze_agent").warning("call_coze_agent 返回空，token=%s..., url=%s", token[:10] if token else "空", url)
        return {
            "authentic": None,
            "confidence": "低",
            "reason": "Agent 调用失败，无法鉴定",
        }

    # 尝试解析为结构化 JSON
    try:
        start = reply.find("{")
        end = reply.rfind("}")
        if start >= 0 and end > start:
            parsed = json.loads(reply[start : end + 1])
            # Agent 可能返回中文字段名，兼容多种格式
            judgment = parsed.get("判定结果", parsed.get("judgment", ""))
            if judgment:
                # 清理 emoji 等前缀符号
                judgment_clean = judgment.replace("✅", "").replace("❌", "").strip()
                authentic = "虚假" not in judgment_clean and "假" not in judgment_clean
            else:
                authentic = parsed.get("authentic", parsed.get("is_real", True))
                if isinstance(authentic, str):
                    authentic = authentic.lower() in ("true", "真实", "可信", "属实")
            # 置信度：数字或文字
            confidence_raw = parsed.get("置信度分数", parsed.get("confidence", "中"))
            if isinstance(confidence_raw, (int, float)):
                if confidence_raw >= 8:
                    confidence = "高"
                elif confidence_raw >= 4:
                    confidence = "中"
                else:
                    confidence = "低"
            else:
                confidence = confidence_raw if confidence_raw in ("高", "中", "低") else "中"
            # 理由：取多个可能的字段
            reason = parsed.get("判定理由", parsed.get("reason", parsed.get("explanation", "")))
            if not reason:
                reason = parsed.get("建议信息源", "")
                if isinstance(reason, list):
                    reason = "，".join(reason)
            return {
                "authentic": authentic,
                "confidence": confidence,
                "reason": reason or reply[:150],
            }
    except json.JSONDecodeError:
        pass

    # 回退：用关键字判断
    reply_lower = reply.lower()
    is_authentic = any(kw in reply_lower for kw in ["真实", "可信", "正确", "属实"])
    return {
        "authentic": is_authentic,
        "confidence": "中",
        "reason": reply[:120],
    }
