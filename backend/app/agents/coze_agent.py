"""Coze 外部 Agent 调用封装。

所有访问凭据必须通过本机 `.env` 或系统环境变量提供，不能写入代码库。
"""
from __future__ import annotations

import json
import logging
import os

import requests


def _get_env(key: str, default: str = "") -> str:
    """每次调用时读取环境变量，确保 .env 已加载。"""
    value = os.environ.get(key, default)
    return value.strip() if value else default


def call_coze_agent(
    query_text: str,
    *,
    api_url: str | None = None,
    bearer_token: str | None = None,
    session_id: str | None = None,
    project_id: str | None = None,
    timeout: tuple[int, int] = (10, 60),
) -> str:
    """调用 Coze Stream API，失败时返回空字符串。"""
    url = api_url or _get_env("COZE_API_URL", "https://vj2f4knwyx.coze.site/stream_run")
    token = bearer_token or _get_env("COZE_BEARER_TOKEN")
    sid = session_id or _get_env("COZE_SESSION_ID")
    pid = project_id or _get_env("COZE_PROJECT_ID")

    if not token or not sid or not pid:
        logging.getLogger("coze_agent").warning("Coze 配置不完整，跳过外部 Agent 调用")
        return ""

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    payload = {
        "content": {"query": {"prompt": [{"type": "text", "content": {"text": query_text}}]}},
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

    reply = ""
    for line in response.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        try:
            event = json.loads(line[5:].strip())
            if event.get("type") == "answer":
                answer = event.get("content", {}).get("answer", "")
                if isinstance(answer, str):
                    reply += answer
        except json.JSONDecodeError:
            continue
    return reply


def verify_news(news_text: str) -> dict:
    """调用外部 Agent 鉴定新闻，返回统一的可信度结构。"""
    reply = call_coze_agent(f"请鉴定以下金融消息的真伪：\n{news_text}\n\n请给出判断结果、置信度和理由。")
    if not reply:
        return {"authentic": None, "confidence": "低", "reason": "Agent 调用失败，无法鉴定"}

    try:
        start, end = reply.find("{"), reply.rfind("}")
        if start >= 0 and end > start:
            parsed = json.loads(reply[start : end + 1])
            judgment = parsed.get("判定结果", parsed.get("judgment", ""))
            if judgment:
                cleaned = str(judgment).replace("✅", "").replace("❌", "").strip()
                authentic = "虚假" not in cleaned and "假" not in cleaned
            else:
                authentic = parsed.get("authentic", parsed.get("is_real", True))
                if isinstance(authentic, str):
                    authentic = authentic.lower() in ("true", "真实", "可信", "属实")
            confidence = parsed.get("置信度", parsed.get("confidence", "中"))
            if confidence not in ("高", "中", "低"):
                confidence = "中"
            reason = parsed.get("判定理由", parsed.get("reason", parsed.get("explanation", "")))
            return {"authentic": authentic, "confidence": confidence, "reason": reason or reply[:150]}
    except json.JSONDecodeError:
        pass

    reply_lower = reply.lower()
    return {
        "authentic": any(word in reply_lower for word in ("真实", "可信", "正确", "属实")),
        "confidence": "中",
        "reason": reply[:120],
    }
