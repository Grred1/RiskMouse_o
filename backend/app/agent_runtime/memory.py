"""小老鼠记忆系统。

借鉴 Claude Code 的“会话摘要 + 按需召回 + 后台巩固”原则，
但只保存风控场景真正稳定、对后续决策有价值的信息。
"""
from __future__ import annotations

import re
import threading
from collections import Counter

from .. import db

MEMORY_TYPES = {"preference", "risk_focus", "feedback", "project", "reference"}
_MEMORY_LOCK = threading.Lock()


def _tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for phrase in re.findall(r"[\u4e00-\u9fff]{2,}", text.lower()):
        tokens.append(phrase)
        # 中文没有天然空格：保留完整词组，同时加入双字片段提高召回率。
        tokens.extend(phrase[index:index + 2] for index in range(len(phrase) - 1))
    tokens.extend(re.findall(r"[A-Za-z0-9_]{2,}", text.lower()))
    return list(dict.fromkeys(tokens))[:80]


def _format_messages(messages: list[dict]) -> str:
    if not messages:
        return "（这是一次新会话）"
    return "\n".join(f"{'用户' if item['role'] == 'user' else '小老鼠'}: {item['content'][:500]}" for item in messages)


def build_context(session_id: str, query: str) -> dict[str, str]:
    """读取有限的短期历史和相关长期记忆，避免把所有历史塞进 Prompt。"""
    session = db.get_agent_session(session_id) or {}
    messages = db.get_agent_messages(session_id, limit=8)
    memories = db.search_agent_memories(_tokens(query), limit=5, space_id=session.get("space_id", "default"))
    short_term = _format_messages(messages)
    if session.get("summary"):
        short_term = f"会话摘要: {session['summary']}\n最近对话:\n{short_term}"
    long_term = "\n".join(
        f"- [{item['memory_type']}] {item['content']}" for item in memories
    ) or "（没有与本轮问题相关的长期记忆）"
    return {"short_term_memory": short_term[:5000], "long_term_memory": long_term[:3000]}


def remember(memory_type: str, content: str, source: str = "user", importance: int = 2, space_id: str = "default") -> dict:
    if memory_type not in MEMORY_TYPES:
        raise ValueError(f"不支持的记忆类型: {memory_type}")
    clean = " ".join(content.split())
    if not clean:
        raise ValueError("记忆内容不能为空")
    # 不保存凭据、极短语句或明显的临时行情描述。
    if re.search(r"(api[_ -]?key|密码|token|sk-[\w-]+)", clean, flags=re.I):
        raise ValueError("不保存密钥、密码或 Token")
    if len(clean) < 6:
        raise ValueError("记忆内容过短，无法形成稳定偏好或规则")
    return db.add_agent_memory(memory_type, clean, " ".join(_tokens(clean)), importance, source, space_id)


def maybe_extract_explicit_memory(text: str, space_id: str = "default") -> dict | None:
    """仅处理明确的“记住”请求，避免后台猜测用户隐私或临时市场信息。"""
    match = re.search(r"(?:请)?记住[：:，,\s]*(.+)", text)
    if not match:
        return None
    content = match.group(1).strip("。！! ")
    if not content:
        return None
    memory_type = "preference"
    if any(word in content for word in ("风险", "仓位", "止损", "关注", "股票", "行业")):
        memory_type = "risk_focus"
    if any(word in content for word in ("不要", "应该", "纠正", "以后")):
        memory_type = "feedback"
    return remember(memory_type, content, source="explicit", importance=3, space_id=space_id)


def consolidate_session(session_id: str, active_goal: str = "") -> None:
    """后台压缩会话：保留近期主题和用户关注点，不调用 LLM，零额外成本。"""
    if not _MEMORY_LOCK.acquire(blocking=False):
        return
    try:
        messages = db.get_agent_messages(session_id, limit=24)
        user_text = " ".join(item["content"] for item in messages if item["role"] == "user")
        keywords = [word for word, _ in Counter(_tokens(user_text)).most_common(8)]
        summary = "近期会话关注：" + ("、".join(keywords) if keywords else "暂无稳定主题")
        db.update_agent_session_summary(session_id, summary, active_goal)
    finally:
        _MEMORY_LOCK.release()
